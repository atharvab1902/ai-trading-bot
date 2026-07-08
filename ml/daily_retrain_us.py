"""US market daily ML retrainer — runs after NYSE close (16:45 ET).

Unlike the India retrainer, this has no DuckDB dependency because we don't
collect historical Alpaca bars. It trains exclusively on real closed trades
from trades.db. As trades accumulate daily, the model progressively learns
US market-specific patterns and diverges from the India starting point.

Minimum trades to retrain: 10 (below that, skip — not enough signal)
Deploy condition: improvement >= -2% on held-out trades (or no old model)

Usage:
    python -m ml.daily_retrain_us
    python -m ml.daily_retrain_us --account us_trader --force
"""

import argparse
import json
import logging
import pickle
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pytz
from xgboost import XGBClassifier
from sklearn.metrics import precision_score

from ml.features import FEATURE_COLS

REPO_ROOT = Path(__file__).parent.parent
TRADES_DB = REPO_ROOT / "data" / "trades.db"
JOURNAL   = REPO_ROOT / "data" / "journal.md"
IST       = pytz.timezone("Asia/Kolkata")
ET        = pytz.timezone("US/Eastern")

log = logging.getLogger(__name__)

MIN_TRADES      = 10     # don't retrain below this
MIN_IMPROVEMENT = -0.02  # tolerate 2% sharpe drop (noise)


def load_us_trades(account: str) -> list[dict]:
    """Load all closed US trades with ML features from trades.db."""
    try:
        con = sqlite3.connect(TRADES_DB)
        rows = con.execute("""
            SELECT side, pnl, signal_features
            FROM trades
            WHERE status='closed'
              AND signal_features IS NOT NULL
              AND pnl IS NOT NULL
              AND account=?
            ORDER BY ts ASC
        """, (account,)).fetchall()
        con.close()
    except Exception as e:
        log.warning(f"Trade load failed: {e}")
        return []

    records = []
    for side, pnl, sf_json in rows:
        try:
            sf = json.loads(sf_json)
            ml_feats = sf.get("ml_features", {})
            if not ml_feats:
                continue
            row = {}
            for c in FEATURE_COLS:
                if c in ml_feats:
                    row[c] = ml_feats[c]
                elif c == "catalyst_score_feat":
                    row[c] = float(ml_feats.get("catalyst_score", sf.get("catalyst_score", 5))) / 10.0
                elif c in ("universe_move_30m_pct", "stock_vs_universe_30m"):
                    row[c] = 0.0
                else:
                    row[c] = 0.5
            won = pnl > 0
            row["label_long"]   = 1 if (side == "BUY"  and won) else 0
            row["label_short"]  = 1 if (side == "SELL" and won) else 0
            row["fwd_move_pct"] = float(pnl)
            row["_side"]        = side
            records.append(row)
        except Exception:
            continue

    return records


def train_us_model(records: list[dict], old_models: dict,
                   old_meta: dict, force: bool = False) -> tuple[dict, dict, bool]:
    """
    Train long + short models on US real trades.
    Returns (new_models, new_meta, deployed).
    """
    import pandas as pd

    df = pd.DataFrame(records)
    n  = len(df)

    # Time-series split: train on older trades, test on most recent 20%
    # Never shuffle — financial data has temporal structure
    if n >= 30:
        split_idx = int(n * 0.8)
        train_df  = df.iloc[:split_idx].copy()
        test_df   = df.iloc[split_idx:].copy()
    else:
        train_df = df.copy()
        test_df  = df.copy()
        print(f"  Only {n} trades — using full set for train+eval (no reliable holdout)")

    # Boost train rows 3x (each trade is hard-won real data)
    train_df = pd.concat([train_df] * 3, ignore_index=True)

    new_models  = {}
    new_meta    = {}
    deployed    = False
    old_sharpes = []
    new_sharpes = []

    for direction in ["long", "short"]:
        label_col = f"label_{direction}"
        X_train   = train_df[FEATURE_COLS]
        y_train   = train_df[label_col]
        X_test    = test_df[FEATURE_COLS]
        y_test    = test_df[label_col]

        pos_rate = float(y_train.mean())
        if pos_rate < 0.01 or pos_rate > 0.99:
            print(f"  {direction}: label rate {pos_rate:.2f} — skipping (degenerate)")
            continue

        model = XGBClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            min_child_weight=3, gamma=0.5,
            scale_pos_weight=(1 - pos_rate) / pos_rate,
            eval_metric="logloss", verbosity=0, random_state=42,
        )
        model.fit(X_train, y_train, verbose=False)
        new_models[f"mid_{direction}"] = model  # US VWAP = midday strategy

        # Eval on test
        proba  = model.predict_proba(X_test)[:, 1]
        old_t  = old_meta.get("mid_threshold", 0.40)
        pred   = (proba >= old_t).astype(int)
        fwd    = test_df.loc[pred == 1, "fwd_move_pct"] if pred.sum() > 0 else pd.Series(dtype=float)
        if direction == "short":
            fwd = -fwd
        net_fwd  = fwd - 0.05  # US slippage/commission estimate
        win_rate = float((net_fwd > 0).mean()) if len(net_fwd) > 0 else 0
        sharpe   = (net_fwd.mean() / net_fwd.std() * np.sqrt(252)
                    if len(net_fwd) > 1 and net_fwd.std() > 0 else 0.0)
        precision = precision_score(y_test, pred, zero_division=0)

        print(f"  NEW {direction}: trades={n} signals={pred.sum()} "
              f"win={win_rate:.1%} sharpe={sharpe:.2f} precision={precision:.1%}")

        # Compare with old model if it exists
        old_key   = f"mid_{direction}"
        old_model = old_models.get(old_key)
        if old_model is not None:
            try:
                old_proba  = old_model.predict_proba(X_test)[:, 1]
                old_pred   = (old_proba >= old_t).astype(int)
                old_fwd    = test_df.loc[old_pred == 1, "fwd_move_pct"] if old_pred.sum() > 0 else pd.Series(dtype=float)
                if direction == "short":
                    old_fwd = -old_fwd
                old_net    = old_fwd - 0.05
                old_sharpe = (old_net.mean() / old_net.std() * np.sqrt(252)
                              if len(old_net) > 1 and old_net.std() > 0 else 0.0)
                print(f"  OLD {direction}: sharpe={old_sharpe:.2f}")
                old_sharpes.append(old_sharpe)
                new_sharpes.append(sharpe)
            except Exception:
                old_sharpes.append(-99)
                new_sharpes.append(sharpe)
        else:
            old_sharpes.append(-99)
            new_sharpes.append(sharpe)

        new_meta[direction] = {
            "win_rate": round(win_rate, 3),
            "sharpe":   round(float(sharpe), 3),
            "signals":  int(pred.sum()),
            "precision": round(float(precision), 3),
            "n_trades": n,
        }

    # Deploy decision
    if not new_models:
        print("  No models trained — nothing to deploy")
        return old_models, old_meta, False

    if force or not old_models:
        deployed = True
        print("  DEPLOY: forced or no prior model")
    else:
        avg_imp = np.mean([n - o for n, o in zip(new_sharpes, old_sharpes)]) if old_sharpes else 1.0
        deployed = bool(avg_imp >= MIN_IMPROVEMENT)
        print(f"  Avg sharpe delta: {avg_imp:+.3f} -> {'DEPLOY' if deployed else 'KEEP OLD'}")

    return new_models if deployed else old_models, new_meta, deployed


def run(account: str = "us_trader", force: bool = False):
    model_path = REPO_ROOT / "ml" / f"model_{account}.pkl"
    meta_path  = REPO_ROOT / "ml" / f"model_{account}_meta.json"

    now_et   = datetime.now(ET)
    date_str = now_et.strftime("%Y-%m-%d %H:%M ET")
    print(f"\n{'='*60}")
    print(f"US ML RETRAIN — {date_str} | account={account}")
    print(f"{'='*60}\n")

    # Load existing model + meta
    old_models: dict = {}
    old_meta:   dict = {}
    if model_path.exists():
        with open(model_path, "rb") as f:
            old_models = pickle.load(f)
    if meta_path.exists():
        old_meta = json.loads(meta_path.read_text())

    # Load US trades
    print("Loading US trades from database...")
    records = load_us_trades(account)
    print(f"  {len(records)} closed trades found for account={account}")

    if len(records) < MIN_TRADES:
        print(f"  Below minimum ({MIN_TRADES}) — skipping retrain, keeping existing model")
        return

    # Train
    print(f"\nTraining on {len(records)} US trades...")
    new_models, metrics, deployed = train_us_model(records, old_models, old_meta, force)

    # Save
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with open(model_path, "wb") as f:
        pickle.dump(new_models, f)

    old_mid_t = old_meta.get("mid_threshold", 0.40)
    meta = {
        "trained_at":    now_et.isoformat(),
        "timezone":      "ET",
        "market":        "US",
        "account":       account,
        "model_type":    "dual",
        "n_trades":      len(records),
        "feature_cols":  FEATURE_COLS,
        "threshold":     old_mid_t,
        "open_threshold": old_mid_t,
        "mid_threshold":  old_mid_t,
        "deployed":      deployed,
        "metrics":       metrics,
    }
    meta_path.write_text(json.dumps(meta, indent=2))

    # Journal
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(f"\n---\n## US ML Retrain — {date_str} | account={account}\n")
        f.write(f"Trades used: {len(records)} | Deployed: {'YES' if deployed else 'NO (kept old)'}\n")
        for d, m in metrics.items():
            f.write(f"  {d}: win={m.get('win_rate',0):.1%} sharpe={m.get('sharpe',0):.2f} "
                    f"signals={m.get('signals',0)} precision={m.get('precision',0):.1%}\n")

    print(f"\nModel saved: {model_path.name} | deployed={deployed}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="us_trader")
    ap.add_argument("--force",   action="store_true")
    args = ap.parse_args()
    run(account=args.account, force=args.force)

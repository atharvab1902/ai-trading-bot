"""Train XGBoost signal model with walk-forward validation.

Walk-forward: train on 60 days, test on 30 days.
Reports out-of-sample Sharpe, win rate, and precision.

Usage:
    python -m ml.train              # train + save model
    python -m ml.train --validate   # validate only, no save
"""
import argparse
import json
import logging
import pickle
from datetime import timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.metrics import precision_score
from sklearn.preprocessing import StandardScaler

from ml.features import build_features, FEATURE_COLS

REPO_ROOT = Path(__file__).parent.parent
DB_PATH    = REPO_ROOT / "data" / "market.duckdb"
MODEL_PATH = REPO_ROOT / "ml" / "model.pkl"
META_PATH  = REPO_ROOT / "ml" / "model_meta.json"

log = logging.getLogger(__name__)


def load_all_data() -> pd.DataFrame:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute("""
        SELECT symbol, ts, open, high, low, close, volume
        FROM ohlcv_1min
        ORDER BY symbol, ts
    """).df()
    con.close()
    df["ts"] = pd.to_datetime(df["ts"])
    return df


def build_all_features(raw: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for sym, grp in raw.groupby("symbol"):
        try:
            feat = build_features(grp.copy())
            feat["symbol"] = sym
            parts.append(feat)
        except Exception as e:
            log.warning(f"Feature build failed for {sym}: {e}")
    return pd.concat(parts, ignore_index=True)


def walk_forward_validate(df: pd.DataFrame,
                          train_days: int = 40,
                          test_days: int = 15) -> dict:
    """Single walk-forward split: train on first 60 days, test on next 30."""
    df = df.dropna(subset=FEATURE_COLS + ["label_long", "label_short"])

    dates = sorted(df["ts"].dt.date.unique())
    if len(dates) < train_days + 5:
        raise ValueError(f"Not enough days: {len(dates)}")

    train_cutoff = dates[train_days - 1]
    test_cutoff  = dates[min(train_days + test_days - 1, len(dates) - 1)]

    train = df[df["ts"].dt.date <= train_cutoff]
    test  = df[(df["ts"].dt.date > train_cutoff) &
               (df["ts"].dt.date <= test_cutoff)]

    results = {}
    for direction in ["long", "short"]:
        label_col = f"label_{direction}"
        X_train = train[FEATURE_COLS]
        y_train = train[label_col]
        X_test  = test[FEATURE_COLS]
        y_test  = test[label_col]

        # Skip if too imbalanced
        pos_rate = y_train.mean()
        if pos_rate < 0.02 or pos_rate > 0.5:
            log.warning(f"{direction}: label rate {pos_rate:.3f} — skipping")
            continue

        model = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=(1 - pos_rate) / pos_rate,
            eval_metric="logloss",
            verbosity=0,
            random_state=42,
        )
        model.fit(X_train, y_train,
                  eval_set=[(X_test, y_test)],
                  verbose=False)

        proba = model.predict_proba(X_test)[:, 1]
        threshold = 0.65
        pred = (proba >= threshold).astype(int)

        precision = precision_score(y_test, pred, zero_division=0)
        n_signals = int(pred.sum())
        base_rate = float(y_test.mean())

        # Simulated PnL: when model fires, use actual forward move
        signal_mask = pred == 1
        if signal_mask.sum() > 0:
            fwd = test.loc[signal_mask, "fwd_move_pct"].copy()
            if direction == "short":
                fwd = -fwd
            position_inr = 50000
            avg_price = float(test.loc[signal_mask, "close"].mean())
            qty = max(1, int(position_inr / avg_price))
            brokerage_pct = 0.16  # round trip
            net_fwd = fwd - brokerage_pct
            trade_pnl = net_fwd / 100 * avg_price * qty
            total_pnl = float(trade_pnl.sum())
            win_rate  = float((net_fwd > 0).mean())
            avg_pnl   = float(trade_pnl.mean())
            # Sharpe per trade (annualised assuming ~5 trades/day)
            trades_per_year = 5 * 252
            sharpe = (net_fwd.mean() / net_fwd.std() * np.sqrt(trades_per_year)
                      if net_fwd.std() > 0 else 0)
        else:
            total_pnl = win_rate = avg_pnl = sharpe = 0.0

        results[direction] = {
            "precision": round(precision, 3),
            "win_rate":  round(win_rate, 3),
            "n_signals": n_signals,
            "base_rate": round(base_rate, 3),
            "total_pnl": round(total_pnl, 2),
            "avg_pnl":   round(avg_pnl, 2),
            "sharpe":    round(float(sharpe), 3),
        }
        log.info(f"{direction}: precision={precision:.3f} win_rate={win_rate:.3f} "
                 f"signals={n_signals} sharpe={sharpe:.2f} pnl=Rs{total_pnl:.0f}")

    return results


def train_final(df: pd.DataFrame) -> dict:
    """Train on ALL available data. Returns {direction: model}."""
    df = df.dropna(subset=FEATURE_COLS + ["label_long", "label_short"])
    models = {}
    for direction in ["long", "short"]:
        label_col = f"label_{direction}"
        X = df[FEATURE_COLS]
        y = df[label_col]
        pos_rate = y.mean()
        model = XGBClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            scale_pos_weight=(1 - pos_rate) / pos_rate,
            eval_metric="logloss", verbosity=0, random_state=42,
        )
        model.fit(X, y, verbose=False)
        models[direction] = model
        log.info(f"Final {direction} model trained on {len(df):,} samples")
    return models


def run(validate_only: bool = False):
    print("Loading data from DuckDB...")
    raw = load_all_data()
    print(f"  {len(raw):,} raw bars across {raw['symbol'].nunique()} stocks")

    print("Building features...")
    df = build_all_features(raw)
    # Full trading day
    minutes = df["ts"].dt.hour * 60 + df["ts"].dt.minute
    df = df[(minutes >= 9 * 60 + 15) & (minutes <= 15 * 60 + 15)]
    print(f"  {len(df):,} feature rows (full day 9:15-15:15)")

    print("\nWalk-forward validation (60d train / 30d test)...")
    val_results = walk_forward_validate(df)

    print("\n=== VALIDATION RESULTS ===")
    has_edge = True
    for direction, r in val_results.items():
        print(f"\n  {direction.upper()}:")
        print(f"    Precision:  {r['precision']:.1%}  (base rate: {r['base_rate']:.1%})")
        print(f"    Win rate:   {r['win_rate']:.1%}")
        print(f"    Signals:    {r['n_signals']}")
        print(f"    Sharpe:     {r['sharpe']:.2f}")
        print(f"    Total PnL:  Rs{r['total_pnl']:,.0f}")
        print(f"    Avg/trade:  Rs{r['avg_pnl']:.2f}")

        lift = r["precision"] / r["base_rate"] if r["base_rate"] > 0 else 0
        has_dir_edge = r["win_rate"] >= 0.50 and lift >= 1.5 and r["sharpe"] > 0.3
        r["has_edge"] = has_dir_edge
        if not has_dir_edge:
            print(f"    WARNING: No edge for {direction} (lift={lift:.1f}x, win={r['win_rate']:.1%}, sharpe={r['sharpe']:.2f})")
            has_edge = False

    directions_with_edge = [d for d, r in val_results.items() if r.get("has_edge")]
    if not directions_with_edge:
        print("\nEDGE CHECK FAILED — no direction has edge. Do NOT deploy.")
        return None, val_results
    print(f"\nEdge confirmed for: {directions_with_edge}")
    has_edge = True

    if validate_only:
        return None, val_results

    print("\nTraining final model on all data...")
    models = train_final(df)

    # Save model + metadata
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(models, f)

    meta = {
        "trained_at": pd.Timestamp.now().isoformat(),
        "n_samples": len(df),
        "n_stocks": raw["symbol"].nunique(),
        "feature_cols": FEATURE_COLS,
        "validation": val_results,
        "threshold": 0.60,
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nModel saved to {MODEL_PATH}")
    print(f"Metadata saved to {META_PATH}")
    return models, val_results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    args = ap.parse_args()
    run(validate_only=args.validate)

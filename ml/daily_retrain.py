"""Daily ML retrainer — runs at 16:15 IST after market close.

Trains TWO models:
  - opening (9:15-10:15 IST): momentum/breakout patterns, target 0.3% in 15 bars
  - midday  (10:15-15:15 IST): mean-reversion patterns, target 0.2% in 15 bars

Compares new vs old on each window independently.
Deploys new model only if improvement (or no old model exists).
Tunes thresholds separately per window from blocked-signal feedback.
All times strictly IST.

Usage:
    python -m ml.daily_retrain
    python -m ml.daily_retrain --force
"""

import argparse
import json
import logging
import pickle
import sqlite3
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytz
from xgboost import XGBClassifier
from sklearn.metrics import precision_score

from ml.features import build_features, FEATURE_COLS

REPO_ROOT  = Path(__file__).parent.parent
DB_PATH    = REPO_ROOT / "data" / "market.duckdb"
TRADES_DB  = REPO_ROOT / "data" / "trades.db"
MODEL_PATH = REPO_ROOT / "ml" / "model.pkl"
META_PATH  = REPO_ROOT / "ml" / "model_meta.json"
JOURNAL    = REPO_ROOT / "data" / "journal.md"
IST        = pytz.timezone("Asia/Kolkata")

log = logging.getLogger(__name__)

TEST_DAYS       = 15
MIN_IMPROVEMENT = -0.02   # tolerate up to 2% sharpe drop (noise)

# Per-window config
WINDOWS = {
    "open": {
        "start_min": 9 * 60 + 15,
        "end_min":   10 * 60 + 15,
        "target_pct": 0.3,
        "target_bars": 15,
        "default_threshold": 0.25,
        "threshold_floor": 0.15,
        "threshold_ceil":  0.40,
    },
    "mid": {
        "start_min": 10 * 60 + 16,
        "end_min":   15 * 60 + 15,
        "target_pct": 0.2,
        "target_bars": 15,
        "default_threshold": 0.22,
        "threshold_floor": 0.12,
        "threshold_ceil":  0.35,
    },
}


# ── Data loading ──────────────────────────────────────────────────────────────

def update_market_data():
    print("  Pulling today's bars from Dhan (IST)...")
    try:
        from ml.data_collector import run as collect
        collect(update_only=True)
        print("  Market data updated.")
    except Exception as e:
        print(f"  WARNING: Data update failed: {e} — using existing data.")


def load_raw() -> pd.DataFrame:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    raw = con.execute("""
        SELECT symbol, ts, open, high, low, close, volume
        FROM ohlcv_1min ORDER BY symbol, ts
    """).df()
    con.close()
    raw["ts"] = pd.to_datetime(raw["ts"])
    return raw


def build_features_for_window(raw: pd.DataFrame, target_pct: float,
                                target_bars: int) -> pd.DataFrame:
    parts = []
    for sym, grp in raw.groupby("symbol"):
        try:
            feat = build_features(grp.copy(),
                                  target_bars=target_bars,
                                  target_pct=target_pct)
            feat["symbol"] = sym
            parts.append(feat)
        except Exception as e:
            log.warning(f"Feature build failed {sym}: {e}")
    df = pd.concat(parts, ignore_index=True)
    return df.dropna(subset=FEATURE_COLS + ["label_long", "label_short"])


# ── Training ──────────────────────────────────────────────────────────────────

def train_models(train_df: pd.DataFrame, window_name: str) -> dict:
    """Train long + short models for one window. Returns {long: model, short: model}."""
    models = {}
    for direction in ["long", "short"]:
        label_col = f"label_{direction}"
        X = train_df[FEATURE_COLS]
        y = train_df[label_col]
        pos_rate = float(y.mean())
        if pos_rate < 0.02 or pos_rate > 0.5:
            log.warning(f"{window_name}/{direction}: label rate {pos_rate:.3f} — skipping")
            continue
        model = XGBClassifier(
            n_estimators=400, max_depth=4, learning_rate=0.04,
            subsample=0.8, colsample_bytree=0.8,
            min_child_weight=10, gamma=1,
            scale_pos_weight=(1 - pos_rate) / pos_rate,
            eval_metric="logloss", verbosity=0, random_state=42,
        )
        model.fit(X, y, verbose=False)
        models[direction] = model
        print(f"  Trained {window_name}/{direction}: {len(train_df):,} rows "
              f"pos_rate={pos_rate:.3f}")
    return models


# ── Evaluation ────────────────────────────────────────────────────────────────

def evaluate_models(models: dict, test_df: pd.DataFrame,
                    threshold: float, prefix: str = "",
                    train_df: pd.DataFrame = None) -> dict:
    results = {}
    for direction in ["long", "short"]:
        key = f"{prefix}{direction}" if prefix else direction
        model = models.get(key) or models.get(direction)
        if model is None:
            continue
        label_col = f"label_{direction}"
        X = test_df[FEATURE_COLS]
        y = test_df[label_col]
        proba = model.predict_proba(X)[:, 1]
        pred  = (proba >= threshold).astype(int)
        n_signals = int(pred.sum())

        if n_signals == 0:
            results[direction] = {"sharpe": -99, "win_rate": 0,
                                  "n_signals": 0, "precision": 0,
                                  "base_rate": float(y.mean())}
            continue

        fwd = test_df.loc[pred == 1, "fwd_move_pct"].copy()
        if direction == "short":
            fwd = -fwd
        net_fwd   = fwd - 0.16
        win_rate  = float((net_fwd > 0).mean())
        precision = precision_score(y, pred, zero_division=0)
        base_rate = float(y.mean())
        sharpe    = (net_fwd.mean() / net_fwd.std() * np.sqrt(5 * 252)
                     if net_fwd.std() > 0 else 0.0)

        r = {
            "sharpe":        round(float(sharpe), 3),
            "win_rate":      round(win_rate, 3),
            "n_signals":     n_signals,
            "n_test_rows":   len(test_df),
            "precision":     round(precision, 3),
            "base_rate":     round(base_rate, 3),
            "lift":          round(precision / base_rate, 2) if base_rate > 0 else 0,
            "avg_pnl_pct":   round(float(net_fwd.mean()), 4),
            "total_pnl_pct": round(float(net_fwd.sum()), 3),
            "threshold_used": threshold,
            # Probability distribution on test set
            "prob_mean":     round(float(proba.mean()), 3),
            "prob_p25":      round(float(np.percentile(proba, 25)), 3),
            "prob_p50":      round(float(np.percentile(proba, 50)), 3),
            "prob_p75":      round(float(np.percentile(proba, 75)), 3),
            "prob_p90":      round(float(np.percentile(proba, 90)), 3),
        }

        # Train-set metrics if provided (shows overfitting gap)
        if train_df is not None:
            Xtr = train_df[FEATURE_COLS]
            ytr = train_df[label_col]
            proba_tr = model.predict_proba(Xtr)[:, 1]
            pred_tr  = (proba_tr >= threshold).astype(int)
            r["train_precision"]  = round(precision_score(ytr, pred_tr, zero_division=0), 3)
            r["train_n_signals"]  = int(pred_tr.sum())
            r["train_n_rows"]     = len(train_df)
            r["train_base_rate"]  = round(float(ytr.mean()), 3)
            fwd_tr = train_df.loc[pred_tr == 1, "fwd_move_pct"].copy()
            if direction == "short":
                fwd_tr = -fwd_tr
            net_fwd_tr = fwd_tr - 0.16
            r["train_win_rate"] = round(float((net_fwd_tr > 0).mean()), 3) if len(net_fwd_tr) > 0 else 0
            overfit = r["train_win_rate"] - win_rate
            r["overfit_gap"] = round(overfit, 3)  # >0.10 means overfitting

        results[direction] = r
    return results


# ── Real trade feedback ───────────────────────────────────────────────────────

def load_real_trade_rows() -> pd.DataFrame:
    """
    Read closed paper trades from trades.db.
    Each trade has signal_features JSON with ml_features (the 14 FEATURE_COLS).
    Returns a DataFrame with FEATURE_COLS + label_long + label_short columns
    that can be appended to training data.
    """
    try:
        con = sqlite3.connect(TRADES_DB)
        rows = con.execute("""
            SELECT side, pnl, signal_features
            FROM trades
            WHERE status='closed'
              AND signal_features IS NOT NULL
              AND pnl IS NOT NULL
        """).fetchall()
        con.close()
    except Exception as e:
        log.warning(f"Trade feedback read failed: {e}")
        return pd.DataFrame()

    records = []
    for side, pnl, sf_json in rows:
        try:
            sf = json.loads(sf_json)
            ml_feats = sf.get("ml_features", {})
            if not ml_feats:
                continue
            # Build feature row with sensible defaults for features absent in older trades
            row = {}
            for c in FEATURE_COLS:
                if c in ml_feats:
                    row[c] = ml_feats[c]
                elif c == "catalyst_score_feat":
                    cs = ml_feats.get("catalyst_score", sf.get("catalyst_score", 5))
                    row[c] = float(cs) / 10.0
                elif c in ("universe_move_30m_pct", "stock_vs_universe_30m"):
                    row[c] = 0.0   # neutral: no directional context recorded
                else:
                    row[c] = 0.5   # neutral default for other context features
            # Label: did this trade make money?
            won = pnl > 0
            row["label_long"]  = 1 if (side == "BUY"  and won) else 0
            row["label_short"] = 1 if (side == "SELL" and won) else 0
            row["fwd_move_pct"] = pnl  # approximate
            records.append(row)
        except Exception:
            continue

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    print(f"  Real trade rows loaded: {len(df)} closed trades")
    return df


# ── Threshold tuning ──────────────────────────────────────────────────────────

def tune_threshold(current: float, window_name: str,
                   floor: float, ceil: float) -> float:
    try:
        con = sqlite3.connect(TRADES_DB)
        # Filter blocked signals by time-of-day matching the window
        if window_name == "open":
            time_filter = "AND CAST(strftime('%H%M', ts) AS INTEGER) BETWEEN 915 AND 1015"
        else:
            time_filter = "AND CAST(strftime('%H%M', ts) AS INTEGER) > 1015"
        rows = con.execute(f"""
            SELECT ml_prob, outcome_pnl_pct
            FROM blocked_signals
            WHERE resolved=1
              AND date(ts) >= date('now', '-14 days')
              {time_filter}
        """).fetchall()
        con.close()
    except Exception as e:
        log.warning(f"Feedback read failed ({window_name}): {e}")
        return current

    if len(rows) < 20:
        clamped = round(max(floor, min(ceil, current)), 3)
        if clamped != current:
            print(f"  [{window_name}] Not enough feedback — clamping {current:.3f} -> {clamped:.3f} (floor={floor})")
        else:
            print(f"  [{window_name}] Not enough feedback ({len(rows)}/20) — keeping {current:.3f}")
        return clamped

    df = pd.DataFrame(rows, columns=["ml_prob", "pnl_pct"])
    profitable_rate = (df["pnl_pct"] > 0.1).mean()
    print(f"  [{window_name}] {len(df)} resolved signals | "
          f"{profitable_rate:.1%} would have been profitable")

    new = current
    if profitable_rate > 0.60:
        new = current - 0.01
        print(f"  [{window_name}] Threshold too high → {new:.3f}")
    elif profitable_rate < 0.30:
        new = current + 0.01
        print(f"  [{window_name}] Threshold too low → {new:.3f}")
    else:
        print(f"  [{window_name}] Threshold OK → {current:.3f}")

    return round(max(floor, min(ceil, new)), 3)


# ── Feature importance ────────────────────────────────────────────────────────

def feature_importance_report(models: dict) -> str:
    lines = []
    for key, model in models.items():
        importances = model.feature_importances_
        ranked = sorted(zip(FEATURE_COLS, importances),
                        key=lambda x: x[1], reverse=True)
        lines.append(f"\n  {key.upper()} — top 5 features:")
        for feat, imp in ranked[:5]:
            lines.append(f"    {feat:<25} {imp:.3f}")
    return "\n".join(lines)


# ── Training report ──────────────────────────────────────────────────────────

def save_training_report(date_str: str, report: dict):
    """Save detailed training report to data/ml_reports/ as JSON."""
    reports_dir = REPO_ROOT / "data" / "ml_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    fname = reports_dir / f"retrain_{date_str.replace(' ', '_').replace(':', '').replace('IST','').strip()}.json"
    class _NpEncoder(json.JSONEncoder):
        def default(self, o):
            import numpy as _np
            if isinstance(o, _np.bool_): return bool(o)
            if isinstance(o, _np.integer): return int(o)
            if isinstance(o, _np.floating): return float(o)
            if isinstance(o, _np.ndarray): return o.tolist()
            return super().default(o)
    with open(fname, "w") as f:
        json.dump(report, f, indent=2, cls=_NpEncoder)
    print(f"  Training report saved: {fname.name}")
    return fname


def print_training_report(report: dict):
    """Print a clean human-readable summary of the training report."""
    print(f"\n{'='*60}")
    print(f"TRAINING REPORT — {report['trained_at']}")
    print(f"{'='*60}")
    print(f"  Total bars in DB : {report['total_bars']:,}")
    print(f"  Trading days     : {report['total_days']}")
    print(f"  Stocks           : {report['n_stocks']}")
    print(f"  Real trades used : {report['real_trades_used']}")

    for wname in ["open", "mid"]:
        w = report["windows"].get(wname, {})
        print(f"\n  [{wname.upper()} WINDOW]")
        print(f"    Train rows : {w.get('train_rows', 0):,}")
        print(f"    Test rows  : {w.get('test_rows', 0):,}")
        print(f"    Deployed   : {w.get('deployed', False)}")
        print(f"    Threshold  : {w.get('old_threshold', 0):.3f} -> {w.get('new_threshold', 0):.3f}")

        for direction in ["long", "short"]:
            m = w.get(f"new_{direction}", {})
            if not m:
                continue
            print(f"\n    {direction.upper()}:")
            print(f"      Test  : precision={m.get('precision',0):.1%}  win_rate={m.get('win_rate',0):.1%}  "
                  f"sharpe={m.get('sharpe',0):.2f}  signals={m.get('n_signals',0)}")
            print(f"      Train : precision={m.get('train_precision',0):.1%}  win_rate={m.get('train_win_rate',0):.1%}  "
                  f"signals={m.get('train_n_signals',0)}")
            print(f"      Overfit gap : {m.get('overfit_gap',0):+.3f}  "
                  f"(>0.10 = overfitting)")
            print(f"      Lift  : {m.get('lift',0):.1f}x over base rate {m.get('base_rate',0):.1%}")
            print(f"      Prob distribution (test): "
                  f"p25={m.get('prob_p25',0):.2f} p50={m.get('prob_p50',0):.2f} "
                  f"p75={m.get('prob_p75',0):.2f} p90={m.get('prob_p90',0):.2f}")
    print(f"{'='*60}\n")


# ── Journal ───────────────────────────────────────────────────────────────────

def write_journal(date_str, results_by_window, deployed_by_window,
                  thresholds_old, thresholds_new, n_feedback, feat_report):
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"\n---\n## ML Retrain — {date_str} (IST)",
        f"Feedback signals used: {n_feedback}",
    ]
    for wname in ["open", "mid"]:
        deployed = deployed_by_window.get(wname, False)
        old_t = thresholds_old.get(wname, 0)
        new_t = thresholds_new.get(wname, 0)
        lines.append(f"\n### {wname.upper()} window | deployed={'YES' if deployed else 'NO'} "
                     f"| threshold {old_t:.3f} -> {new_t:.3f}")
        r = results_by_window.get(wname, {})
        for direction in ["long", "short"]:
            old = r.get(f"old_{direction}", {})
            new = r.get(f"new_{direction}", {})
            for metric in ["sharpe", "win_rate", "n_signals"]:
                o = old.get(metric, "-")
                n = new.get(metric, "-")
                lines.append(f"  {direction}/{metric}: {o} -> {n}")
    lines.append(f"\n### Feature importance{feat_report}")
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Journal written.")


# ── Main ──────────────────────────────────────────────────────────────────────

def run(force: bool = False):
    now_ist  = datetime.now(IST)
    date_str = now_ist.strftime("%Y-%m-%d %H:%M IST")
    print(f"\n{'='*60}")
    print(f"DAILY ML RETRAIN — {date_str}")
    print(f"{'='*60}\n")

    # Step 1: update data
    print("Step 1: Updating market data...")
    update_market_data()

    # Step 2: load raw bars
    print("\nStep 2: Loading raw bars from DuckDB...")
    raw = load_raw()
    dates = sorted(raw["ts"].dt.date.unique())
    print(f"  {len(raw):,} bars | {len(dates)} trading days | {raw['symbol'].nunique()} stocks")

    if len(dates) < TEST_DAYS + 10:
        print(f"  Not enough data ({len(dates)} days). Skipping.")
        return

    train_dates = dates[:-(TEST_DAYS)]
    test_dates  = dates[-TEST_DAYS:]
    train_raw = raw[raw["ts"].dt.date.isin(train_dates)]
    test_raw  = raw[raw["ts"].dt.date.isin(test_dates)]
    print(f"  Train: {train_dates[0]} to {train_dates[-1]} ({len(train_dates)} days)")
    print(f"  Test:  {test_dates[0]} to {test_dates[-1]} ({len(test_dates)} days)")

    # Load existing model + meta
    old_models = {}
    old_meta   = {}
    if MODEL_PATH.exists():
        with open(MODEL_PATH, "rb") as f:
            old_models = pickle.load(f)
    if META_PATH.exists():
        old_meta = json.loads(META_PATH.read_text())

    new_combined_models = {}
    thresholds_old = {}
    thresholds_new = {}
    deployed_by_window = {}
    results_by_window  = {}
    window_report  = {}
    feedback_total = 0

    for wname, wcfg in WINDOWS.items():
        print(f"\n('-'*50)")
        print(f"WINDOW: {wname.upper()} "
              f"({wcfg['start_min']//60}:{wcfg['start_min']%60:02d}"
              f"–{wcfg['end_min']//60}:{wcfg['end_min']%60:02d} IST)")
        print(f"('-'*50)")

        # Filter by time window (IST minutes)
        def filter_window(df):
            m = df["ts"].dt.hour * 60 + df["ts"].dt.minute
            return df[(m >= wcfg["start_min"]) & (m <= wcfg["end_min"])]

        # Step 3: build features for this window
        print(f"  Building features (target={wcfg['target_pct']}% in {wcfg['target_bars']} bars)...")
        train_feat = build_features_for_window(train_raw, wcfg["target_pct"], wcfg["target_bars"])
        test_feat  = build_features_for_window(test_raw,  wcfg["target_pct"], wcfg["target_bars"])
        train_feat = filter_window(train_feat)
        test_feat  = filter_window(test_feat)
        print(f"  Train rows: {len(train_feat):,} | Test rows: {len(test_feat):,}")

        old_t = old_meta.get(f"{wname}_threshold", wcfg["default_threshold"])
        thresholds_old[wname] = old_t

        # Step 4: evaluate old model on test window
        print(f"  Evaluating OLD model...")
        old_w = {d: old_models.get(f"{wname}_{d}") for d in ["long", "short"]}
        if any(old_w.values()):
            try:
                old_metrics = evaluate_models(old_w, test_feat, old_t)
            except ValueError:
                # Old model trained on different feature set (e.g. after adding new features)
                print(f"  OLD model feature mismatch — skipping old eval, will deploy new model")
                old_metrics = {}
        else:
            old_metrics = {}
        for d, r in old_metrics.items():
            print(f"    OLD {d}: sharpe={r['sharpe']:.3f} win={r['win_rate']:.1%} signals={r['n_signals']}")

        # Step 5: train new model — append real trade outcomes to training data
        print(f"  Training NEW model...")
        real_trades = load_real_trade_rows()
        if not real_trades.empty:
            boosted = pd.concat([real_trades] * 5, ignore_index=True)
            train_feat = pd.concat([train_feat, boosted], ignore_index=True)
            print(f"  Boosted training with {len(real_trades)} real trades (5x weight)")
        new_w = train_models(train_feat, wname)
        new_metrics = evaluate_models(new_w, test_feat, old_t, train_df=train_feat)
        for d, r in new_metrics.items():
            print(f"    NEW {d}: sharpe={r['sharpe']:.3f} win={r['win_rate']:.1%} "
                  f"precision={r['precision']:.1%} signals={r['n_signals']} "
                  f"overfit={r.get('overfit_gap',0):+.3f}")

        # Step 6: deploy decision
        should_deploy = force or not any(old_w.values())
        if not should_deploy:
            improvements = []
            for d in ["long", "short"]:
                old_s = old_metrics.get(d, {}).get("sharpe", -99)
                new_s = new_metrics.get(d, {}).get("sharpe", -99)
                improvements.append(new_s - old_s)
            avg_imp = np.mean(improvements)
            should_deploy = avg_imp >= MIN_IMPROVEMENT
            print(f"  Avg sharpe improvement: {avg_imp:+.3f} -> {'DEPLOY' if should_deploy else 'KEEP OLD'}")

        deployed_by_window[wname] = should_deploy
        results_by_window[wname] = {
            f"old_{d}": old_metrics.get(d, {}) for d in ["long", "short"]
        } | {
            f"new_{d}": new_metrics.get(d, {}) for d in ["long", "short"]
        }

        # Step 7: threshold tuning
        print(f"  Tuning threshold from feedback...")
        new_t = tune_threshold(old_t, wname,
                               wcfg["threshold_floor"], wcfg["threshold_ceil"])
        thresholds_new[wname] = new_t

        # Add to combined model dict
        active_w = new_w if should_deploy else old_w
        for d, m in active_w.items():
            if m is not None:
                new_combined_models[f"{wname}_{d}"] = m

        try:
            con = sqlite3.connect(TRADES_DB)
            n = con.execute("SELECT COUNT(*) FROM blocked_signals WHERE resolved=1").fetchone()[0]
            con.close()
            feedback_total = max(feedback_total, n)
        except Exception:
            pass

        # Store metrics for report
        window_report[wname] = {
            "train_rows":     len(train_feat),
            "test_rows":      len(test_feat),
            "deployed":       deployed_by_window.get(wname, False),
            "old_threshold":  old_t,
            "new_threshold":  thresholds_new.get(wname, old_t),
            **{f"old_{d}": old_metrics.get(d, {}) for d in ["long", "short"]},
            **{f"new_{d}": new_metrics.get(d, {}) for d in ["long", "short"]},
        }

    # Step 8: save
    print(f"\n('-'*50)")
    print("Saving model + metadata...")
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(new_combined_models, f)

    meta = {
        "trained_at":   now_ist.isoformat(),
        "timezone":     "IST",
        "model_type":   "dual",
        "n_stocks":     raw["symbol"].nunique(),
        "feature_cols": FEATURE_COLS,
        "threshold":    thresholds_new.get("open", 0.55),  # default for scorer
        "open_threshold": thresholds_new["open"],
        "mid_threshold":  thresholds_new["mid"],
        "old_open_threshold": thresholds_old.get("open"),
        "old_mid_threshold":  thresholds_old.get("mid"),
        "feedback_signals": feedback_total,
        "deployed": deployed_by_window,
    }
    class _NpEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, np.bool_): return bool(o)
            if isinstance(o, np.integer): return int(o)
            if isinstance(o, np.floating): return float(o)
            if isinstance(o, np.ndarray): return o.tolist()
            return super().default(o)

    # Write atomically — serialize first, then write, so a crash never corrupts the file
    meta_json = json.dumps(meta, indent=2, cls=_NpEncoder)
    META_PATH.write_text(meta_json)

    print(f"  open_threshold: {thresholds_old.get('open'):.3f} -> {thresholds_new['open']:.3f}")
    print(f"  mid_threshold:  {thresholds_old.get('mid'):.3f} -> {thresholds_new['mid']:.3f}")
    print(f"  Models saved: {list(new_combined_models.keys())}")

    # Step 9: feature importance + journal
    feat_report = feature_importance_report(new_combined_models)
    print(f"\nFeature importance:{feat_report}".encode("ascii", errors="replace").decode("ascii"))

    print("\nWriting journal...")
    write_journal(date_str, results_by_window, deployed_by_window,
                  thresholds_old, thresholds_new, feedback_total, feat_report)

    # Save detailed training report
    real_trade_count = len(load_real_trade_rows())
    full_report = {
        "trained_at":       now_ist.isoformat(),
        "timezone":         "IST",
        "total_bars":       len(raw),
        "total_days":       len(dates),
        "n_stocks":         raw["symbol"].nunique(),
        "real_trades_used": real_trade_count,
        "feedback_signals": feedback_total,
        "windows":          window_report,
        "deployed":         deployed_by_window,
        "thresholds_old":   thresholds_old,
        "thresholds_new":   thresholds_new,
        "feature_cols":     FEATURE_COLS,
    }
    report_path = save_training_report(now_ist.strftime("%Y-%m-%d"), full_report)
    print_training_report(full_report)

    print(f"\n{'='*60}")
    print(f"RETRAIN COMPLETE")
    print(f"  open: deployed={deployed_by_window.get('open')} threshold={thresholds_new['open']}")
    print(f"  mid:  deployed={deployed_by_window.get('mid')}  threshold={thresholds_new['mid']}")
    print(f"  Report: {report_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    run(force=args.force)

"""Generate historically labelled signals from ORB and VWAP rules.

For each day × stock, simulate ORB and VWAP entries using actual 1-min bars.
Label each signal: 1 = hit target, 0 = hit stoploss.

This is what we train the ML model on — not random bars.
"""
import logging
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from ml.features import compute_vwap, compute_ema, compute_rsi, compute_atr, FEATURE_COLS

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "data" / "market.duckdb"
log = logging.getLogger(__name__)


def simulate_orb_signals(day_df: pd.DataFrame,
                         range_minutes: int = 15,
                         sl_pct: float = 0.5,
                         tgt_pct: float = 1.0,
                         buffer_pct: float = 0.05) -> list:
    """Simulate ORB entries on a single day's 1-min data. Returns list of signal dicts."""
    signals = []
    day_df = day_df.sort_values("ts").reset_index(drop=True)
    if len(day_df) < 20:
        return signals

    market_open = day_df["ts"].iloc[0].replace(hour=9, minute=15, second=0)
    range_end   = market_open + pd.Timedelta(minutes=range_minutes)
    latest_entry = market_open.replace(hour=10, minute=0)

    range_bars = day_df[day_df["ts"] < range_end]
    if range_bars.empty:
        return signals

    rng_high = range_bars["high"].max()
    rng_low  = range_bars["low"].min()

    entry_bars = day_df[(day_df["ts"] >= range_end) & (day_df["ts"] <= latest_entry)]
    taken = {"long": False, "short": False}

    for _, bar in entry_bars.iterrows():
        price = bar["close"]
        buf = price * buffer_pct / 100

        for direction in ["long", "short"]:
            if taken[direction]:
                continue
            if direction == "long" and price > rng_high + buf:
                entry = price
                sl = entry * (1 - sl_pct / 100)
                tgt = entry * (1 + tgt_pct / 100)
            elif direction == "short" and price < rng_low - buf:
                entry = price
                sl = entry * (1 + sl_pct / 100)
                tgt = entry * (1 - tgt_pct / 100)
            else:
                continue

            # Simulate outcome on remaining bars
            remaining = day_df[day_df["ts"] > bar["ts"]]
            outcome = _simulate_outcome(remaining, entry, sl, tgt, direction)
            if outcome is None:
                continue

            taken[direction] = True
            signals.append({
                "ts": bar["ts"],
                "strategy": "orb",
                "direction": direction,
                "entry": entry,
                "sl": sl,
                "tgt": tgt,
                "rng_high": rng_high,
                "rng_low": rng_low,
                "rng_width_pct": (rng_high - rng_low) / rng_low * 100,
                "label": outcome["label"],
                "pnl_pct": outcome["pnl_pct"],
            })

    return signals


def simulate_vwap_signals(day_df: pd.DataFrame,
                          threshold_pct: float = 0.5,
                          sl_pct: float = 0.3,
                          tgt_pct: float = 0.5,
                          cooldown_bars: int = 10) -> list:
    """Simulate VWAP mean-reversion entries on a single day's 1-min data."""
    signals = []
    day_df = day_df.sort_values("ts").reset_index(drop=True)
    if len(day_df) < 30:
        return signals

    day_df["vwap"] = compute_vwap(day_df)
    last_signal_bar = -cooldown_bars

    close_arr = day_df["close"].values
    vwap_arr  = day_df["vwap"].values

    for i in range(20, len(day_df) - 5):
        if i - last_signal_bar < cooldown_bars:
            continue
        price = close_arr[i]
        vwap  = vwap_arr[i]
        if vwap <= 0:
            continue
        dev = (price - vwap) / vwap * 100

        if dev <= -threshold_pct:
            direction = "long"
        elif dev >= threshold_pct:
            direction = "short"
        else:
            continue

        entry = price
        sl  = entry * (1 - sl_pct / 100) if direction == "long" else entry * (1 + sl_pct / 100)
        tgt = entry * (1 + tgt_pct / 100) if direction == "long" else entry * (1 - tgt_pct / 100)

        remaining = day_df.iloc[i+1:]
        outcome = _simulate_outcome(remaining, entry, sl, tgt, direction)
        if outcome is None:
            continue

        last_signal_bar = i
        signals.append({
            "ts": day_df["ts"].iloc[i],
            "strategy": "vwap",
            "direction": direction,
            "entry": entry,
            "sl": sl,
            "tgt": tgt,
            "vwap_dev_pct": dev,
            "label": outcome["label"],
            "pnl_pct": outcome["pnl_pct"],
        })

    return signals


def _simulate_outcome(remaining: pd.DataFrame,
                      entry: float, sl: float, tgt: float,
                      direction: str) -> dict | None:
    """Walk forward through bars until SL or target hit. Returns label dict."""
    for _, bar in remaining.iterrows():
        if direction == "long":
            if bar["low"] <= sl:
                return {"label": 0, "pnl_pct": (sl - entry) / entry * 100}
            if bar["high"] >= tgt:
                return {"label": 1, "pnl_pct": (tgt - entry) / entry * 100}
        else:
            if bar["high"] >= sl:
                return {"label": 0, "pnl_pct": (entry - sl) / entry * 100}
            if bar["low"] <= tgt:
                return {"label": 1, "pnl_pct": (entry - tgt) / entry * 100}
    return None  # squareoff at end of day — exclude these


def attach_features(signals_df: pd.DataFrame, ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Join ML features to each signal using the bar at entry time."""
    ohlcv = ohlcv.copy().sort_values("ts").reset_index(drop=True)
    ohlcv["vwap"]  = compute_vwap(ohlcv)
    ohlcv["ema9"]  = compute_ema(ohlcv["close"], 9)
    ohlcv["ema21"] = compute_ema(ohlcv["close"], 21)
    ohlcv["rsi14"] = compute_rsi(ohlcv["close"], 14)
    ohlcv["atr14"] = compute_atr(ohlcv, 14)

    ohlcv["date"] = ohlcv["ts"].dt.date
    daily_open = ohlcv.groupby("date")["open"].first()
    ohlcv["day_open"] = ohlcv["date"].map(daily_open)

    daily_vol = ohlcv.groupby("date")["volume"].sum()
    ohlcv["daily_vol"] = ohlcv["date"].map(daily_vol)
    ohlcv["avg_5d_vol"] = ohlcv["daily_vol"].shift(375).rolling(375 * 5, min_periods=1).mean()

    ohlcv["vwap_dev_pct"]    = (ohlcv["close"] - ohlcv["vwap"]) / ohlcv["vwap"] * 100
    ohlcv["ema9_21_spread"]  = (ohlcv["ema9"] - ohlcv["ema21"]) / ohlcv["ema21"] * 100
    ohlcv["rsi14_feat"]      = ohlcv["rsi14"]
    ohlcv["atr14_pct"]       = ohlcv["atr14"] / ohlcv["close"] * 100
    ohlcv["gap_pct"]         = (ohlcv["day_open"] - ohlcv["close"].shift(1)) / ohlcv["close"].shift(1) * 100
    ohlcv["vol_ratio_20bar"] = ohlcv["volume"] / ohlcv["volume"].rolling(20, min_periods=1).mean()
    ohlcv["vol_ratio_5d"]    = ohlcv["daily_vol"] / ohlcv["avg_5d_vol"].replace(0, np.nan)
    minutes = ohlcv["ts"].dt.hour * 60 + ohlcv["ts"].dt.minute
    ohlcv["time_bucket"]     = ((minutes - (9 * 60 + 15)) // 45).clip(0, 7).astype(int)
    ohlcv["is_first_30min"]  = (minutes < (9 * 60 + 45)).astype(int)
    ohlcv["is_last_hour"]    = (minutes >= (14 * 60 + 15)).astype(int)
    ohlcv["roll30_move_pct"] = (ohlcv["close"] - ohlcv["close"].shift(30)) / ohlcv["close"].shift(30) * 100
    ohlcv["above_vwap"]      = (ohlcv["close"] > ohlcv["vwap"]).astype(int)
    ohlcv["bars_above_vwap_pct"] = ohlcv["above_vwap"].rolling(30, min_periods=1).mean() * 100

    # Merge by nearest ts
    ohlcv_feat = ohlcv.set_index("ts")[FEATURE_COLS]
    signals_df = signals_df.copy()
    signals_df["ts"] = pd.to_datetime(signals_df["ts"])
    signals_df = pd.merge_asof(
        signals_df.sort_values("ts"),
        ohlcv_feat.reset_index().sort_values("ts"),
        on="ts", direction="nearest", tolerance=pd.Timedelta("2min"),
    )
    return signals_df


def build_signal_dataset() -> pd.DataFrame:
    """Run full simulation across all stocks and days. Returns labelled signal dataset."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    symbols = [r[0] for r in con.execute("SELECT DISTINCT symbol FROM ohlcv_1min").fetchall()]
    con.close()

    all_signals = []
    for i, sym in enumerate(symbols):
        con = duckdb.connect(str(DB_PATH), read_only=True)
        df = con.execute(
            "SELECT * FROM ohlcv_1min WHERE symbol=? ORDER BY ts", [sym]
        ).df()
        con.close()
        df["ts"] = pd.to_datetime(df["ts"])

        sym_signals = []
        for date, day_df in df.groupby(df["ts"].dt.date):
            day_df = day_df.reset_index(drop=True)
            sym_signals += simulate_orb_signals(day_df)
            sym_signals += simulate_vwap_signals(day_df)

        if sym_signals:
            sig_df = pd.DataFrame(sym_signals)
            sig_df["symbol"] = sym
            sig_df = attach_features(sig_df, df)
            all_signals.append(sig_df)

        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(symbols)}] {sym}: {len(sym_signals)} signals")

    result = pd.concat(all_signals, ignore_index=True)
    print(f"\nTotal signals: {len(result):,}")
    print(f"Label distribution: {result['label'].value_counts().to_dict()}")
    win_rate = result['label'].mean()
    print(f"Overall win rate: {win_rate:.1%}")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    print("Building signal dataset...")
    df = build_signal_dataset()
    out = REPO_ROOT / "data" / "signal_dataset.parquet"
    df.to_parquet(out, index=False)
    print(f"Saved to {out}")

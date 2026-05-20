"""Feature engineering for ML signal model.

Takes raw 1-min OHLCV bars and produces a feature matrix ready for XGBoost.

Features per bar:
  Price-based:   vwap_dev_pct, ema9_21_spread, rsi14, atr14_pct, gap_pct
  Volume-based:  vol_ratio_5d, vol_ratio_20bar
  Time:          time_bucket (0-7), is_first_30min, is_last_hour
  Regime:        rolling_30m_move_pct, bars_above_vwap_pct
  Target:        move_30m_pct (label: did price move >= threshold in next 30 bars?)
"""

import numpy as np
import pandas as pd


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    """Intraday VWAP — resets each day."""
    df = df.copy()
    df["date"] = df["ts"].dt.date
    df["tp"] = (df["high"] + df["low"] + df["close"]) / 3
    df["tp_vol"] = df["tp"] * df["volume"]
    df["cum_tp_vol"] = df.groupby("date")["tp_vol"].cumsum()
    df["cum_vol"] = df.groupby("date")["volume"].cumsum()
    vwap = df["cum_tp_vol"] / df["cum_vol"].replace(0, np.nan)
    return vwap


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"]  - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def time_bucket(ts: pd.Series) -> pd.Series:
    """Divide trading day into 8 buckets of ~45 min each."""
    minutes = ts.dt.hour * 60 + ts.dt.minute - (9 * 60 + 15)
    return (minutes // 45).clip(0, 7).astype(int)


def build_features(df: pd.DataFrame, target_bars: int = 30,
                   target_pct: float = 0.7) -> pd.DataFrame:
    """
    df: must have columns [symbol, ts, open, high, low, close, volume]
        sorted by ts ascending, single symbol.
    Returns feature dataframe with label columns added.
    """
    df = df.copy().sort_values("ts").reset_index(drop=True)

    # ── Core indicators ──────────────────────────────────────────────────
    df["vwap"] = compute_vwap(df)
    df["ema9"]  = compute_ema(df["close"], 9)
    df["ema21"] = compute_ema(df["close"], 21)
    df["rsi14"] = compute_rsi(df["close"], 14)
    df["atr14"] = compute_atr(df, 14)

    # Daily open for gap calc (first bar of each day)
    df["date"] = df["ts"].dt.date
    daily_open = df.groupby("date")["open"].first().rename("day_open")
    df = df.join(daily_open, on="date")

    # 5-day avg daily volume for vol_ratio
    daily_vol = df.groupby("date")["volume"].sum().rename("daily_vol")
    df = df.join(daily_vol, on="date")
    df["avg_5d_vol"] = df.groupby("symbol")["daily_vol"].transform(
        lambda x: x.shift(1).rolling(5, min_periods=1).mean()
    )

    # ── Feature columns ──────────────────────────────────────────────────
    df["vwap_dev_pct"]    = (df["close"] - df["vwap"]) / df["vwap"] * 100
    df["ema9_21_spread"]  = (df["ema9"]  - df["ema21"]) / df["ema21"] * 100
    df["rsi14_feat"]      = df["rsi14"]
    df["atr14_pct"]       = df["atr14"] / df["close"] * 100
    df["gap_pct"]         = (df["day_open"] - df["close"].shift(1)) / df["close"].shift(1) * 100
    df["vol_surge_5d"]    = df["daily_vol"] / df["avg_5d_vol"].replace(0, np.nan)
    df["mom_30m_pct"]     = (df["close"] - df["close"].shift(30)) / df["close"].shift(30) * 100
    df["mom_15m_pct"]     = (df["close"] - df["close"].shift(15)) / df["close"].shift(15) * 100
    df["vol_ratio_5m"]    = df["volume"] / df["volume"].rolling(5, min_periods=1).mean()
    df["time_bucket"]     = time_bucket(df["ts"])
    df["is_first_30min"]  = ((df["ts"].dt.hour * 60 + df["ts"].dt.minute) < (9 * 60 + 45)).astype(int)
    df["is_last_hour"]    = ((df["ts"].dt.hour * 60 + df["ts"].dt.minute) >= (14 * 60 + 15)).astype(int)

    # Opening range width (first 15 min high-low as % of ATR)
    df["date"] = df["ts"].dt.date
    orb_end = df["ts"].apply(lambda t: t.replace(hour=9, minute=30, second=0))
    orb_mask = df["ts"] < orb_end
    orb_high = df[orb_mask].groupby("date")["high"].max()
    orb_low  = df[orb_mask].groupby("date")["low"].min()
    df["orb_high"] = df["date"].map(orb_high)
    df["orb_low"]  = df["date"].map(orb_low)
    df["orb_width_pct"] = (df["orb_high"] - df["orb_low"]) / df["close"] * 100

    # % bars above VWAP in last 30 bars — trend strength
    df["above_vwap"] = (df["close"] > df["vwap"]).astype(int)
    df["bars_above_vwap_pct"] = df["above_vwap"].rolling(30, min_periods=1).mean() * 100

    # Context features — stubbed here, injected with real values at score time
    df["sym_win_rate_10"] = 0.5
    df["vix_level"] = 0.5
    df["universe_move_30m_pct"] = 0.0
    df["stock_vs_universe_30m"] = 0.0
    df["catalyst_score_feat"] = 0.5

    # ── Labels ───────────────────────────────────────────────────────────
    future_close = df["close"].shift(-target_bars)
    fwd_move = (future_close - df["close"]) / df["close"] * 100

    # Zero out cross-day forward leakage
    fwd_move[df["date"] != df["date"].shift(-target_bars)] = np.nan
    df["label_long"]  = (fwd_move >=  target_pct).astype(int)
    df["label_short"] = (fwd_move <= -target_pct).astype(int)
    df["fwd_move_pct"] = fwd_move

    return df


FEATURE_COLS = [
    # Strongest signals from data analysis
    "gap_pct",           # gap vs prev close — catalyst indicator
    "vol_surge_5d",      # today's volume vs 5-day avg — unusual activity
    "mom_30m_pct",       # 30-min momentum — trending or mean-reverting
    "mom_15m_pct",       # 15-min momentum
    "vol_ratio_5m",      # 5-bar volume surge — immediate buying pressure
    # Supporting features
    "vwap_dev_pct",      # deviation from fair price
    "ema9_21_spread",    # trend direction
    "rsi14_feat",        # overbought/oversold
    "atr14_pct",         # volatility of this stock today
    "orb_width_pct",     # opening range width vs ATR — quality of setup
    # Time context
    "time_bucket",       # 0=open, 7=close — strongest alpha at open
    "is_first_30min",    # first 30 min has 3x more movement
    "is_last_hour",      # closing hour has different dynamics
    # Sector momentum proxy
    "bars_above_vwap_pct",  # % time above VWAP — trend strength
    # Context features (real values injected at score time; 0.5 default for historical bars)
    "sym_win_rate_10",   # rolling win rate of last 10 trades for this symbol
    "vix_level",         # India VIX normalized (vix/30.0, capped at 1.0)
    # Directional market context (injected at score time; 0.0 default for historical bars)
    "universe_move_30m_pct",  # avg 30m move across tracked universe (market direction)
    "stock_vs_universe_30m",  # this stock's 30m minus universe avg (relative strength)
    "catalyst_score_feat",    # normalized catalyst score from scanner (0-1)
]

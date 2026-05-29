"""Real-time ML scorer for the executor hot path.

Loads the trained XGBoost model once at startup.
Scores feature vectors in < 1ms per call.
"""
import json
import logging
import pickle
from datetime import datetime, date
from pathlib import Path

import numpy as np
import pandas as pd
import pytz

from ml.features import compute_vwap, compute_ema, compute_rsi, compute_atr, FEATURE_COLS

REPO_ROOT   = Path(__file__).parent.parent
MODEL_PATH  = REPO_ROOT / "ml" / "model.pkl"
META_PATH   = REPO_ROOT / "ml" / "model_meta.json"
IST         = pytz.timezone("Asia/Kolkata")

def _bars_cache_path() -> Path:
    today = datetime.now(IST).strftime("%Y%m%d")
    return REPO_ROOT / "data" / f"scorer_bars_{today}.json"

log = logging.getLogger(__name__)


class MLScorer:
    """
    Loaded once by the executor at startup.
    Maintains per-stock rolling feature state (last 30 bars).
    """

    def __init__(self):
        self.models = {}
        self.threshold      = 0.55
        self.open_threshold = 0.55
        self.mid_threshold  = 0.45
        self.model_type     = "single"
        self._bars: dict = {}
        self._loaded = False
        self._last_meta_check = 0
        self._last_bars_save = 0
        self._win_rate_cache: dict = {}   # {symbol: (rate, fetch_ts)}
        self._vix_cache: tuple = (0.5, 0) # (vix_level, fetch_ts)
        self._vol_baseline: dict = {}     # {symbol: {date_str: total_volume}}
        self._load()
        self._load_bars()
        self._load_vol_baseline()

    def _load(self):
        if not MODEL_PATH.exists():
            log.warning("ML model not found — scorer will pass all signals through")
            return
        try:
            with open(MODEL_PATH, "rb") as f:
                self.models = pickle.load(f)
            with open(META_PATH) as f:
                meta = json.load(f)
            self.threshold     = meta.get("threshold", 0.55)
            self.open_threshold = meta.get("open_threshold", self.threshold)
            self.mid_threshold  = meta.get("mid_threshold", self.threshold - 0.10)
            self.model_type     = meta.get("model_type", "single")
            self._loaded = True
            log.info(f"ML model loaded | type={self.model_type} "
                     f"open_threshold={self.open_threshold} mid_threshold={self.mid_threshold} "
                     f"trained={meta.get('trained_at','?')[:10]}")
        except Exception as e:
            log.error(f"ML model load failed: {e} — passing all signals through")

    def update(self, symbol: str, bar: dict):
        """Feed a new 1-min bar. Call every loop tick."""
        buf = self._bars.setdefault(symbol, [])
        buf.append(bar)
        if len(buf) > 60:   # keep last 60 bars (1 hour)
            buf.pop(0)
        # Force save every 10th bar per symbol to ensure state is never too stale
        self._save_bars(force=(len(buf) % 10 == 0))

    def _load_bars(self):
        path = _bars_cache_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            # Parse ts strings back to datetime
            restored = {}
            for sym, bars in data.items():
                restored[sym] = [
                    {**b, "ts": datetime.fromisoformat(b["ts"])}
                    for b in bars
                ]
            self._bars = restored
            total = sum(len(v) for v in restored.values())
            log.info(f"ML bar cache restored: {len(restored)} symbols, {total} bars")
        except Exception as e:
            log.warning(f"ML bar cache load failed: {e}")

    def _save_bars(self, force: bool = False):
        import time
        now = time.time()
        if not force and now - self._last_bars_save < 30:  # save at most every 30 seconds
            return
        self._last_bars_save = now
        try:
            path = _bars_cache_path()
            # Convert bar dicts — ensure ts is serializable
            serializable = {}
            for sym, bars in self._bars.items():
                serializable[sym] = [
                    {**b, "ts": b["ts"].isoformat() if hasattr(b["ts"], "isoformat") else str(b["ts"])}
                    for b in bars
                ]
            path.write_text(json.dumps(serializable))
        except Exception as e:
            log.warning(f"ML bar cache save failed: {e}")
        self._save_vol_baseline()

    def _load_vol_baseline(self):
        path = REPO_ROOT / "data" / "vol_baseline.json"
        if not path.exists():
            return
        try:
            self._vol_baseline = json.loads(path.read_text())
        except Exception as e:
            log.warning(f"vol_baseline load failed: {e}")

    def _save_vol_baseline(self):
        """Persist daily total volumes so vol_surge_5d can be computed across sessions."""
        if not self._bars:
            return
        try:
            for sym, bars in self._bars.items():
                if not bars:
                    continue
                today_date = bars[-1]["ts"].date() if hasattr(bars[-1]["ts"], "date") else None
                if today_date is None:
                    continue
                today_vol = sum(b.get("volume", 0) for b in bars if
                                (b["ts"].date() if hasattr(b["ts"], "date") else None) == today_date)
                today_str = str(today_date)
                sym_hist = self._vol_baseline.setdefault(sym, {})
                sym_hist[today_str] = int(today_vol)
                # Keep only the last 10 calendar days per symbol
                if len(sym_hist) > 10:
                    del sym_hist[sorted(sym_hist.keys())[0]]
            (REPO_ROOT / "data" / "vol_baseline.json").write_text(
                json.dumps(self._vol_baseline, indent=2)
            )
        except Exception as e:
            log.warning(f"vol_baseline save failed: {e}")

    def _reload_threshold(self):
        """Re-read all thresholds from model_meta.json every 60 seconds."""
        import time
        now = time.time()
        if now - self._last_meta_check < 60:
            return
        self._last_meta_check = now
        try:
            if META_PATH.exists():
                meta = json.load(open(META_PATH))
                new_open = meta.get("open_threshold", self.open_threshold)
                new_mid  = meta.get("mid_threshold",  self.mid_threshold)
                new_t    = meta.get("threshold",       self.threshold)
                changed = []
                if new_open != self.open_threshold:
                    changed.append(f"open {self.open_threshold:.3f}->{new_open:.3f}")
                    self.open_threshold = new_open
                if new_mid != self.mid_threshold:
                    changed.append(f"mid {self.mid_threshold:.3f}->{new_mid:.3f}")
                    self.mid_threshold = new_mid
                self.threshold = new_t
                if changed:
                    log.info(f"THRESHOLD UPDATED: {' | '.join(changed)}")
        except Exception:
            pass

    def _get_sym_win_rate(self, symbol: str) -> float:
        """Rolling win rate of last 10 closed trades for this symbol. Cached 5 min."""
        import time as _time
        now = _time.time()
        cached = self._win_rate_cache.get(symbol)
        if cached and now - cached[1] < 300:
            return cached[0]
        try:
            import sqlite3 as _sqlite3
            con = _sqlite3.connect(str(REPO_ROOT / "data" / "trades.db"))
            rows = con.execute(
                "SELECT pnl FROM trades WHERE symbol=? AND status='closed' "
                "AND pnl IS NOT NULL ORDER BY ts DESC LIMIT 10",
                (symbol,)
            ).fetchall()
            con.close()
            rate = sum(1 for r in rows if r[0] > 0) / len(rows) if len(rows) >= 3 else 0.5
        except Exception:
            rate = 0.5
        self._win_rate_cache[symbol] = (rate, now)
        return rate

    def _get_vix_level(self) -> float:
        """Normalized India VIX from market_context.json. Cached 5 min."""
        import time as _time
        now = _time.time()
        if now - self._vix_cache[1] < 300:
            return self._vix_cache[0]
        try:
            ctx_path = REPO_ROOT / "data" / "market_context.json"
            if ctx_path.exists():
                ctx = json.loads(ctx_path.read_text())
                vix = ctx.get("vix")
                if vix:
                    level = min(1.0, float(vix) / 30.0)
                    self._vix_cache = (level, now)
                    return level
        except Exception:
            pass
        return self._vix_cache[0]

    def _get_universe_move_30m(self, exclude: str = None) -> float:
        """Avg 30m price move across all tracked stocks except the scored symbol."""
        moves = []
        for sym, bars in self._bars.items():
            if sym == exclude or len(bars) < 31:
                continue
            try:
                cur  = bars[-1]["close"]
                past = bars[-31]["close"]
                if past > 0:
                    moves.append((cur - past) / past * 100)
            except (KeyError, IndexError):
                continue
        return float(np.mean(moves)) if moves else 0.0

    def _get_stock_move_30m(self, symbol: str) -> float:
        """30m price move for a specific symbol from bar buffer."""
        bars = self._bars.get(symbol, [])
        if len(bars) < 31:
            return 0.0
        try:
            cur  = bars[-1]["close"]
            past = bars[-31]["close"]
            return (cur - past) / past * 100 if past > 0 else 0.0
        except (KeyError, IndexError):
            return 0.0

    def score(self, symbol: str, direction: str,
              catalyst_score: int = 5) -> tuple[float, bool, dict]:
        """
        Returns (probability, should_trade, feature_vector).
        feature_vector is a dict of all 14 feature values — save with the trade for retraining.
        direction: 'long' or 'short'
        catalyst_score: 0-10 from morning scanner
        """
        self._reload_threshold()
        if not self._loaded:
            return 0.5, True, {}

        # Pick model and threshold based on time of day
        now_ist = datetime.now(IST)
        ist_minutes = now_ist.hour * 60 + now_ist.minute
        is_opening = (9 * 60 + 15) <= ist_minutes <= (10 * 60 + 15)
        window = "open" if is_opening else "mid"

        if self.model_type == "dual":
            model = self.models.get(f"{window}_{direction}")
            base_threshold = self.open_threshold if is_opening else self.mid_threshold
        else:
            model = self.models.get(direction)
            base_threshold = self.threshold

        if model is None:
            return 0.5, True, {}

        buf = self._bars.get(symbol, [])
        if len(buf) < 20:
            return 0.5, False, {}

        feats = self._build_features(symbol, buf)
        if feats is None:
            return 0.5, False, {}

        # Inject real context features (override the 0.5/0.0 stubs from _build_features)
        feats = feats.copy()
        feats.loc[feats.index[0], "sym_win_rate_10"] = self._get_sym_win_rate(symbol)
        feats.loc[feats.index[0], "vix_level"] = self._get_vix_level()
        univ_move = self._get_universe_move_30m(exclude=symbol)
        stock_move = self._get_stock_move_30m(symbol)
        feats.loc[feats.index[0], "universe_move_30m_pct"] = univ_move
        feats.loc[feats.index[0], "stock_vs_universe_30m"] = stock_move - univ_move
        feats.loc[feats.index[0], "catalyst_score_feat"] = catalyst_score / 10.0

        try:
            proba = float(model.predict_proba(feats)[0][1])
        except Exception as e:
            log.error(f"ML score error {symbol}: {e}")
            return 0.5, True, {}

        # Catalyst adjustment: high catalyst lowers required threshold
        catalyst_adj = (catalyst_score - 5) * 0.01
        effective_threshold = base_threshold - catalyst_adj

        should_trade = proba >= effective_threshold
        log.info(f"ML SCORE | {symbol} {direction} | prob={proba:.3f} "
                 f"threshold={effective_threshold:.3f} catalyst={catalyst_score} "
                 f"-> {'TRADE' if should_trade else 'SKIP'}")

        # Return feature vector for trade logging
        feat_dict = feats.iloc[0].to_dict()
        feat_dict["ml_prob"]       = proba
        feat_dict["ml_window"]     = window
        feat_dict["catalyst_score"] = catalyst_score
        return proba, should_trade, feat_dict

    def _build_features(self, symbol: str, buf: list) -> pd.DataFrame | None:
        try:
            df = pd.DataFrame(buf)
            df["ts"] = pd.to_datetime(df["ts"])
            df = df.sort_values("ts").reset_index(drop=True)

            df["vwap"]  = compute_vwap(df)
            df["ema9"]  = compute_ema(df["close"], 9)
            df["ema21"] = compute_ema(df["close"], 21)
            df["rsi14"] = compute_rsi(df["close"], 14)
            df["atr14"] = compute_atr(df, 14)

            df["date"] = df["ts"].dt.date
            daily_open = df.groupby("date")["open"].first()
            df["day_open"] = df["date"].map(daily_open)
            daily_vol = df.groupby("date")["volume"].sum()
            df["daily_vol"] = df["date"].map(daily_vol)

            df["vwap_dev_pct"]   = (df["close"] - df["vwap"]) / df["vwap"] * 100
            df["ema9_21_spread"] = (df["ema9"] - df["ema21"]) / df["ema21"] * 100
            df["rsi14_feat"]     = df["rsi14"]
            df["atr14_pct"]      = df["atr14"] / df["close"] * 100
            df["gap_pct"]        = (df["day_open"] - df["close"].shift(1)) / df["close"].shift(1) * 100
            today_date = df["date"].iloc[-1]
            today_vol = float(df[df["date"] == today_date]["volume"].sum())
            sym_hist = self._vol_baseline.get(symbol, {})
            past_days = sorted(d for d in sym_hist if d != str(today_date))[-5:]
            past_vols = [sym_hist[d] for d in past_days if sym_hist[d] > 0]
            if len(past_vols) >= 2:
                avg_5d = sum(past_vols) / len(past_vols)
                df["vol_surge_5d"] = today_vol / avg_5d if avg_5d > 0 else 1.0
            else:
                df["vol_surge_5d"] = 1.0
            df["mom_30m_pct"]    = (df["close"] - df["close"].shift(30)) / df["close"].shift(30) * 100
            df["mom_15m_pct"]    = (df["close"] - df["close"].shift(15)) / df["close"].shift(15) * 100
            df["vol_ratio_5m"]   = df["volume"] / df["volume"].rolling(5, min_periods=1).mean()

            minutes = df["ts"].dt.hour * 60 + df["ts"].dt.minute
            df["time_bucket"]      = ((minutes - (9 * 60 + 15)) // 45).clip(0, 7).astype(int)
            df["is_first_30min"]   = (minutes < (9 * 60 + 45)).astype(int)
            df["is_last_hour"]     = (minutes >= (14 * 60 + 15)).astype(int)
            df["above_vwap"]       = (df["close"] > df["vwap"]).astype(int)
            df["bars_above_vwap_pct"] = df["above_vwap"].rolling(30, min_periods=1).mean() * 100

            # ORB width from today's first 15 min bars
            orb_mask = minutes < (9 * 60 + 30)
            if orb_mask.any():
                orb_h = df.loc[orb_mask, "high"].max()
                orb_l = df.loc[orb_mask, "low"].min()
                df["orb_width_pct"] = (orb_h - orb_l) / df["close"] * 100
            else:
                df["orb_width_pct"] = 0.0

            # Context feature stubs — replaced by score() with real values
            df["sym_win_rate_10"] = 0.5
            df["vix_level"] = 0.5
            df["universe_move_30m_pct"] = 0.0
            df["stock_vs_universe_30m"] = 0.0
            df["catalyst_score_feat"] = 0.5

            last = df.iloc[[-1]][FEATURE_COLS].fillna(0)
            return last

        except Exception as e:
            log.warning(f"Feature build error {symbol}: {e}")
            return None

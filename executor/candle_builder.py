"""Builds real 1-min OHLCV candles from repeated REST poll quotes.

Problem it solves: Dhan REST API returns just LTP + cumulative day volume.
The ML model needs real 1-min bars (actual high/low/volume per candle).
This class accumulates polls into proper candles by tracking minute boundaries
and computing per-candle volume as delta of cumulative day volume.
"""
import threading
from collections import defaultdict
from datetime import datetime


class CandleBuilder:
    """
    Thread-safe 1-min OHLCV candle aggregator.

    Usage:
        builder = CandleBuilder()
        # On each poll tick:
        completed = builder.update(symbol, ltp, cum_volume, now)
        if completed:
            bars = builder.get_all_bars(symbol)  # feed to ML scorer
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._completed: dict = defaultdict(list)  # symbol -> [bar, ...]
        self._current: dict = {}                    # symbol -> current bar
        self._prev_cum_vol: dict = {}               # symbol -> last seen cumulative volume

    def update(self, symbol: str, ltp: float, cum_volume: int, ts: datetime) -> bool:
        """
        Feed a poll. Returns True when a new completed bar is created.
        ltp: last traded price
        cum_volume: cumulative day volume from broker (we diff it to get candle volume)
        ts: timestamp of this poll
        """
        minute_ts = ts.replace(second=0, microsecond=0)
        with self._lock:
            cur = self._current.get(symbol)

            if cur is None:
                # First tick for this symbol today
                self._current[symbol] = self._new_bar(minute_ts, ltp)
                self._prev_cum_vol[symbol] = cum_volume
                return False

            if minute_ts > cur["ts"]:
                # Crossed a minute boundary — finalize the old bar
                bars = self._completed[symbol]
                bars.append(dict(cur))
                if len(bars) > 60:
                    bars.pop(0)
                # Start fresh bar for new minute
                self._current[symbol] = self._new_bar(minute_ts, ltp)
                self._prev_cum_vol[symbol] = cum_volume
                return True

            # Same minute — update high/low/close and accumulate volume delta
            cur["high"]  = max(cur["high"], ltp)
            cur["low"]   = min(cur["low"], ltp)
            cur["close"] = ltp
            prev = self._prev_cum_vol.get(symbol, cum_volume)
            cur["volume"] += max(0, cum_volume - prev)
            self._prev_cum_vol[symbol] = cum_volume
            return False

    def get_all_bars(self, symbol: str) -> list:
        """Completed bars + current partial bar. Ready to pass to ml_scorer."""
        with self._lock:
            bars = list(self._completed.get(symbol, []))
            cur = self._current.get(symbol)
            if cur:
                bars = bars + [dict(cur)]
            return bars

    def get_current_bar(self, symbol: str) -> dict | None:
        with self._lock:
            cur = self._current.get(symbol)
            return dict(cur) if cur else None

    def reset(self):
        """Call at start of new trading day to clear all state."""
        with self._lock:
            self._completed.clear()
            self._current.clear()
            self._prev_cum_vol.clear()

    def _new_bar(self, ts: datetime, price: float) -> dict:
        return {
            "ts": ts, "open": price, "high": price,
            "low": price, "close": price, "volume": 0,
        }

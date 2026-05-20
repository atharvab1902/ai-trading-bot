"""EMA Crossover Strategy — trend following for 10:00-14:30 IST.

Fast EMA (9-period) crosses above Slow EMA (21-period) → BUY
Fast EMA crosses below Slow EMA → SELL
Uses 1-minute candles built from ticks for smoother signals.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class Signal:
    action: str
    symbol: str
    price: float
    stoploss: float
    target: float
    reason: str


class EMA:
    def __init__(self, params: dict, market_open: str = "09:15"):
        self.fast_period = params.get("fast_period", 9)
        self.slow_period = params.get("slow_period", 21)
        self.sl_pct = params.get("stoploss_pct", 0.3)
        self.tgt_pct = params.get("target_pct", 0.4)
        self.allow_short = params.get("allow_short", False)
        self.start_time = params.get("start_time", "10:00")
        self.end_time = params.get("end_time", "14:30")

        h, m = map(int, market_open.split(":"))
        self.open_time = time(h, m)
        sh, sm = map(int, self.start_time.split(":"))
        self.active_start = time(sh, sm)
        eh, em = map(int, self.end_time.split(":"))
        self.active_end = time(eh, em)

        # Per-symbol state
        self._candles: dict = {}       # symbol -> list of 1-min close prices
        self._current_candle: dict = {}  # symbol -> {open, high, low, close, minute}
        self._fast_ema: dict = {}
        self._slow_ema: dict = {}
        self._prev_fast: dict = {}
        self._prev_slow: dict = {}
        self._taken: dict = {}         # symbol -> last trade datetime

    def _ema(self, prev: float, price: float, period: int) -> float:
        k = 2 / (period + 1)
        return price * k + prev * (1 - k)

    def _in_active_window(self, now: datetime) -> bool:
        t = now.time()
        return self.active_start <= t <= self.active_end

    def _in_cooldown(self, symbol: str, now: datetime, minutes: int = 10) -> bool:
        last = self._taken.get(symbol)
        if not last:
            return False
        return (now - last).total_seconds() < minutes * 60

    def on_tick(self, symbol: str, price: float, now: datetime, position_open: bool) -> Optional[Signal]:
        if price <= 0:
            return None

        # Build 1-minute candles from ticks
        minute_key = now.replace(second=0, microsecond=0)
        candle = self._current_candle.get(symbol)

        if candle is None or candle["minute"] != minute_key:
            # Close previous candle and start new one
            if candle is not None:
                close_price = candle["close"]
                candles = self._candles.setdefault(symbol, [])
                candles.append(close_price)

                # Update EMAs
                if len(candles) == 1:
                    self._fast_ema[symbol] = close_price
                    self._slow_ema[symbol] = close_price
                else:
                    self._prev_fast[symbol] = self._fast_ema.get(symbol, close_price)
                    self._prev_slow[symbol] = self._slow_ema.get(symbol, close_price)
                    self._fast_ema[symbol] = self._ema(self._fast_ema[symbol], close_price, self.fast_period)
                    self._slow_ema[symbol] = self._ema(self._slow_ema[symbol], close_price, self.slow_period)

            self._current_candle[symbol] = {"minute": minute_key, "open": price, "high": price, "low": price, "close": price}
        else:
            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price

        if not self._in_active_window(now):
            log.debug(f"{symbol} EMA SKIP | outside window ({self.start_time}-{self.end_time})")
            return None

        if position_open or self._in_cooldown(symbol, now):
            return None

        fast = self._fast_ema.get(symbol)
        slow = self._slow_ema.get(symbol)
        prev_fast = self._prev_fast.get(symbol)
        prev_slow = self._prev_slow.get(symbol)

        candle_count = len(self._candles.get(symbol, []))
        if candle_count < self.slow_period:
            log.debug(f"{symbol} EMA SKIP | warming up ({candle_count}/{self.slow_period} candles)")
            return None

        if not all([fast, slow, prev_fast, prev_slow]):
            return None

        log.debug(f"{symbol} EMA | fast={fast:.2f} slow={slow:.2f} prev_fast={prev_fast:.2f} prev_slow={prev_slow:.2f} candles={candle_count}")

        # Golden cross: fast crosses above slow
        if prev_fast <= prev_slow and fast > slow:
            entry = price
            sl = entry * (1 - self.sl_pct / 100)
            tgt = entry * (1 + self.tgt_pct / 100)
            self._taken[symbol] = now
            log.info(f"EMA SIGNAL BUY {symbol} entry={entry:.2f} sl={sl:.2f} tgt={tgt:.2f} fast={fast:.2f} slow={slow:.2f}")
            return Signal("BUY", symbol, entry, sl, tgt,
                          f"EMA crossover: fast({self.fast_period})={fast:.2f} crossed above slow({self.slow_period})={slow:.2f}")

        # Death cross: fast crosses below slow
        if self.allow_short and prev_fast >= prev_slow and fast < slow:
            entry = price
            sl = entry * (1 + self.sl_pct / 100)
            tgt = entry * (1 - self.tgt_pct / 100)
            self._taken[symbol] = now
            log.info(f"EMA SIGNAL SELL {symbol} entry={entry:.2f} sl={sl:.2f} tgt={tgt:.2f} fast={fast:.2f} slow={slow:.2f}")
            return Signal("SELL", symbol, entry, sl, tgt,
                          f"EMA crossover: fast({self.fast_period})={fast:.2f} crossed below slow({self.slow_period})={slow:.2f}")

        return None

    def get_state(self) -> dict:
        return {
            "candles": {s: v[-50:] for s, v in self._candles.items()},  # keep last 50
            "fast_ema": dict(self._fast_ema),
            "slow_ema": dict(self._slow_ema),
            "prev_fast": dict(self._prev_fast),
            "prev_slow": dict(self._prev_slow),
        }

    def load_state(self, state: dict):
        self._candles = dict(state.get("candles", {}))
        self._fast_ema = dict(state.get("fast_ema", {}))
        self._slow_ema = dict(state.get("slow_ema", {}))
        self._prev_fast = dict(state.get("prev_fast", {}))
        self._prev_slow = dict(state.get("prev_slow", {}))
        log.info(f"EMA state loaded | symbols={list(self._fast_ema.keys())}")

    def reset_for_new_day(self):
        self._candles.clear()
        self._current_candle.clear()
        self._fast_ema.clear()
        self._slow_ema.clear()
        self._prev_fast.clear()
        self._prev_slow.clear()
        self._taken.clear()

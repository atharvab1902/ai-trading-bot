"""Opening Range Breakout."""
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


class ORB:
    def __init__(self, params: dict, market_open: str = "09:15"):
        self.range_minutes = params.get("range_minutes", 15)
        self.sl_pct = params.get("stoploss_pct", 0.5)
        self.tgt_pct = params.get("target_pct", 1.0)
        self.buffer_pct = params.get("entry_buffer_pct", 0.05)
        self.allow_short = params.get("allow_short", False)
        self.suppress_long = params.get("_strategist_suppress_long", False)
        self.latest_entry = params.get("latest_entry", "10:00")

        h, m = map(int, market_open.split(":"))
        self.open_time = time(h, m)
        lh, lm = map(int, self.latest_entry.split(":"))
        self.latest_entry_time = time(lh, lm)

        self._range = {}
        self._taken = set()

    def _in_range_window(self, now: datetime) -> bool:
        start = now.replace(hour=self.open_time.hour, minute=self.open_time.minute, second=0, microsecond=0)
        end_min = start.minute + self.range_minutes
        end = start.replace(hour=start.hour + end_min // 60, minute=end_min % 60)
        return start <= now < end

    def _range_locked(self, symbol: str, now: datetime) -> bool:
        r = self._range.get(symbol)
        if not r:
            return False
        return not self._in_range_window(now) and "high" in r

    def on_tick(self, symbol: str, price: float, now: datetime, position_open: bool) -> Optional[Signal]:
        r = self._range.setdefault(symbol, {})

        if self._in_range_window(now):
            r["high"] = max(r.get("high", price), price)
            r["low"] = min(r.get("low", price), price)
            log.debug(f"{symbol} BUILDING RANGE | ltp={price:.2f} | range={r['low']:.2f}-{r['high']:.2f}")
            return None

        if not self._range_locked(symbol, now):
            log.debug(f"{symbol} SKIP | range not formed (started mid-day?)")
            return None

        if now.time() > self.latest_entry_time:
            log.debug(f"{symbol} SKIP | past ORB entry window (latest={self.latest_entry})")
            return None

        if symbol in self._taken:
            log.debug(f"{symbol} SKIP | already traded today")
            return None

        if position_open:
            log.debug(f"{symbol} SKIP | max positions reached")
            return None

        high = r["high"]
        low = r["low"]
        buf = price * self.buffer_pct / 100
        long_trigger = high + buf
        short_trigger = low - buf
        gap_to_long = (long_trigger - price) / price * 100
        gap_to_short = (price - short_trigger) / price * 100

        log.debug(
            f"{symbol} | ltp={price:.2f} | range={low:.2f}-{high:.2f} | "
            f"BUY>={long_trigger:.2f}(gap {gap_to_long:+.3f}%) "
            f"SELL<={short_trigger:.2f}(gap {gap_to_short:+.3f}%)"
        )

        if price > long_trigger:
            if self.suppress_long:
                log.debug(f"{symbol} SKIP ORB LONG | _strategist_suppress_long=True")
                return None
            entry = price
            sl = entry * (1 - self.sl_pct / 100)
            tgt = entry * (1 + self.tgt_pct / 100)
            self._taken.add(symbol)
            log.info(f"ORB SIGNAL BUY {symbol} entry={entry:.2f} sl={sl:.2f} tgt={tgt:.2f}")
            return Signal("BUY", symbol, entry, sl, tgt,
                          f"ORB long: breakout above {high:.2f} + {self.buffer_pct}% buf")

        if self.allow_short and price < short_trigger:
            entry = price
            sl = entry * (1 + self.sl_pct / 100)
            tgt = entry * (1 - self.tgt_pct / 100)
            self._taken.add(symbol)
            log.info(f"ORB SIGNAL SELL {symbol} entry={entry:.2f} sl={sl:.2f} tgt={tgt:.2f}")
            return Signal("SELL", symbol, entry, sl, tgt,
                          f"ORB short: breakdown below {low:.2f} - {self.buffer_pct}% buf")

        return None

    def get_state(self) -> dict:
        return {
            "range": {s: dict(r) for s, r in self._range.items()},
            "taken": list(self._taken),
        }

    def load_state(self, state: dict):
        self._range = {s: dict(r) for s, r in state.get("range", {}).items()}
        self._taken = set(state.get("taken", []))
        log.info(f"ORB state loaded | range={list(self._range.keys())} taken={self._taken}")

    def update_params(self, params: dict):
        self.sl_pct = params.get("stoploss_pct", self.sl_pct)
        self.tgt_pct = params.get("target_pct", self.tgt_pct)
        self.buffer_pct = params.get("entry_buffer_pct", self.buffer_pct)
        self.allow_short = params.get("allow_short", self.allow_short)
        self.suppress_long = params.get("_strategist_suppress_long", self.suppress_long)
        log.info(f"ORB params updated: sl={self.sl_pct} tgt={self.tgt_pct} suppress_long={self.suppress_long}")

    def reset_for_new_day(self):
        self._range.clear()
        self._taken.clear()

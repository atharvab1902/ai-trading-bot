"""VWAP Mean Reversion Strategy."""
import logging
from dataclasses import dataclass, field
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


class VWAP:
    def __init__(self, params: dict, market_open: str = "09:15"):
        self.entry_threshold_pct = params.get("entry_threshold_pct", 0.3)
        self.sl_pct = params.get("stoploss_pct", 0.4)
        self.tgt_pct = params.get("target_pct", 0.25)
        self.allow_short = params.get("allow_short", False)
        self.cooldown_after_trade = params.get("cooldown_minutes", 15)

        h, m = map(int, market_open.split(":"))
        self.open_time = time(h, m)

        self._cum_price_vol: dict = {}
        self._cum_vol: dict = {}
        self._prev_price: dict = {}
        self._taken: dict = {}
        self._ticks: dict = {}

    def _vwap(self, symbol: str) -> Optional[float]:
        cv = self._cum_vol.get(symbol, 0)
        if cv == 0:
            return None
        return self._cum_price_vol.get(symbol, 0) / cv

    def _update(self, symbol: str, price: float, volume: int):
        self._cum_price_vol[symbol] = self._cum_price_vol.get(symbol, 0) + price * max(volume, 1)
        self._cum_vol[symbol] = self._cum_vol.get(symbol, 0) + max(volume, 1)
        self._ticks[symbol] = self._ticks.get(symbol, 0) + 1

    def _in_cooldown(self, symbol: str, now: datetime) -> bool:
        last = self._taken.get(symbol)
        if not last:
            return False
        return (now - last).total_seconds() < self.cooldown_after_trade * 60

    def _skip_time(self, now: datetime) -> bool:
        h, m = self.open_time.hour, self.open_time.minute
        start = now.replace(hour=h, minute=m + 30, second=0, microsecond=0)
        end = now.replace(hour=15, minute=0, second=0, microsecond=0)
        return now < start or now > end

    def on_tick(self, symbol: str, price: float, volume: int,
                now: datetime, position_open: bool) -> Optional[Signal]:
        if price <= 0:
            log.warning(f"{symbol} SKIP | price={price} (zero/invalid)")
            return None

        self._update(symbol, price, volume)
        prev = self._prev_price.get(symbol)
        self._prev_price[symbol] = price
        ticks = self._ticks.get(symbol, 0)

        if self._skip_time(now):
            log.debug(f"{symbol} SKIP | outside VWAP window (09:30-15:00)")
            return None

        if position_open:
            log.debug(f"{symbol} SKIP | max positions reached")
            return None

        if self._in_cooldown(symbol, now):
            last = self._taken.get(symbol)
            secs = (now - last).total_seconds() if last else 0
            log.debug(f"{symbol} SKIP | cooldown ({secs:.0f}s elapsed / {self.cooldown_after_trade*60}s required)")
            return None

        if ticks < 10:
            log.debug(f"{symbol} SKIP | warming up ({ticks}/10 ticks)")
            return None

        vwap = self._vwap(symbol)
        if not vwap or prev is None:
            log.debug(f"{symbol} SKIP | no VWAP yet")
            return None

        deviation_pct = (price - vwap) / vwap * 100
        momentum_up = price > prev
        momentum_down = price < prev
        momentum_label = "UP" if momentum_up else ("DOWN" if momentum_down else "FLAT")

        log.debug(
            f"{symbol} | ltp={price:.2f} prev={prev:.2f} | vwap={vwap:.2f} | "
            f"dev={deviation_pct:+.3f}% (threshold={self.entry_threshold_pct:.3f}%) | "
            f"momentum={momentum_label} | vol={volume} ticks={ticks}"
        )

        if deviation_pct <= -self.entry_threshold_pct and not momentum_down:
            entry = price
            sl = entry * (1 - self.sl_pct / 100)
            # Target: whichever is further — tgt_pct move OR return to VWAP
            tgt = max(entry * (1 + self.tgt_pct / 100), vwap * 1.001)
            self._taken[symbol] = now
            log.info(f"VWAP SIGNAL BUY {symbol} entry={entry:.2f} sl={sl:.2f} tgt={tgt:.2f} dev={deviation_pct:+.3f}%")
            return Signal(
                "BUY", symbol, entry, sl, tgt,
                f"VWAP long: price {deviation_pct:.2f}% below VWAP Rs{vwap:.2f}"
            )

        if self.allow_short and deviation_pct > 0 and deviation_pct >= self.entry_threshold_pct and not momentum_up:
            entry = price
            sl = entry * (1 + self.sl_pct / 100)
            # Target: whichever is further — tgt_pct move OR return to VWAP
            tgt = min(entry * (1 - self.tgt_pct / 100), vwap * 0.999)
            self._taken[symbol] = now
            log.info(f"VWAP SIGNAL SELL {symbol} entry={entry:.2f} sl={sl:.2f} tgt={tgt:.2f} dev={deviation_pct:+.3f}%")
            return Signal(
                "SELL", symbol, entry, sl, tgt,
                f"VWAP short: price {deviation_pct:.2f}% above VWAP Rs{vwap:.2f}"
            )

        return None

    def get_state(self) -> dict:
        return {
            "cum_price_vol": dict(self._cum_price_vol),
            "cum_vol": dict(self._cum_vol),
            "prev_price": dict(self._prev_price),
            "ticks": dict(self._ticks),
            "taken": {s: t.isoformat() for s, t in self._taken.items()},
        }

    def load_state(self, state: dict):
        from datetime import datetime
        self._cum_price_vol = dict(state.get("cum_price_vol", {}))
        self._cum_vol = dict(state.get("cum_vol", {}))
        self._prev_price = dict(state.get("prev_price", {}))
        self._ticks = dict(state.get("ticks", {}))
        self._taken = {
            s: datetime.fromisoformat(t)
            for s, t in state.get("taken", {}).items()
        }
        log.info(f"VWAP state loaded | symbols={list(self._cum_vol.keys())} ticks={dict(self._ticks)}")

    def update_params(self, params: dict):
        self.entry_threshold_pct = params.get("entry_threshold_pct", self.entry_threshold_pct)
        self.sl_pct = params.get("stoploss_pct", self.sl_pct)
        self.tgt_pct = params.get("target_pct", self.tgt_pct)
        self.allow_short = params.get("allow_short", self.allow_short)
        self.cooldown_after_trade = params.get("cooldown_minutes", self.cooldown_after_trade)
        log.info(f"VWAP params updated: threshold={self.entry_threshold_pct} sl={self.sl_pct} tgt={self.tgt_pct}")

    def reset_for_new_day(self):
        self._cum_price_vol.clear()
        self._cum_vol.clear()
        self._prev_price.clear()
        self._taken.clear()
        self._ticks.clear()

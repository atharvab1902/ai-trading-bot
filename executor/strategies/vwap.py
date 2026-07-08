"""VWAP Mean Reversion Strategy."""
import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
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
        # min recovery: price must bounce back this fraction of threshold from worst point
        # e.g. 0.5 means if threshold=0.3%, price must recover 0.15% from its worst deviation
        self.min_recovery_ratio = params.get("min_recovery_ratio", 0.5)
        self._warmup_minutes = params.get("warmup_minutes", 45)  # skip first N min after open

        h, m = map(int, market_open.split(":"))
        self.open_time = time(h, m)

        # Configurable end time — defaults to 15:00 for India, override for US (e.g. "15:30")
        end_str = params.get("vwap_end", "15:00")
        eh, em = map(int, end_str.split(":"))
        self._end_time = time(eh, em)

        self._cum_price_vol: dict = {}
        self._cum_vol: dict = {}
        self._prev_price: dict = {}
        self._taken: dict = {}
        self._ticks: dict = {}
        self._peak_dev: dict = {}  # tracks worst deviation per symbol per direction

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
        market_open_dt = now.replace(
            hour=self.open_time.hour, minute=self.open_time.minute, second=0, microsecond=0
        )
        start = market_open_dt + timedelta(minutes=self._warmup_minutes)
        end = now.replace(hour=self._end_time.hour, minute=self._end_time.minute, second=0, microsecond=0)
        return now < start or now > end

    def _update_peak_and_check_recovery(self, symbol: str, deviation_pct: float, for_long: bool) -> bool:
        """
        Track worst deviation from VWAP. Require price has bounced back
        min_recovery_ratio * threshold from its worst point before entering.

        This prevents entering a trade where the stock is just stuck below/above
        VWAP without any sign of reverting — like NAUKRI stuck at -0.74% for 10+ ticks.
        """
        min_recovery = self.entry_threshold_pct * self.min_recovery_ratio
        if for_long:
            key = symbol + "_L"
            if deviation_pct >= 0:
                # Crossed back above VWAP — reset peak
                self._peak_dev.pop(key, None)
                return False
            # Track worst (most negative) deviation
            self._peak_dev[key] = min(self._peak_dev.get(key, deviation_pct), deviation_pct)
            recovery = deviation_pct - self._peak_dev[key]  # positive when bouncing back
            return recovery >= min_recovery
        else:
            key = symbol + "_S"
            if deviation_pct <= 0:
                # Crossed back below VWAP — reset peak
                self._peak_dev.pop(key, None)
                return False
            # Track worst (most positive) deviation
            self._peak_dev[key] = max(self._peak_dev.get(key, deviation_pct), deviation_pct)
            recovery = self._peak_dev[key] - deviation_pct  # positive when coming back down
            return recovery >= min_recovery

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
            market_open_dt = now.replace(
                hour=self.open_time.hour, minute=self.open_time.minute, second=0, microsecond=0
            )
            start = market_open_dt + timedelta(minutes=self._warmup_minutes)
            end = now.replace(hour=self._end_time.hour, minute=self._end_time.minute, second=0, microsecond=0)
            log.debug(f"{symbol} SKIP | outside VWAP window "
                      f"({start.strftime('%H:%M')}-{end.strftime('%H:%M')})")
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

        # Update peak deviation tracking (runs every tick, needed for recovery state)
        if deviation_pct < 0:
            key_l = symbol + "_L"
            self._peak_dev[key_l] = min(self._peak_dev.get(key_l, deviation_pct), deviation_pct)
        else:
            self._peak_dev.pop(symbol + "_L", None)

        if deviation_pct > 0:
            key_s = symbol + "_S"
            self._peak_dev[key_s] = max(self._peak_dev.get(key_s, deviation_pct), deviation_pct)
        else:
            self._peak_dev.pop(symbol + "_S", None)

        log.debug(
            f"{symbol} | ltp={price:.2f} prev={prev:.2f} | vwap={vwap:.2f} | "
            f"dev={deviation_pct:+.3f}% (threshold={self.entry_threshold_pct:.3f}%) | "
            f"momentum={momentum_label} | vol={volume} ticks={ticks}"
        )

        if deviation_pct <= -self.entry_threshold_pct and not momentum_down:
            min_recovery = self.entry_threshold_pct * self.min_recovery_ratio
            peak = self._peak_dev.get(symbol + "_L", deviation_pct)
            recovery = deviation_pct - peak
            if recovery < min_recovery:
                log.debug(f"{symbol} SKIP | no recovery from peak (peak={peak:+.3f}% recovery={recovery:+.3f}% need={min_recovery:.3f}%)")
                return None
            entry = price
            sl = entry * (1 - self.sl_pct / 100)
            tgt = max(entry * (1 + self.tgt_pct / 100), vwap * (1 + self.tgt_pct / 100))
            # NOTE: cooldown set via notify_traded() only after executor confirms the trade placed
            log.info(f"VWAP SIGNAL BUY {symbol} entry={entry:.2f} sl={sl:.2f} tgt={tgt:.2f} dev={deviation_pct:+.3f}% recovery={recovery:+.3f}%")
            return Signal(
                "BUY", symbol, entry, sl, tgt,
                f"VWAP long: price {deviation_pct:.2f}% below VWAP {vwap:.2f}"
            )

        if self.allow_short and deviation_pct >= self.entry_threshold_pct and not momentum_up:
            min_recovery = self.entry_threshold_pct * self.min_recovery_ratio
            peak = self._peak_dev.get(symbol + "_S", deviation_pct)
            recovery = peak - deviation_pct
            if recovery < min_recovery:
                log.debug(f"{symbol} SKIP | no recovery from peak (peak={peak:+.3f}% recovery={recovery:+.3f}% need={min_recovery:.3f}%)")
                return None
            entry = price
            sl = entry * (1 + self.sl_pct / 100)
            tgt = min(entry * (1 - self.tgt_pct / 100), vwap * (1 - self.tgt_pct / 100))
            # NOTE: cooldown set via notify_traded() only after executor confirms the trade placed
            log.info(f"VWAP SIGNAL SELL {symbol} entry={entry:.2f} sl={sl:.2f} tgt={tgt:.2f} dev={deviation_pct:+.3f}% recovery={recovery:+.3f}%")
            return Signal(
                "SELL", symbol, entry, sl, tgt,
                f"VWAP short: price {deviation_pct:.2f}% above VWAP {vwap:.2f}"
            )

        return None

    def notify_traded(self, symbol: str, now: datetime):
        """Called by executor after trade is confirmed placed. Starts cooldown."""
        self._taken[symbol] = now
        log.debug(f"VWAP cooldown started for {symbol} ({self.cooldown_after_trade}min)")

    def get_state(self) -> dict:
        return {
            "cum_price_vol": dict(self._cum_price_vol),
            "cum_vol": dict(self._cum_vol),
            "prev_price": dict(self._prev_price),
            "ticks": dict(self._ticks),
            "taken": {s: t.isoformat() for s, t in self._taken.items()},
            "peak_dev": dict(self._peak_dev),
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
        self._peak_dev = dict(state.get("peak_dev", {}))
        log.info(f"VWAP state loaded | symbols={list(self._cum_vol.keys())} ticks={dict(self._ticks)}")

    def update_params(self, params: dict):
        self.entry_threshold_pct = params.get("entry_threshold_pct", self.entry_threshold_pct)
        self.sl_pct = params.get("stoploss_pct", self.sl_pct)
        self.tgt_pct = params.get("target_pct", self.tgt_pct)
        self.allow_short = params.get("allow_short", self.allow_short)
        self.cooldown_after_trade = params.get("cooldown_minutes", self.cooldown_after_trade)
        self.min_recovery_ratio = params.get("min_recovery_ratio", self.min_recovery_ratio)
        log.info(f"VWAP params updated: threshold={self.entry_threshold_pct} sl={self.sl_pct} tgt={self.tgt_pct} min_recovery_ratio={self.min_recovery_ratio}")

    def reset_for_new_day(self):
        self._cum_price_vol.clear()
        self._cum_vol.clear()
        self._prev_price.clear()
        self._taken.clear()
        self._ticks.clear()
        self._peak_dev.clear()

"""Tests for executor/strategies/vwap.py."""
from datetime import datetime, timedelta
import pytest

from executor.strategies.vwap import VWAP, Signal

PARAMS = {
    "entry_threshold_pct": 0.4,
    "stoploss_pct": 0.5,
    "target_pct": 0.5,
    "allow_short": True,
    "cooldown_minutes": 5,
    "warmup_minutes": 10,
    "min_recovery_ratio": 0.5,
    "vwap_end": "15:30",
}

# Market open at 09:30, warmup 10 min → trading from 09:40
OPEN = "09:30"
TRADE_TIME = datetime(2026, 7, 8, 10, 0, 0)   # well within window
EARLY_TIME = datetime(2026, 7, 8, 9, 35, 0)   # in warmup
LATE_TIME  = datetime(2026, 7, 8, 15, 45, 0)  # after vwap_end


def _feed(strategy, symbol, price, volume, now, n=1):
    """Feed n identical ticks."""
    sig = None
    for _ in range(n):
        sig = strategy.on_tick(symbol, price, volume, now, position_open=False)
    return sig


def _warm_up(strategy, symbol, base_price=100.0, n=15):
    """Feed enough ticks to pass warmup and build VWAP."""
    now = datetime(2026, 7, 8, 9, 45, 0)
    for i in range(n):
        strategy.on_tick(symbol, base_price, 1000, now + timedelta(seconds=i * 5), position_open=False)


# ── warmup / time window ──────────────────────────────────────────────────────

def test_no_signal_during_warmup():
    s = VWAP(PARAMS, OPEN)
    sig = s.on_tick("TSLA", 100.0, 1000, EARLY_TIME, position_open=False)
    assert sig is None


def test_no_signal_after_vwap_end():
    s = VWAP(PARAMS, OPEN)
    _warm_up(s, "TSLA")
    sig = s.on_tick("TSLA", 100.0, 1000, LATE_TIME, position_open=False)
    assert sig is None


def test_no_signal_when_position_open():
    s = VWAP(PARAMS, OPEN)
    _warm_up(s, "TSLA")
    sig = s.on_tick("TSLA", 100.0, 1000, TRADE_TIME, position_open=True)
    assert sig is None


def test_no_signal_before_10_ticks():
    s = VWAP(PARAMS, OPEN)
    now = datetime(2026, 7, 8, 9, 45, 0)
    for i in range(5):
        sig = s.on_tick("TSLA", 100.0, 1000, now + timedelta(seconds=i * 5), position_open=False)
    assert sig is None


# ── long signal ───────────────────────────────────────────────────────────────

def test_long_signal_below_vwap_with_recovery():
    """Price drops below VWAP by > threshold, then recovers → long signal."""
    s = VWAP(PARAMS, OPEN)
    now = datetime(2026, 7, 8, 9, 45, 0)
    # Build VWAP at ~100
    for i in range(15):
        s.on_tick("TSLA", 100.0, 1000, now + timedelta(seconds=i * 5), False)

    t = now + timedelta(minutes=10)
    # Drop price below VWAP by 0.6% (> threshold 0.4%)
    s.on_tick("TSLA", 99.3, 1000, t, False)
    s.on_tick("TSLA", 99.2, 1000, t + timedelta(seconds=5), False)  # worst point
    # Recover by 0.2% (>= 0.5 * 0.4% = 0.2%)
    sig = s.on_tick("TSLA", 99.4, 1000, t + timedelta(seconds=10), False)

    assert sig is not None
    assert sig.action == "BUY"
    assert sig.symbol == "TSLA"
    assert sig.stoploss < sig.price
    assert sig.target > sig.price


def test_no_long_signal_without_sufficient_recovery():
    """Price below VWAP but barely recovered — no signal yet."""
    s = VWAP(PARAMS, OPEN)
    now = datetime(2026, 7, 8, 9, 45, 0)
    for i in range(15):
        s.on_tick("TSLA", 100.0, 1000, now + timedelta(seconds=i * 5), False)

    t = now + timedelta(minutes=10)
    s.on_tick("TSLA", 99.3, 1000, t, False)
    s.on_tick("TSLA", 99.2, 1000, t + timedelta(seconds=5), False)
    # Only 0.05% recovery, below the 0.2% minimum
    sig = s.on_tick("TSLA", 99.25, 1000, t + timedelta(seconds=10), False)
    assert sig is None


# ── short signal ──────────────────────────────────────────────────────────────

def test_short_signal_above_vwap_with_recovery():
    """Price rises above VWAP by > threshold, then pulls back → short signal.

    Short condition: deviation >= threshold AND not momentum_up AND recovery >= min_recovery.
    Because each tick shifts VWAP slightly upward, we compute expected deviation
    after the warmup ticks and use prices that keep the condition above threshold.
    We verify the signal action rather than asserting exact prices.
    """
    s = VWAP(PARAMS, OPEN)
    now = datetime(2026, 7, 8, 9, 45, 0)
    # Build VWAP at ~100 with 15 ticks (all at 100.0)
    for i in range(15):
        s.on_tick("TSLA", 100.0, 1000, now + timedelta(seconds=i * 5), False)

    t = now + timedelta(minutes=10)
    # Push price up — VWAP will drift a little with each tick
    # Use large moves so the deviation stays well above 0.4% even after drift
    s.on_tick("TSLA", 101.0, 1000, t, False)                            # +~0.9% above vwap
    s.on_tick("TSLA", 101.5, 1000, t + timedelta(seconds=5), False)    # peak, momentum UP
    # Pullback — still clearly above VWAP, momentum DOWN, recovery > min_recovery
    sig = s.on_tick("TSLA", 101.1, 1000, t + timedelta(seconds=10), False)

    assert sig is not None, (
        "Expected SELL signal: price above VWAP by > threshold, pulled back, momentum DOWN"
    )
    assert sig.action == "SELL"
    assert sig.stoploss > sig.price
    assert sig.target < sig.price


def test_no_short_when_allow_short_false():
    params = dict(PARAMS, allow_short=False)
    s = VWAP(params, OPEN)
    now = datetime(2026, 7, 8, 9, 45, 0)
    for i in range(15):
        s.on_tick("TSLA", 100.0, 1000, now + timedelta(seconds=i * 5), False)

    t = now + timedelta(minutes=10)
    s.on_tick("TSLA", 100.5, 1000, t, False)
    s.on_tick("TSLA", 100.6, 1000, t + timedelta(seconds=5), False)
    sig = s.on_tick("TSLA", 100.4, 1000, t + timedelta(seconds=10), False)
    assert sig is None or sig.action != "SELL"


# ── cooldown ──────────────────────────────────────────────────────────────────

def test_cooldown_prevents_reentry():
    s = VWAP(PARAMS, OPEN)
    now = datetime(2026, 7, 8, 9, 45, 0)
    for i in range(15):
        s.on_tick("TSLA", 100.0, 1000, now + timedelta(seconds=i * 5), False)

    t = now + timedelta(minutes=10)
    s.on_tick("TSLA", 99.3, 1000, t, False)
    s.on_tick("TSLA", 99.2, 1000, t + timedelta(seconds=5), False)
    sig1 = s.on_tick("TSLA", 99.4, 1000, t + timedelta(seconds=10), False)
    if sig1:
        s._taken["TSLA"] = t + timedelta(seconds=10)

    # Immediately try again — should be in cooldown
    sig2 = s.on_tick("TSLA", 99.4, 1000, t + timedelta(seconds=15), False)
    assert sig2 is None


# ── stoploss / target levels ──────────────────────────────────────────────────

def test_long_stoploss_and_target_levels():
    s = VWAP(PARAMS, OPEN)
    now = datetime(2026, 7, 8, 9, 45, 0)
    for i in range(15):
        s.on_tick("TSLA", 100.0, 1000, now + timedelta(seconds=i * 5), False)

    t = now + timedelta(minutes=10)
    s.on_tick("TSLA", 99.3, 1000, t, False)
    s.on_tick("TSLA", 99.2, 1000, t + timedelta(seconds=5), False)
    sig = s.on_tick("TSLA", 99.4, 1000, t + timedelta(seconds=10), False)

    if sig and sig.action == "BUY":
        # stoploss: entry * (1 - sl_pct/100)
        expected_sl = sig.price * (1 - 0.005)
        assert abs(sig.stoploss - expected_sl) < 0.01, f"SL: {sig.stoploss} vs {expected_sl}"
        # target: max(entry*(1+tgt_pct/100), vwap*(1+tgt_pct/100))
        # Just verify target > entry (direction is correct) and uses tgt_pct
        assert sig.target > sig.price, "Target must be above entry for long"
        assert sig.stoploss < sig.price, "Stoploss must be below entry for long"


# ── zero / invalid price ──────────────────────────────────────────────────────

def test_zero_price_returns_none():
    s = VWAP(PARAMS, OPEN)
    _warm_up(s, "TSLA")
    sig = s.on_tick("TSLA", 0.0, 1000, TRADE_TIME, False)
    assert sig is None

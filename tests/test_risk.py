"""Tests for executor/risk.py — position sizing and risk checks."""
import pytest
from unittest.mock import patch


def make_cfg(**overrides):
    cfg = {
        "name": "test_acct",
        "capital": 100000,
        "daily_loss_limit_pct": 2.0,
        "max_positions": 3,
        "max_position_size": 10000,
        "active_strategy": "vwap",
        "strategy_params": {
            "vwap": {"stoploss_pct": 0.5, "target_pct": 0.5,
                     "entry_threshold_pct": 0.4, "warmup_minutes": 45}
        },
    }
    cfg.update(overrides)
    return cfg


# ── validate_config ───────────────────────────────────────────────────────────

def test_validate_config_valid(base_cfg):
    from executor.risk import validate_config
    result = validate_config(base_cfg)
    assert result.ok, result.reason


def test_validate_config_daily_loss_too_high():
    from executor.risk import validate_config
    cfg = make_cfg(daily_loss_limit_pct=6.0)
    result = validate_config(cfg)
    assert not result.ok
    assert "daily_loss_limit_pct" in result.reason


def test_validate_config_max_positions_too_high():
    from executor.risk import validate_config
    cfg = make_cfg(max_positions=15)
    result = validate_config(cfg)
    assert not result.ok
    assert "max_positions" in result.reason


def test_validate_config_position_size_over_50pct():
    from executor.risk import validate_config
    # 60k position on 100k capital = 60% → should fail
    cfg = make_cfg(capital=100000, max_position_size=60000)
    result = validate_config(cfg)
    assert not result.ok
    assert "50%" in result.reason


def test_validate_config_stoploss_too_low():
    from executor.risk import validate_config
    cfg = make_cfg()
    cfg["strategy_params"]["vwap"]["stoploss_pct"] = 0.05
    result = validate_config(cfg)
    assert not result.ok


def test_validate_config_stoploss_too_high():
    from executor.risk import validate_config
    cfg = make_cfg()
    cfg["strategy_params"]["vwap"]["stoploss_pct"] = 6.0
    result = validate_config(cfg)
    assert not result.ok


# ── effective_max_positions ───────────────────────────────────────────────────

def test_effective_max_positions_from_capital():
    from executor.risk import effective_max_positions
    # 100k capital / 10k per trade = 10, but capped at config max_positions=3
    cfg = make_cfg(capital=100000, max_position_size=10000, max_positions=3)
    assert effective_max_positions(cfg) == 3


def test_effective_max_positions_capital_limited():
    from executor.risk import effective_max_positions
    # 100k capital / 40k per trade = 2, config allows 5 → should be 2
    cfg = make_cfg(capital=100000, max_position_size=40000, max_positions=5)
    assert effective_max_positions(cfg) == 2


def test_effective_max_positions_hard_cap():
    from executor.risk import effective_max_positions, HARD_MAX_POSITIONS
    cfg = make_cfg(capital=1000000, max_position_size=10000, max_positions=HARD_MAX_POSITIONS + 5)
    assert effective_max_positions(cfg) <= HARD_MAX_POSITIONS


def test_effective_max_positions_minimum_one():
    from executor.risk import effective_max_positions
    cfg = make_cfg(capital=1000, max_position_size=5000, max_positions=3)
    assert effective_max_positions(cfg) >= 1


# ── position_size ─────────────────────────────────────────────────────────────

def test_position_size_basic():
    from executor.risk import position_size
    cfg = make_cfg(max_position_size=10000)
    # 10000 / 200 = 50 shares
    assert position_size(cfg, 200.0) == 50


def test_position_size_expensive_stock():
    from executor.risk import position_size
    cfg = make_cfg(max_position_size=10000)
    # 10000 / 3000 = 3 shares
    assert position_size(cfg, 3000.0) == 3


def test_position_size_very_expensive_floors_to_zero():
    from executor.risk import position_size
    cfg = make_cfg(max_position_size=1000)
    # 1000 / 5000 = 0 shares
    assert position_size(cfg, 5000.0) == 0


def test_position_size_with_multiplier():
    from executor.risk import position_size
    cfg = make_cfg(max_position_size=10000)
    cfg["strategy_params"]["vwap"]["size_multiplier"] = 0.5
    # 10000 * 0.5 / 200 = 25
    assert position_size(cfg, 200.0) == 25


# ── can_open_new_position ─────────────────────────────────────────────────────

def test_can_open_halt():
    from executor.risk import can_open_new_position
    cfg = make_cfg(active_strategy="halt")
    result = can_open_new_position(cfg)
    assert not result.ok
    assert "halt" in result.reason.lower()


def test_can_open_daily_loss_hit():
    from executor.risk import can_open_new_position
    cfg = make_cfg(daily_loss_limit_pct=2.0)
    # today_pnl returns -2100, loss% = 2.1% > 2.0%
    with patch("executor.risk.db.today_pnl", return_value=-2100.0), \
         patch("executor.risk.db.open_positions_count", return_value=0):
        result = can_open_new_position(cfg)
    assert not result.ok
    assert "Daily loss" in result.reason


def test_can_open_max_positions_hit():
    from executor.risk import can_open_new_position
    cfg = make_cfg(max_positions=3, max_position_size=10000)
    with patch("executor.risk.db.today_pnl", return_value=0.0), \
         patch("executor.risk.db.open_positions_count", return_value=3):
        result = can_open_new_position(cfg)
    assert not result.ok
    assert "Max positions" in result.reason


def test_can_open_ok():
    from executor.risk import can_open_new_position
    cfg = make_cfg()
    with patch("executor.risk.db.today_pnl", return_value=0.0), \
         patch("executor.risk.db.open_positions_count", return_value=0):
        result = can_open_new_position(cfg)
    assert result.ok


# ── _max_pos_size helper ──────────────────────────────────────────────────────

def test_max_pos_size_us_key():
    from executor.risk import _max_pos_size
    assert _max_pos_size({"max_position_size": 10000}) == 10000


def test_max_pos_size_india_key():
    from executor.risk import _max_pos_size
    assert _max_pos_size({"max_position_size_inr": 50000}) == 50000


def test_max_pos_size_us_takes_priority():
    from executor.risk import _max_pos_size
    assert _max_pos_size({"max_position_size": 10000, "max_position_size_inr": 50000}) == 10000

"""Hard risk limits. These live in code, not config. Claude cannot override.

If any check fails, the executor halts and Telegram-alerts the human.
"""
from dataclasses import dataclass
from . import db


# Absolute caps that cannot be exceeded regardless of config
HARD_DAILY_LOSS_LIMIT_PCT = 5.0       # even if config tries higher, cap at 5%
HARD_MAX_POSITIONS = 10
HARD_MAX_POSITION_SIZE_PCT_OF_CAPITAL = 50.0
HARD_MIN_STOPLOSS_PCT = 0.1
HARD_MAX_STOPLOSS_PCT = 5.0


@dataclass
class RiskCheck:
    ok: bool
    reason: str = ""


def _max_pos_size(cfg: dict) -> float:
    """Generic position size — supports both max_position_size (US) and max_position_size_inr (India)."""
    return cfg.get("max_position_size") or cfg.get("max_position_size_inr", 0)


def validate_config(cfg: dict) -> RiskCheck:
    """Run at startup and before every config reload."""
    if cfg.get("daily_loss_limit_pct", 999) > HARD_DAILY_LOSS_LIMIT_PCT:
        return RiskCheck(False, f"daily_loss_limit_pct exceeds hard cap {HARD_DAILY_LOSS_LIMIT_PCT}")
    if cfg.get("max_positions", 999) > HARD_MAX_POSITIONS:
        return RiskCheck(False, f"max_positions exceeds hard cap {HARD_MAX_POSITIONS}")
    cap = cfg.get("capital", 0)
    mps = _max_pos_size(cfg)
    if cap > 0 and mps > 0 and (mps / cap * 100) > HARD_MAX_POSITION_SIZE_PCT_OF_CAPITAL:
        return RiskCheck(False, "max_position_size exceeds 50% of capital")
    sp = cfg.get("strategy_params", {}).get(cfg.get("active_strategy"), {})
    sl = sp.get("stoploss_pct")
    if sl is None or sl < HARD_MIN_STOPLOSS_PCT or sl > HARD_MAX_STOPLOSS_PCT:
        return RiskCheck(False, f"stoploss_pct must be in [{HARD_MIN_STOPLOSS_PCT}, {HARD_MAX_STOPLOSS_PCT}]")
    return RiskCheck(True)


def effective_max_positions(cfg: dict) -> int:
    """Compute max open positions from capital and per-trade budget, capped by hard limit."""
    capital = cfg.get("capital", 0)
    per_trade = _max_pos_size(cfg) or capital
    from_capital = int(capital / per_trade) if per_trade > 0 else 1
    explicit = cfg.get("max_positions", HARD_MAX_POSITIONS)
    return max(1, min(explicit, from_capital, HARD_MAX_POSITIONS))


def can_open_new_position(cfg: dict) -> RiskCheck:
    """Checked before each new entry attempt."""
    account = cfg["name"]
    capital = cfg["capital"]

    # Halt flag
    if cfg.get("active_strategy") == "halt":
        return RiskCheck(False, "Strategy set to halt")

    # Daily loss check
    pnl = db.today_pnl(account)
    loss_pct = (-pnl / capital * 100) if pnl < 0 else 0
    if loss_pct >= cfg["daily_loss_limit_pct"]:
        return RiskCheck(False, f"Daily loss limit hit: {loss_pct:.2f}%")

    # Position count — auto-calculated from capital/position-size, never stale
    open_n = db.open_positions_count(account)
    max_pos = effective_max_positions(cfg)
    if open_n >= max_pos:
        return RiskCheck(False, f"Max positions held: {open_n}/{max_pos}")

    return RiskCheck(True)


def position_size(cfg: dict, price: float) -> int:
    """Compute qty for a new position, respecting all size caps."""
    cap_per_trade = _max_pos_size(cfg) or cfg.get("capital", 50000)
    multiplier = cfg.get("strategy_params", {}).get(
        cfg.get("active_strategy"), {}
    ).get("size_multiplier", 1.0)
    budget = cap_per_trade * multiplier
    qty = int(budget // price)
    return max(qty, 0)

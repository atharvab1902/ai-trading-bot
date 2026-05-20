"""Market Regime Detector.

Runs every 30 minutes during market hours. Analyses price action across
the watchlist and writes data/regime.json.

Regime types:
  BULLISH_TREND  — most stocks trending up, use momentum strategies (ORB BUY, EMA BUY)
  BEARISH_TREND  — most stocks trending down, use momentum strategies (ORB SELL, EMA SELL)
  CHOPPY         — no clear direction, use mean reversion only (VWAP)
  VOLATILE       — large swings, reduce position size, widen stops

The executor reads this file every loop and adjusts strategy behaviour.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict

import pytz

log = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")
REPO_ROOT = Path(__file__).parent.parent


def _load_vix() -> float | None:
    """Load India VIX from market_context.json if available."""
    try:
        import json as _json
        ctx_path = REPO_ROOT / "data" / "market_context.json"
        if ctx_path.exists():
            ctx = _json.loads(ctx_path.read_text())
            return ctx.get("vix")
    except Exception:
        pass
    return None


def detect_regime(quotes_history: Dict[str, list]) -> dict:
    """
    quotes_history: {symbol: [ltp1, ltp2, ...]} — last 30 min of prices (360 ticks at 5s)
    Also reads India VIX from market_context.json if available.
    Returns regime dict.
    """
    if not quotes_history:
        return _write_regime("CHOPPY", 0.0, "No data")

    moves = []
    volatilities = []

    for symbol, prices in quotes_history.items():
        if len(prices) < 10:
            continue
        start = prices[0]
        end = prices[-1]
        move_pct = (end - start) / start * 100
        moves.append(move_pct)

        ticks = [abs(prices[i] - prices[i-1]) / prices[i-1] * 100
                 for i in range(1, len(prices))]
        volatilities.append(sum(ticks) / len(ticks) if ticks else 0)

    if not moves:
        return _write_regime("CHOPPY", 0.0, "Insufficient data")

    avg_move = sum(moves) / len(moves)
    avg_vol = sum(volatilities) / len(volatilities) if volatilities else 0
    bullish_count = sum(1 for m in moves if m > 0.2)
    bearish_count = sum(1 for m in moves if m < -0.2)
    total = len(moves)

    # India VIX override — high VIX forces VOLATILE regardless of price action
    vix = _load_vix()
    vix_note = f" | VIX={vix:.1f}" if vix else ""
    if vix and vix >= 20:
        return _write_regime("VOLATILE", avg_move,
                              f"India VIX={vix:.1f} >= 20 — reduce size, no ORB{vix_note}")

    # Volatile: avg tick-to-tick move > 0.05%
    if avg_vol > 0.05:
        return _write_regime("VOLATILE", avg_move,
                              f"High intraday volatility: avg_tick={avg_vol:.4f}%{vix_note}")

    # Strong trend: >60% stocks moving same direction
    if bullish_count / total >= 0.6 and avg_move > 0.2:
        return _write_regime("BULLISH_TREND", avg_move,
                              f"{bullish_count}/{total} stocks up | avg_move={avg_move:+.2f}%{vix_note}")

    if bearish_count / total >= 0.6 and avg_move < -0.2:
        return _write_regime("BEARISH_TREND", avg_move,
                              f"{bearish_count}/{total} stocks down | avg_move={avg_move:+.2f}%{vix_note}")

    return _write_regime("CHOPPY", avg_move,
                          f"Mixed signals: {bullish_count}up/{bearish_count}dn/{total-bullish_count-bearish_count}flat{vix_note}")


def _write_regime(regime: str, avg_move: float, reason: str) -> dict:
    data = {
        "regime": regime,
        "avg_move_pct": round(avg_move, 3),
        "reason": reason,
        "ts": datetime.now(IST).isoformat(),
        "strategies": _strategy_config(regime),
    }
    path = REPO_ROOT / "data" / "regime.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    log.info(f"REGIME: {regime} | {reason}")
    return data


def _strategy_config(regime: str) -> dict:
    """Returns which strategies and directions are active for each regime."""
    if regime == "BULLISH_TREND":
        return {
            "orb":  {"active": True,  "allow_short": False},
            "ema":  {"active": True,  "allow_short": False},
            "vwap": {"active": True,  "allow_short": False},
            "position_size_multiplier": 1.0,
        }
    if regime == "BEARISH_TREND":
        return {
            "orb":  {"active": True,  "allow_short": True,  "allow_long": False},
            "ema":  {"active": True,  "allow_short": True,  "allow_long": False},
            "vwap": {"active": True,  "allow_short": True,  "allow_long": False},
            "position_size_multiplier": 1.0,
        }
    if regime == "VOLATILE":
        return {
            "orb":  {"active": False},
            "ema":  {"active": False},
            "vwap": {"active": True, "allow_short": True},
            "position_size_multiplier": 0.5,  # half size in volatile markets
        }
    # CHOPPY — default
    return {
        "orb":  {"active": False},
        "ema":  {"active": False},
        "vwap": {"active": True, "allow_short": True},
        "position_size_multiplier": 1.0,
    }


def load_regime() -> dict:
    path = REPO_ROOT / "data" / "regime.json"
    if not path.exists():
        return {"regime": "CHOPPY", "strategies": _strategy_config("CHOPPY"),
                "position_size_multiplier": 1.0}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {"regime": "CHOPPY", "strategies": _strategy_config("CHOPPY"),
                "position_size_multiplier": 1.0}

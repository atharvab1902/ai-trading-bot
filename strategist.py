"""Strategist Agent — AI-driven daily parameter adjustments.

Runs after Newsdesk (premarket.py) at 08:30 IST.
Reads: VIX, FII flow, global bias, per-stock sentiment.
Writes: strategy override JSON to data/strategy_override_YYYYMMDD.json
        and applies safe parameter tweaks to the account config.

Rules the Strategist can change (within hard limits):
- max_positions (1–3)
- position_size_multiplier (0.5–1.0) — never increases beyond configured max
- Disable ORB longs when regime outlook is bearish
- Disable ORB shorts when regime outlook is bullish
- Add stocks to skip list (negative sentiment + event risk)

Rules the Strategist CANNOT change:
- SL% or target% — these require backtest validation (researcher + critic + PR)
- Capital or daily loss limit
- Broker mode (paper/live)
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import pytz
import yaml

REPO_ROOT = Path(__file__).parent
IST = pytz.timezone("Asia/Kolkata")
log = logging.getLogger(__name__)


def run_strategist(account: str, market_ctx: dict, stock_analysis: list, global_bias: dict):
    """Compute and apply today's strategy adjustments based on market context."""
    cfg_path = REPO_ROOT / "config" / "accounts" / f"{account}.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    vix = market_ctx.get("vix")
    vix_regime = market_ctx.get("vix_regime", "NORMAL")
    fii_bias = market_ctx.get("fii_bias", "NEUTRAL")
    fii_net = market_ctx.get("fii_net_cr")
    global_mood = global_bias.get("bias", "neutral")

    decisions = []
    overrides = {
        "date": datetime.now(IST).strftime("%Y-%m-%d"),
        "account": account,
        "applied": [],
        "skipped": [],
        "vix": vix,
        "fii_net_cr": fii_net,
        "global_bias": global_mood,
    }

    # ── Position size multiplier based on VIX ──────────────────────────────
    pos_mult = 1.0
    if vix_regime == "HIGH_VOLATILITY":
        pos_mult = 0.5
        decisions.append(f"VIX={vix:.1f} >= 20: position size -> 50% (high vol protection)")
    elif vix_regime == "LOW_VOLATILITY":
        pos_mult = 1.0
        decisions.append(f"VIX={vix:.1f} <= 14: low vol, full size, favor VWAP mean reversion")

    # ── Max positions based on global bias ────────────────────────────────
    base_max = cfg.get("max_positions", 2)
    if global_mood == "risk_off":
        max_pos = max(1, base_max - 1)
        decisions.append(f"Global risk-off: max_positions -> {max_pos}")
    elif global_mood == "risk_on":
        max_pos = min(3, base_max + 1)
        decisions.append(f"Global risk-on: max_positions -> {max_pos}")
    else:
        max_pos = base_max
        decisions.append(f"Global neutral: max_positions unchanged at {max_pos}")

    # ── Directional bias from FII + global ────────────────────────────────
    bullish_signals = 0
    bearish_signals = 0
    if fii_bias == "BULLISH":
        bullish_signals += 1
    elif fii_bias == "BEARISH":
        bearish_signals += 1
    if global_mood == "risk_on":
        bullish_signals += 1
    elif global_mood == "risk_off":
        bearish_signals += 1

    # Aggregate stock sentiment
    sentiments = [s["sentiment"] for s in stock_analysis]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
    if avg_sentiment > 0.3:
        bullish_signals += 1
    elif avg_sentiment < -0.3:
        bearish_signals += 1

    # Direction preference
    if bullish_signals >= 2 and bearish_signals == 0:
        direction_bias = "BULLISH"
        decisions.append(f"Direction bias BULLISH ({bullish_signals} bullish signals): suppress ORB shorts")
    elif bearish_signals >= 2 and bullish_signals == 0:
        direction_bias = "BEARISH"
        decisions.append(f"Direction bias BEARISH ({bearish_signals} bearish signals): suppress ORB longs")
    else:
        direction_bias = "NEUTRAL"
        decisions.append(f"Direction bias NEUTRAL (bull={bullish_signals} bear={bearish_signals}): both directions open")

    # ── Apply to config ────────────────────────────────────────────────────
    cfg["max_positions"] = max_pos
    orb_params = cfg.get("strategy_params", {}).get("orb", {})
    vwap_params = cfg.get("strategy_params", {}).get("vwap", {})

    if direction_bias == "BEARISH":
        orb_params["allow_short"] = True
        # ORB longs: only allow if no strong bearish signal
        orb_params["_strategist_suppress_long"] = True
    elif direction_bias == "BULLISH":
        orb_params["allow_short"] = False
        orb_params.pop("_strategist_suppress_long", None)
    else:
        orb_params["allow_short"] = True
        orb_params.pop("_strategist_suppress_long", None)

    # Write updated config
    cfg["strategy_params"]["orb"] = orb_params
    with open(cfg_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # ── Save override file ─────────────────────────────────────────────────
    overrides["decisions"] = decisions
    overrides["pos_size_multiplier"] = pos_mult
    overrides["direction_bias"] = direction_bias
    overrides["max_positions"] = max_pos

    date_str = datetime.now(IST).strftime("%Y%m%d")
    override_path = REPO_ROOT / "data" / f"strategy_override_{date_str}.json"
    override_path.write_text(json.dumps(overrides, indent=2))

    print(f"\n  Strategist decisions:")
    for d in decisions:
        print(f"    - {d}")

    log.info(f"Strategist done | bias={direction_bias} pos_mult={pos_mult} max_pos={max_pos}")
    return overrides

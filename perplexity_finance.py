"""Perplexity Finance Search integration.

Provides:
- pre_market_context()  : VIX, Dow futures, sector heatmap, earnings today
- intraday_refresh()    : per-symbol sentiment + commodity/macro update
- stock_news()          : rich news for a single stock

Called by:
- premarket.py at 08:30 (pre_market_context)
- executor.py every 90 min during market hours (intraday_refresh)
- scanner.py at 08:00 (stock_news replacing basic sonar call)
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import pytz
import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent
IST = pytz.timezone("Asia/Kolkata")
load_dotenv(REPO_ROOT / ".env")

PERPLEXITY_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
BASE_URL = "https://api.perplexity.ai/chat/completions"

log = logging.getLogger(__name__)


def _query(prompt: str, max_tokens: int = 500, model: str = "sonar") -> str:
    if not PERPLEXITY_KEY:
        log.warning("No PERPLEXITY_API_KEY — skipping finance query")
        return ""
    try:
        resp = requests.post(
            BASE_URL,
            headers={"Authorization": f"Bearer {PERPLEXITY_KEY}",
                     "Content-Type": "application/json"},
            json={"model": model,
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": max_tokens},
            timeout=20,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        log.warning(f"Perplexity Finance HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        log.warning(f"Perplexity Finance error: {e}")
    return ""


def pre_market_context() -> dict:
    """
    Run at 08:30 IST. Returns structured pre-market intelligence:
    - India VIX
    - SGX Nifty / Dow futures direction
    - Top gaining/losing sectors
    - Stocks with earnings today (skip list)
    - Commodity prices (crude, metals) relevant to NSE stocks
    - Overall market bias
    """
    today = datetime.now(IST).strftime("%Y-%m-%d")
    prompt = f"""Today is {today} IST. Indian markets open in ~45 minutes.

Give me a structured pre-market briefing for NSE India intraday trading:

1. INDIA VIX: current value and whether it signals high/low volatility
2. SGX NIFTY or GIFT NIFTY: current level vs yesterday's Nifty close (gap up/down %)
3. US MARKETS: how did Dow, S&P 500, Nasdaq close yesterday?
4. COMMODITIES: crude oil price, gold price, key metals (zinc, aluminium if available)
5. TOP SECTORS: which NSE sectors are expected to be strong/weak today based on overnight cues?
6. EARNINGS TODAY: any Nifty100 companies reporting results today?
7. MACRO EVENTS: any RBI, SEBI, Fed announcements expected today?
8. OVERALL BIAS: risk-on or risk-off for Indian markets today? One sentence.

Be specific with numbers. If data unavailable say N/A."""

    raw = _query(prompt, max_tokens=700)
    if not raw:
        return {"raw": "", "bias": "neutral", "vix": None, "sectors": {}, "earnings_today": [], "commodities": {}}

    # Parse key fields from response
    result = {"raw": raw, "bias": "neutral", "vix": None,
              "sectors": {}, "earnings_today": [], "commodities": {},
              "date": datetime.now(IST).strftime("%Y-%m-%d")}

    raw_lower = raw.lower()

    # Bias
    if any(w in raw_lower for w in ["risk-on", "bullish", "positive bias", "strong open"]):
        result["bias"] = "risk_on"
    elif any(w in raw_lower for w in ["risk-off", "bearish", "negative bias", "weak open", "caution"]):
        result["bias"] = "risk_off"

    # VIX — extract number after "vix"
    import re
    vix_match = re.search(r'vix[:\s]+(\d+\.?\d*)', raw_lower)
    if vix_match:
        try:
            result["vix"] = float(vix_match.group(1))
        except Exception:
            pass

    # Sectors
    if "it" in raw_lower and any(w in raw_lower for w in ["strong", "positive", "up"]):
        result["sectors"]["IT"] = "bullish"
    if "metal" in raw_lower and any(w in raw_lower for w in ["weak", "negative", "down"]):
        result["sectors"]["METAL"] = "bearish"
    if "bank" in raw_lower and any(w in raw_lower for w in ["strong", "positive"]):
        result["sectors"]["BANK"] = "bullish"
    if "pharma" in raw_lower and any(w in raw_lower for w in ["strong", "positive"]):
        result["sectors"]["PHARMA"] = "bullish"

    log.info(f"PRE-MARKET CONTEXT | bias={result['bias']} vix={result['vix']} sectors={result['sectors']}")
    return result


def _claude_extract_intraday(raw: str, symbols: list) -> dict:
    """Use Claude Code CLI to extract structured trading signals from raw Perplexity text."""
    import subprocess
    sym_list = ", ".join(symbols)
    prompt = f"""You are parsing a market news summary for a trading bot. Extract only REAL trading alerts.

Symbols being traded: {sym_list}

News text:
{raw}

Return ONLY a JSON object, no explanation:
{{
  "macro_shock": false,
  "commodity_shock": false,
  "symbol_alerts": {{}}
}}

Rules (be strict):
- macro_shock: true ONLY for surprise RBI/Fed rate decision, war escalation, market circuit breaker, trading halt
- commodity_shock: true ONLY if crude/gold/metals moved >3% suddenly
- symbol_alerts: add a symbol ONLY for SPECIFIC breaking news about THAT symbol — earnings miss, trading halt, block deal, acquisition, profit warning, regulatory action. Do NOT add a symbol just because it appears in a list like "no news for GAIL, NAUKRI..."
- When in doubt, return empty symbol_alerts"""

    try:
        res = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=45
        )
        text = res.stdout.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(text[start:end])
            log.info(f"Claude intraday extract: macro={parsed.get('macro_shock')} "
                     f"commodity={parsed.get('commodity_shock')} "
                     f"alerts={list(parsed.get('symbol_alerts', {}).keys())}")
            return parsed
    except Exception as e:
        log.warning(f"Claude intraday extract failed: {e} — returning empty signals")
    return {"macro_shock": False, "commodity_shock": False, "symbol_alerts": {}}


def intraday_refresh(symbols: list) -> dict:
    """
    Run every 90 min during market hours.
    Returns updated sentiment + commodity signals for the watchlist.
    Saves to data/intraday_context.json for executor to read.
    """
    today = datetime.now(IST).strftime("%Y-%m-%d %H:%M")
    sym_list = ", ".join(symbols[:10])  # top 10 to keep prompt tight

    prompt = f"""Time: {today} IST. Indian markets are open.

Quick intraday update for NSE stocks: {sym_list}

1. COMMODITY UPDATE: Current crude oil, gold, zinc/aluminium prices — any significant moves in last 2 hours?
2. GLOBAL CUES: Any significant moves in US futures, Asian markets right now?
3. SECTOR ROTATION: Any sectors showing unusual strength or weakness right now?
4. BREAKING NEWS: Any breaking news for these specific stocks in last 2 hours: {sym_list}
5. MACRO SHOCK: Any surprise RBI/Fed/geopolitical news in last 2 hours?

Keep it brief and specific. Flag anything that would change intraday trade direction."""

    raw = _query(prompt, max_tokens=500)
    if not raw:
        return {}

    result = {
        "ts": datetime.now(IST).isoformat(),
        "raw": raw,
        "commodity_shock": False,
        "macro_shock": False,
        "symbol_alerts": {},
    }

    # Use Claude Code to extract structured signals — no fragile keyword matching
    parsed = _claude_extract_intraday(raw, symbols)
    result["commodity_shock"] = parsed.get("commodity_shock", False)
    result["macro_shock"] = parsed.get("macro_shock", False)
    result["symbol_alerts"] = parsed.get("symbol_alerts", {})

    if result["commodity_shock"]:
        log.warning("INTRADAY COMMODITY SHOCK detected")
    if result["macro_shock"]:
        log.warning("INTRADAY MACRO SHOCK detected")
    for sym, alert in result["symbol_alerts"].items():
        log.info(f"INTRADAY ALERT | {sym}: {alert[:80]}")

    # Save for executor
    ctx_path = REPO_ROOT / "data" / "intraday_context.json"
    ctx_path.write_text(json.dumps(result, indent=2))
    log.info(f"INTRADAY REFRESH | commodity_shock={result['commodity_shock']} "
             f"macro_shock={result['macro_shock']} alerts={list(result['symbol_alerts'].keys())}")
    return result


def stock_news(symbol: str) -> dict:
    """
    Rich news fetch for a single stock. Replaces basic sonar call in scanner.
    Returns structured dict with news_summary, catalyst_score hint, event_risk.
    """
    today = datetime.now(IST).strftime("%Y-%m-%d")
    prompt = f"""NSE India stock {symbol} — {today}.

Last 24 hours only:
1. Any earnings/results announced?
2. Any management changes, promoter activity, or block deals?
3. Any FII/DII significant buying or selling?
4. Any sector news affecting this stock?
5. Any regulatory, legal, or policy news?
6. Gap up/down reason if any?

Rate the catalyst: STRONG_LONG / WEAK_LONG / NEUTRAL / WEAK_SHORT / STRONG_SHORT
Rate event risk: YES / NO (earnings today = YES)

Format last 2 lines as:
CATALYST: <rating>
EVENT_RISK: <YES/NO>"""

    raw = _query(prompt, max_tokens=350)
    if not raw:
        return {"symbol": symbol, "news": "N/A", "catalyst": "NEUTRAL", "event_risk": False}

    catalyst = "NEUTRAL"
    event_risk = False

    for line in raw.split("\n"):
        if line.startswith("CATALYST:"):
            catalyst = line.replace("CATALYST:", "").strip()
        if line.startswith("EVENT_RISK:"):
            event_risk = "YES" in line.upper()

    direction = "LONG" if "LONG" in catalyst else ("SHORT" if "SHORT" in catalyst else "NEUTRAL")
    strength = "STRONG" if "STRONG" in catalyst else ("WEAK" if "WEAK" in catalyst else "NEUTRAL")

    return {
        "symbol": symbol,
        "news_summary": raw,
        "catalyst": catalyst,
        "direction": direction,
        "strength": strength,
        "event_risk": event_risk,
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1 and sys.argv[1] == "premarket":
        ctx = pre_market_context()
        print(json.dumps(ctx, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "intraday":
        syms = sys.argv[2].split(",") if len(sys.argv) > 2 else ["VEDL", "COALINDIA"]
        result = intraday_refresh(syms)
        print(json.dumps(result, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "stock":
        sym = sys.argv[2] if len(sys.argv) > 2 else "RELIANCE"
        result = stock_news(sym)
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python perplexity_finance.py [premarket|intraday SYMS|stock SYM]")

"""Premarket intelligence pipeline. Run at 8:30 IST before market opens.

What it does:
1. Fetches overnight news for each watchlist stock via Perplexity API (or WebFetch fallback)
2. Scores sentiment per stock (-1 / 0 / +1)
3. Detects event risk (earnings, ex-dividend, block deal)
4. Gets global market bias (US close, crude, INR/USD)
5. Writes analysis to data/premarket_today.json
6. Updates config — skips stocks with event risk, prioritizes high-sentiment stocks
7. Sends full briefing to Telegram

Usage:
    python premarket.py --account tester
"""

import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import pytz
import requests
import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent
IST = pytz.timezone("Asia/Kolkata")
load_dotenv(REPO_ROOT / ".env")

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


# ── Telegram ────────────────────────────────────────────────────────────────

def tg(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[TG] {text}")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=5,
        )
    except Exception as e:
        print(f"[TG ERROR] {e}")


# ── News fetching ────────────────────────────────────────────────────────────

def fetch_perplexity(query: str) -> str:
    """Call Perplexity Sonar API. Falls back to WebFetch-style requests if no key."""
    if PERPLEXITY_API_KEY:
        resp = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": query}],
                "max_tokens": 400,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]

    # Fallback — scrape Google News RSS (no key needed)
    symbol = query.split()[0]
    rss_url = f"https://news.google.com/rss/search?q={symbol}+NSE+stock&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        r = requests.get(rss_url, timeout=10)
        # Extract titles from RSS
        titles = re.findall(r"<title>(.*?)</title>", r.text)[1:6]  # skip feed title
        return "\n".join(titles) if titles else "No news found"
    except Exception:
        return "News fetch failed"


def score_sentiment(text: str) -> int:
    """Simple keyword-based sentiment scorer. Returns -1, 0, or +1."""
    text_lower = text.lower()
    positive = ["beat", "profit", "growth", "upgrade", "buy", "bullish", "strong",
                 "rally", "surge", "record", "positive", "gain", "outperform"]
    negative = ["miss", "loss", "downgrade", "sell", "bearish", "weak", "fall",
                 "drop", "concern", "risk", "negative", "fraud", "investigation",
                 "crash", "default", "cut", "layoff"]
    # Only flag event risk for things happening TODAY or this week
    # Distant future events (next month earnings) should not block trading
    event_risk_words = ["ex-dividend", "ex-div", "block deal", "fir",
                        "sebi notice", "suspension", "results today",
                        "earnings today", "q4 results today", "q3 results today"]

    pos = sum(1 for w in positive if w in text_lower)
    neg = sum(1 for w in negative if w in text_lower)
    has_event = any(w in text_lower for w in event_risk_words)

    score = 0
    if pos > neg + 1:
        score = 1
    elif neg > pos + 1:
        score = -1

    return score, has_event


def analyze_stock(symbol: str) -> dict:
    print(f"  Fetching news: {symbol}...")
    query = (
        f"{symbol} NSE India stock news last 24 hours. "
        f"Any earnings results, management changes, regulatory issues, or major events? "
        f"Brief summary only."
    )
    news_text = fetch_perplexity(query)
    sentiment, event_risk = score_sentiment(news_text)
    return {
        "symbol": symbol,
        "sentiment": sentiment,
        "event_risk": event_risk,
        "headline": news_text[:300],
        "ts": datetime.now(IST).isoformat(),
    }


def fetch_global_bias() -> dict:
    print("  Fetching global market bias...")
    query = (
        "What happened in global markets last night? "
        "US market close direction, Asian markets, crude oil, INR/USD. "
        "One line each. Is the mood risk-on or risk-off for Indian markets today?"
    )
    text = fetch_perplexity(query)
    bias = "neutral"
    if any(w in text.lower() for w in ["risk-on", "bullish", "gains", "rally"]):
        bias = "risk_on"
    elif any(w in text.lower() for w in ["risk-off", "bearish", "sell-off", "fall"]):
        bias = "risk_off"
    return {"bias": bias, "summary": text[:400]}


# ── Config update ────────────────────────────────────────────────────────────

def update_config(account: str, stock_analysis: list, global_bias: dict):
    cfg_path = REPO_ROOT / "config" / "accounts" / f"{account}.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    # Use today's scanner watchlist if available
    today_str = datetime.now(IST).strftime("%Y%m%d")
    scanner_path = REPO_ROOT / "data" / f"watchlist_{today_str}.json"
    if scanner_path.exists():
        scanner_data = json.loads(scanner_path.read_text())
        scanner_symbols = [s["symbol"] for s in scanner_data.get("watchlist", [])]
        if scanner_symbols:
            cfg["watchlist"] = scanner_symbols

    original_watchlist = cfg["watchlist"]

    # Filter out event-risk stocks
    safe_stocks = [s for s in stock_analysis if not s["event_risk"]]
    risky_stocks = [s["symbol"] for s in stock_analysis if s["event_risk"]]

    # Sort by sentiment — positive first
    safe_stocks.sort(key=lambda x: x["sentiment"], reverse=True)

    # If global bias is risk_off, only trade top 3 positive-sentiment stocks
    if global_bias["bias"] == "risk_off":
        tradeable = [s["symbol"] for s in safe_stocks if s["sentiment"] >= 0][:3]
        cfg["max_positions"] = 1  # reduce exposure on bad days
    elif global_bias["bias"] == "risk_on":
        tradeable = [s["symbol"] for s in safe_stocks if s["sentiment"] >= 0]
        cfg["max_positions"] = 3
    else:
        tradeable = [s["symbol"] for s in safe_stocks if s["sentiment"] >= 0]
        cfg["max_positions"] = 2

    # If no tradeable stocks, halt today via active_strategy flag (risk.py checks this)
    if not tradeable:
        cfg["active_strategy"] = "halt"
        skipped_all = True
    else:
        # Never overwrite active_strategy or strategies_enabled — executor manages multi-strategy
        # Only update watchlist; all strategy config stays as the user set it
        cfg["watchlist"] = tradeable
        # Remove stale halt flag from a previous bad day
        if cfg.get("active_strategy") == "halt":
            cfg["active_strategy"] = cfg.get("strategies_enabled", ["orb"])[0]
        skipped_all = False

    with open(cfg_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return risky_stocks, tradeable, skipped_all


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True)
    args = ap.parse_args()

    cfg_path = REPO_ROOT / "config" / "accounts" / f"{args.account}.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    # Use today's scanner watchlist if available (overrides config watchlist)
    today_str = datetime.now(IST).strftime("%Y%m%d")
    scanner_path = REPO_ROOT / "data" / f"watchlist_{today_str}.json"
    if scanner_path.exists():
        scanner_data = json.loads(scanner_path.read_text())
        scanner_symbols = [s["symbol"] for s in scanner_data.get("watchlist", [])]
        if scanner_symbols:
            cfg["watchlist"] = scanner_symbols

    now_ist = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
    print(f"\n{'='*50}")
    print(f"PREMARKET INTELLIGENCE — {now_ist}")
    print(f"Account: {args.account} | Watchlist: {len(cfg['watchlist'])} stocks (from scanner)")
    print(f"{'='*50}\n")

    tg(f"*PREMARKET STARTING* — {now_ist}\nAnalyzing {len(cfg['watchlist'])} stocks...")

    # 1. Global market bias — enhanced with Finance Search
    try:
        from perplexity_finance import pre_market_context
        # Don't re-fetch if already done today (survive restarts)
        fc_path = REPO_ROOT / "data" / "finance_context.json"
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        if fc_path.exists():
            _existing = json.loads(fc_path.read_text())
            if _existing.get("date") == today_str:
                finance_ctx = _existing
                print(f"  Finance context loaded from cache (already ran today)")
                fc_path = None  # skip re-save
            else:
                finance_ctx = pre_market_context()
        else:
            finance_ctx = pre_market_context()
        print(f"Finance context: bias={finance_ctx.get('bias','?')} vix={finance_ctx.get('vix','?')} sectors={finance_ctx.get('sectors',{})}")
        if finance_ctx.get("earnings_today"):
            print(f"  Earnings today (will skip): {finance_ctx['earnings_today']}")
        # Save for executor to use
        fc_path = REPO_ROOT / "data" / "finance_context.json"
        fc_path.write_text(json.dumps(finance_ctx, indent=2))
    except Exception as _e:
        print(f"  Finance context error (non-fatal): {_e}")
        finance_ctx = {}

    global_bias = fetch_global_bias()
    # Merge finance bias if available
    if finance_ctx.get("bias") and finance_ctx["bias"] != "neutral":
        global_bias["bias"] = finance_ctx["bias"]
    print(f"Global bias: {global_bias['bias'].upper()}")

    # 2. Per-stock analysis
    stock_analysis = []
    for sym in cfg["watchlist"]:
        result = analyze_stock(sym)
        stock_analysis.append(result)
        sentiment_label = {1: "POSITIVE", 0: "NEUTRAL", -1: "NEGATIVE"}[result["sentiment"]]
        event_label = " ⚠️ EVENT RISK" if result["event_risk"] else ""
        print(f"  {sym}: {sentiment_label}{event_label}")
        time.sleep(1)  # rate limit

    # 3. Fetch VIX + FII data and save to market_context.json
    print("\n  Fetching India VIX + FII data...")
    try:
        from data_feeds import fetch_and_save as fetch_market_context
        sentiments = {s["symbol"]: s["sentiment"] for s in stock_analysis}
        market_ctx = fetch_market_context(
            global_bias=global_bias["bias"],
            sentiments=sentiments,
        )
        vix = market_ctx.get("vix")
        fii_net = market_ctx.get("fii_net_cr")
        vix_str = f"VIX={vix:.1f}" if vix else "VIX=N/A"
        fii_str = f"FII={fii_net:+.0f}Cr" if fii_net is not None else "FII=N/A"
        print(f"  {vix_str} | {fii_str}")
    except Exception as e:
        print(f"  Data feeds error: {e}")
        market_ctx = {}

    # 4. Update config
    risky_stocks, tradeable, halted = update_config(args.account, stock_analysis, global_bias)

    # 5. Run Strategist — AI-driven daily parameter adjustments
    print("\n  Running Strategist...")
    try:
        from strategist import run_strategist
        run_strategist(args.account, market_ctx, stock_analysis, global_bias)
        print("  Strategist done.")
    except Exception as e:
        print(f"  Strategist error (non-fatal): {e}")

    # 6. Save analysis
    output = {
        "date": datetime.now(IST).strftime("%Y-%m-%d"),
        "account": args.account,
        "global": global_bias,
        "stocks": stock_analysis,
        "tradeable": tradeable,
        "skipped_event_risk": risky_stocks,
        "halted": halted,
        "market_context": market_ctx,
    }
    out_path = REPO_ROOT / "data" / f"premarket_{datetime.now(IST).strftime('%Y%m%d')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))

    # 7. Telegram briefing
    sentiment_lines = ""
    for s in stock_analysis:
        icon = "+" if s["sentiment"] == 1 else ("-" if s["sentiment"] == -1 else "=")
        event = " SKIP" if s["event_risk"] else ""
        sentiment_lines += f"[{icon}] {s['symbol']}{event}\n"

    vix_line = f"VIX: {market_ctx['vix']:.1f} ({market_ctx.get('vix_regime','?')})\n" if market_ctx.get("vix") else ""
    fii_line = f"FII: {market_ctx['fii_net_cr']:+.0f} Cr ({market_ctx.get('fii_bias','?')})\n" if market_ctx.get("fii_net_cr") is not None else ""

    if halted:
        strategy_line = "Strategy: *HALTED* — no safe stocks today"
    else:
        strategy_line = f"Trading: *{', '.join(tradeable)}*\nMax positions: {cfg.get('max_positions', 2)}"

    briefing = (
        f"*PREMARKET BRIEFING*\n"
        f"Date: {datetime.now(IST).strftime('%d %b %Y')}\n"
        f"Global: *{global_bias['bias'].upper()}*\n"
        f"{vix_line}{fii_line}\n"
        f"*Stock Sentiment:*\n{sentiment_lines}\n"
        f"{strategy_line}\n\n"
        f"Market opens in ~{max(0, 9*60+15 - datetime.now(IST).hour*60 - datetime.now(IST).minute)} min"
    )
    tg(briefing)
    print(f"\nBriefing sent to Telegram.")
    print(f"Tradeable today: {tradeable}")
    if risky_stocks:
        print(f"Skipped (event risk): {risky_stocks}")
    if halted:
        print("STRATEGY HALTED — no safe stocks")


if __name__ == "__main__":
    main()

"""US premarket intelligence. Run ~45 min before NYSE open (09:00 ET).

What it does:
1. Fetches overnight news for each US watchlist stock
2. Scores sentiment per stock (-1 / 0 / +1)
3. Detects event risk (earnings, FOMC, dividend)
4. Gets overnight bias (Asia/Europe market direction, US futures)
5. Writes data/premarket_{account}_{date}.json
6. Updates account config watchlist — skips event-risk stocks
7. Sends Telegram briefing

Usage:
    python premarket_us.py --account us_trader
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
ET = pytz.timezone("US/Eastern")
IST = pytz.timezone("Asia/Kolkata")
load_dotenv(REPO_ROOT / ".env")

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


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


def fetch_perplexity(query: str) -> str:
    if PERPLEXITY_API_KEY:
        try:
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
        except Exception:
            pass

    # Fallback — Google News RSS
    symbol = query.split()[0]
    rss_url = f"https://news.google.com/rss/search?q={symbol}+NASDAQ+NYSE+stock&hl=en-US&gl=US&ceid=US:en"
    try:
        r = requests.get(rss_url, timeout=10)
        titles = re.findall(r"<title>(.*?)</title>", r.text)[1:6]
        return "\n".join(titles) if titles else "No news found"
    except Exception:
        return "News fetch failed"


def score_sentiment(text: str) -> tuple[int, bool]:
    text_lower = text.lower()
    positive = ["beat", "profit", "growth", "upgrade", "buy", "bullish", "strong",
                 "rally", "surge", "record", "positive", "gain", "outperform", "raised guidance"]
    negative = ["miss", "loss", "downgrade", "sell", "bearish", "weak", "fall",
                 "drop", "concern", "risk", "negative", "fraud", "investigation",
                 "crash", "default", "cut", "layoff", "warning", "guidance cut"]
    event_risk_words = ["earnings today", "reports today", "earnings release", "ex-dividend today",
                        "ex-div today", "fomc today", "fed decision today", "sec investigation",
                        "trading halt", "circuit breaker", "results today"]

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
        f"{symbol} US stock news last 24 hours. "
        f"Any earnings, guidance, analyst changes, regulatory news, or major events? "
        f"Brief summary only."
    )
    news_text = fetch_perplexity(query)
    sentiment, event_risk = score_sentiment(news_text)
    return {
        "symbol": symbol,
        "sentiment": sentiment,
        "event_risk": event_risk,
        "headline": news_text[:300],
        "ts": datetime.now(ET).isoformat(),
    }


def fetch_overnight_bias() -> dict:
    print("  Fetching overnight market bias...")
    query = (
        "US stock market futures pre-market today. "
        "S&P 500 futures, Nasdaq futures direction. "
        "Asia and Europe market close. Any major macro events (Fed, CPI, jobs)? "
        "Is the mood risk-on or risk-off for US markets today? One line each."
    )
    text = fetch_perplexity(query)
    bias = "neutral"
    if any(w in text.lower() for w in ["risk-on", "bullish", "gains", "rally", "higher", "futures up"]):
        bias = "risk_on"
    elif any(w in text.lower() for w in ["risk-off", "bearish", "sell-off", "fall", "lower", "futures down"]):
        bias = "risk_off"
    return {"bias": bias, "summary": text[:400]}


def update_config(account: str, stock_analysis: list, overnight_bias: dict):
    cfg_path = REPO_ROOT / "config" / "accounts" / f"{account}.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    safe_stocks = [s for s in stock_analysis if not s["event_risk"]]
    risky_stocks = [s["symbol"] for s in stock_analysis if s["event_risk"]]

    safe_stocks.sort(key=lambda x: x["sentiment"], reverse=True)

    if overnight_bias["bias"] == "risk_off":
        tradeable = [s["symbol"] for s in safe_stocks if s["sentiment"] >= 0][:8]
    else:
        tradeable = [s["symbol"] for s in safe_stocks if s["sentiment"] >= 0]

    if not tradeable:
        cfg["active_strategy"] = "halt"
        skipped_all = True
    else:
        cfg["watchlist"] = tradeable
        if cfg.get("active_strategy") == "halt":
            cfg["active_strategy"] = cfg.get("strategies_enabled", ["vwap"])[0]
        skipped_all = False

    with open(cfg_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return risky_stocks, tradeable, skipped_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="us_trader")
    args = ap.parse_args()

    cfg_path = REPO_ROOT / "config" / "accounts" / f"{args.account}.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    now_et = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    print(f"\n{'='*55}")
    print(f"US PREMARKET INTELLIGENCE — {now_et}")
    print(f"Account: {args.account} | Watchlist: {len(cfg['watchlist'])} stocks")
    print(f"{'='*55}\n")

    tg(f"*US PREMARKET STARTING* — {now_et}\nAnalyzing {len(cfg['watchlist'])} US stocks...")

    # 1. Overnight bias
    overnight_bias = fetch_overnight_bias()
    print(f"Overnight bias: {overnight_bias['bias'].upper()}")

    # 2. Per-stock analysis
    stock_analysis = []
    for sym in cfg["watchlist"]:
        result = analyze_stock(sym)
        stock_analysis.append(result)
        label = {1: "POSITIVE", 0: "NEUTRAL", -1: "NEGATIVE"}[result["sentiment"]]
        event_label = " EVENT RISK" if result["event_risk"] else ""
        print(f"  {sym}: {label}{event_label}")
        time.sleep(1)

    # 3. Fetch US VIX
    print("\n  Fetching US VIX...")
    try:
        from data_feeds import fetch_and_save_us
        sentiments = {s["symbol"]: s["sentiment"] for s in stock_analysis}
        market_ctx = fetch_and_save_us(
            global_bias=overnight_bias["bias"],
            sentiments=sentiments,
            account=args.account,
        )
        vix = market_ctx.get("vix")
        vix_str = f"US VIX={vix:.1f} ({market_ctx.get('vix_regime','?')})" if vix else "US VIX=N/A"
        print(f"  {vix_str}")
    except Exception as e:
        print(f"  Data feeds error: {e}")
        market_ctx = {}

    # 4. Update config watchlist
    risky_stocks, tradeable, halted = update_config(args.account, stock_analysis, overnight_bias)

    # 5. Save output
    output = {
        "date": datetime.now(ET).strftime("%Y-%m-%d"),
        "account": args.account,
        "overnight_bias": overnight_bias,
        "stocks": stock_analysis,
        "tradeable": tradeable,
        "skipped_event_risk": risky_stocks,
        "halted": halted,
        "market_context": market_ctx,
    }
    today_str = datetime.now(ET).strftime("%Y%m%d")
    out_path = REPO_ROOT / "data" / f"premarket_{args.account}_{today_str}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))

    # 6. Telegram briefing
    sentiment_lines = ""
    for s in stock_analysis:
        icon = "+" if s["sentiment"] == 1 else ("-" if s["sentiment"] == -1 else "=")
        event = " SKIP" if s["event_risk"] else ""
        sentiment_lines += f"[{icon}] {s['symbol']}{event}\n"

    vix_line = f"US VIX: {market_ctx['vix']:.1f} ({market_ctx.get('vix_regime','?')})\n" if market_ctx.get("vix") else ""

    if halted:
        strategy_line = "Strategy: *HALTED* — no safe stocks today"
    else:
        now_et_obj = datetime.now(ET)
        mins_to_open = max(0, 9 * 60 + 30 - now_et_obj.hour * 60 - now_et_obj.minute)
        strategy_line = (
            f"Trading: *{', '.join(tradeable)}*\n"
            f"Max positions: {cfg.get('max_positions', 3)}\n"
            f"Market opens in ~{mins_to_open} min (ET)"
        )

    briefing = (
        f"*US PREMARKET BRIEFING*\n"
        f"Date: {datetime.now(ET).strftime('%d %b %Y')} (ET)\n"
        f"Overnight: *{overnight_bias['bias'].upper()}*\n"
        f"{vix_line}\n"
        f"*Stock Sentiment:*\n{sentiment_lines}\n"
        f"{strategy_line}"
    )
    tg(briefing)
    print(f"\nBriefing sent to Telegram.")
    print(f"Tradeable today: {tradeable}")
    if risky_stocks:
        print(f"Skipped (event risk): {risky_stocks}")
    if halted:
        print("STRATEGY HALTED")


if __name__ == "__main__":
    main()

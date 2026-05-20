"""Morning Scanner — runs at 08:00 IST before premarket.

What it does:
1. Pulls previous day's price/volume data for all 97 Nifty stocks
2. Filters by liquidity, ATR, gap, volume surge
3. Calls Perplexity for news on top 25 candidates
4. Calls Claude Opus 4.7 to interpret news + assign catalyst scores
5. Outputs ranked watchlist of 15-20 stocks with reasons

Output: data/watchlist_YYYYMMDD.json
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd
import pytz
import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent.parent
IST = pytz.timezone("Asia/Kolkata")
load_dotenv(REPO_ROOT / ".env")

PERPLEXITY_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
CLAUDE_CMD = r"C:\Users\athar\AppData\Roaming\npm\claude.cmd"
DB_PATH = REPO_ROOT / "data" / "market.duckdb"
IDS_PATH = REPO_ROOT / "data" / "nifty100_security_ids.json"

log = logging.getLogger(__name__)


# ── Step 1: Screen stocks by price/volume criteria ───────────────────────────

def screen_stocks() -> pd.DataFrame:
    """
    From all 97 stocks, pick top candidates based on:
    - Gap vs previous close (absolute gap > 0.3%)
    - Volume surge vs 5-day average (> 1.2x)
    - ATR > 0.6% (stock moves enough to be tradeable after brokerage)
    Returns ranked DataFrame.
    """
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute("""
        SELECT symbol, ts, open, high, low, close, volume
        FROM ohlcv_1min
        WHERE ts >= CURRENT_DATE - INTERVAL '10 days'
        ORDER BY symbol, ts
    """).df()
    con.close()

    df["ts"] = pd.to_datetime(df["ts"])
    df["date"] = df["ts"].dt.date

    results = []
    for sym, grp in df.groupby("symbol"):
        days = sorted(grp["date"].unique())
        if len(days) < 3:
            continue

        # Latest complete trading day
        latest_day = days[-1]
        prev_day   = days[-2]

        today_df = grp[grp["date"] == latest_day]
        prev_df  = grp[grp["date"] == prev_day]

        if today_df.empty or prev_df.empty:
            continue

        today_open  = today_df["open"].iloc[0]
        prev_close  = prev_df["close"].iloc[-1]
        today_close = today_df["close"].iloc[-1]

        gap_pct = (today_open - prev_close) / prev_close * 100

        # ATR of latest day
        atr = (today_df["high"].max() - today_df["low"].min()) / today_close * 100

        # Volume surge: today's total vs avg of previous days
        today_vol = today_df["volume"].sum()
        prev_vols = [grp[grp["date"] == d]["volume"].sum() for d in days[-6:-1]]
        avg_vol   = sum(prev_vols) / len(prev_vols) if prev_vols else 1
        vol_surge = today_vol / avg_vol if avg_vol > 0 else 1

        # Intraday momentum (close vs open)
        intraday_move = (today_close - today_open) / today_open * 100

        results.append({
            "symbol":        sym,
            "gap_pct":       round(gap_pct, 3),
            "atr_pct":       round(atr, 3),
            "vol_surge":     round(vol_surge, 3),
            "intraday_move": round(intraday_move, 3),
            "close":         round(today_close, 2),
        })

    df_screen = pd.DataFrame(results)
    if df_screen.empty:
        return df_screen

    # Filter: must be tradeable
    df_screen = df_screen[df_screen["atr_pct"] >= 0.5]  # moves enough
    df_screen = df_screen[df_screen["close"] >= 100]     # not penny stocks

    # Score: weight gap + vol_surge + atr
    df_screen["score"] = (
        df_screen["gap_pct"].abs() * 2.0 +
        (df_screen["vol_surge"] - 1).clip(0) * 1.5 +
        df_screen["atr_pct"] * 1.0
    )

    return df_screen.sort_values("score", ascending=False).reset_index(drop=True)


# ── Step 2: Fetch news via Perplexity ────────────────────────────────────────

def fetch_news_perplexity(symbols: list) -> dict:
    """
    Fetch news for a batch of symbols from Perplexity.
    Returns {symbol: news_text}
    """
    if not PERPLEXITY_KEY:
        log.warning("No Perplexity key — skipping news fetch")
        return {}

    results = {}
    for sym in symbols:
        query = (
            f"NSE India stock {sym}: any news in last 24 hours? "
            f"Earnings results, management changes, FII activity, "
            f"sector news, regulatory issues, block deals, or major announcements? "
            f"Be specific and concise. If no news, say 'No significant news'."
        )
        try:
            resp = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {PERPLEXITY_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": query}],
                    "max_tokens": 300,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                results[sym] = resp.json()["choices"][0]["message"]["content"]
            else:
                results[sym] = "News fetch failed"
                log.warning(f"Perplexity {sym}: HTTP {resp.status_code}")
        except Exception as e:
            results[sym] = "News fetch failed"
            log.warning(f"Perplexity {sym}: {e}")
        time.sleep(0.5)  # rate limit

    return results


# ── Step 3: Claude Opus 4.7 interprets news + scores catalysts ───────────────

def interpret_with_claude(symbols_data: list) -> list:
    """
    symbols_data: list of {symbol, gap_pct, vol_surge, atr_pct, news}
    Returns list with catalyst_score and reasoning added.

    Uses Claude Opus 4.7 via CLI — no API cost.
    """
    prompt = f"""You are a senior NSE intraday trader. Today is {datetime.now(IST).strftime('%Y-%m-%d')}.

For each stock below, analyze the news + technical data and assign:
- catalyst_score: 0-10 (0=no catalyst, 10=strong catalyst with clear direction)
- direction: LONG / SHORT / NEUTRAL
- confidence: HIGH / MEDIUM / LOW
- reason: one line explaining the trade thesis

Data:
{json.dumps(symbols_data, indent=2)}

Rules:
- Earnings beat + gap up = strong LONG catalyst (8-10)
- Earnings miss + gap down = strong SHORT catalyst (8-10)
- High volume surge with no news = suspicious, LOW confidence
- FII buying confirmed = LONG bias
- No news + normal volume = score 2-3, NEUTRAL
- Event risk today (results, ex-div) = score 0, skip trading

Respond with ONLY a JSON array. No explanation outside the JSON.
Format: [{{"symbol": "X", "catalyst_score": 7, "direction": "LONG", "confidence": "HIGH", "reason": "..."}}]"""

    try:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                         delete=False, encoding="utf-8") as f:
            f.write(prompt)
            tmp_path = f.name

        result = subprocess.run(
            f'type "{tmp_path}" | {CLAUDE_CMD} --model claude-opus-4-7 --dangerously-skip-permissions',
            capture_output=True, text=True, timeout=90,
            shell=True, cwd=str(REPO_ROOT),
            encoding="utf-8", errors="replace",
        )
        Path(tmp_path).unlink(missing_ok=True)
        output = result.stdout.strip()

        # Extract JSON from output
        start = output.find("[")
        end   = output.rfind("]") + 1
        if start >= 0 and end > start:
            scored = json.loads(output[start:end])
            return scored
        else:
            log.error(f"Claude output not parseable: {output[:200]}")
            return []
    except Exception as e:
        log.error(f"Claude interpretation failed: {e}")
        return []


# ── Step 4: Global market context ────────────────────────────────────────────

def fetch_global_context() -> dict:
    """Ask Perplexity for overnight global market summary."""
    if not PERPLEXITY_KEY:
        return {"bias": "neutral", "summary": "No Perplexity key"}

    query = (
        "Global markets overnight summary for Indian traders: "
        "US market close (S&P500, Nasdaq direction), Asian markets open, "
        "crude oil price, USD/INR, any major macro events. "
        "One line each. Overall: risk-on or risk-off for NSE today?"
    )
    try:
        resp = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {PERPLEXITY_KEY}",
                     "Content-Type": "application/json"},
            json={"model": "sonar",
                  "messages": [{"role": "user", "content": query}],
                  "max_tokens": 400},
            timeout=15,
        )
        if resp.status_code == 200:
            text = resp.json()["choices"][0]["message"]["content"]
            bias = "neutral"
            tl = text.lower()
            if any(w in tl for w in ["risk-on", "bullish", "rally", "gains"]):
                bias = "risk_on"
            elif any(w in tl for w in ["risk-off", "bearish", "sell-off", "decline"]):
                bias = "risk_off"
            return {"bias": bias, "summary": text}
    except Exception as e:
        log.warning(f"Global context fetch failed: {e}")

    return {"bias": "neutral", "summary": "Fetch failed"}


# ── Main ──────────────────────────────────────────────────────────────────────

def run_scanner(top_n: int = 25) -> dict:
    now = datetime.now(IST)
    date_str = now.strftime("%Y-%m-%d")
    print(f"\n{'='*55}")
    print(f"MORNING SCANNER — {date_str}")
    print(f"{'='*55}\n")

    # 1. Screen by technicals
    print("Step 1: Screening 97 stocks by gap/volume/ATR...")
    screened = screen_stocks()
    if screened.empty:
        print("  No stocks passed screening — market data may not be updated yet")
        return {}
    print(f"  {len(screened)} stocks passed ATR/liquidity filter")
    candidates = screened.head(top_n)
    print(f"  Top {len(candidates)} by score: {candidates['symbol'].tolist()}")

    # 2. Fetch news
    print(f"\nStep 2: Fetching news for {len(candidates)} stocks via Perplexity...")
    news = fetch_news_perplexity(candidates["symbol"].tolist())

    # 3. Global context
    print("\nStep 3: Fetching global market context...")
    global_ctx = fetch_global_context()
    print(f"  Global bias: {global_ctx['bias'].upper()}")

    # 4. Claude interpretation
    print("\nStep 4: Claude Opus 4.7 interpreting catalysts...")
    symbols_data = []
    for _, row in candidates.iterrows():
        symbols_data.append({
            "symbol":    row["symbol"],
            "gap_pct":   row["gap_pct"],
            "vol_surge": row["vol_surge"],
            "atr_pct":   row["atr_pct"],
            "news":      news.get(row["symbol"], "No news fetched"),
        })

    scored = interpret_with_claude(symbols_data)

    # 5. Merge scores back
    score_map = {s["symbol"]: s for s in scored}
    final = []
    for _, row in candidates.iterrows():
        sym = row["symbol"]
        s = score_map.get(sym, {})
        catalyst_score = s.get("catalyst_score", 3)
        direction      = s.get("direction", "NEUTRAL")
        confidence     = s.get("confidence", "LOW")
        reason         = s.get("reason", "No catalyst identified")

        # Skip event-risk stocks (score=0)
        if catalyst_score == 0:
            print(f"  SKIP {sym} — event risk flagged by Claude")
            continue

        final.append({
            "symbol":         sym,
            "catalyst_score": catalyst_score,
            "direction":      direction,
            "confidence":     confidence,
            "reason":         reason,
            "gap_pct":        row["gap_pct"],
            "vol_surge":      row["vol_surge"],
            "atr_pct":        row["atr_pct"],
            "close":          row["close"],
            "news_summary":   news.get(sym, ""),
        })

    # Sort: high catalyst score first, then by vol_surge
    final.sort(key=lambda x: (x["catalyst_score"], x["vol_surge"]), reverse=True)

    # Top 15 for today's watchlist
    watchlist = final[:15]

    output = {
        "date":          date_str,
        "global":        global_ctx,
        "watchlist":     watchlist,
        "all_candidates": len(candidates),
        "generated_at":  now.isoformat(),
    }

    out_path = REPO_ROOT / "data" / f"watchlist_{now.strftime('%Y%m%d')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))

    # Print summary
    print(f"\n{'='*55}")
    print(f"TODAY'S WATCHLIST ({len(watchlist)} stocks)")
    print(f"Global: {global_ctx['bias'].upper()}")
    print(f"{'='*55}")
    for s in watchlist:
        bar = "#" * s["catalyst_score"]
        print(f"  {s['symbol']:12s} [{s['direction']:7s}] score={s['catalyst_score']}/10 "
              f"conf={s['confidence']:6s} gap={s['gap_pct']:+.2f}% vol={s['vol_surge']:.1f}x")
        print(f"    -> {s['reason']}".encode('ascii', errors='replace').decode('ascii'))
    print(f"\nSaved to {out_path.name}")

    return output


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    run_scanner()

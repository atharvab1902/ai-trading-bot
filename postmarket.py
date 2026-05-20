"""Postmarket routine. Runs at 16:00 IST after market close.

What it does:
1. Reads today's trades from SQLite
2. Calculates PnL, win rate, best/worst trade
3. Fetches today's market summary via Perplexity
4. Writes journal entry to data/journal.md
5. Detects recurring loss patterns (tags)
6. Sends full EOD report to Telegram

Usage:
    python postmarket.py --account tester
"""

import argparse
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pytz
import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent
IST = pytz.timezone("Asia/Kolkata")
load_dotenv(REPO_ROOT / ".env")

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
DB_PATH = REPO_ROOT / "data" / "trades.db"


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


def fetch_market_summary() -> str:
    query = (
        "What happened in Indian stock markets today? "
        "Nifty 50 direction, major movers, any big news. "
        "2-3 sentences max."
    )
    if PERPLEXITY_API_KEY:
        try:
            resp = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                         "Content-Type": "application/json"},
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": query}],
                    "max_tokens": 200,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
        except Exception:
            pass
    return "Market summary unavailable (no Perplexity key)"


def get_today_trades(account: str) -> list:
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(DB_PATH) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM trades WHERE account=? AND date(ts)=date('now')",
            (account,)
        ).fetchall()
    return [dict(r) for r in rows]


def tag_trade(trade: dict) -> list:
    tags = []
    pnl = trade.get("pnl") or 0
    symbol = trade.get("symbol", "")
    notes = trade.get("notes", "") or ""
    strategy = trade.get("strategy", "orb")

    tags.append(f"#{strategy}")
    tags.append(f"#{symbol.lower()}")
    if pnl > 0:
        tags.append("#win")
        if "TARGET" in notes:
            tags.append("#clean-exit")
    else:
        tags.append("#loss")
        if "STOPLOSS" in notes:
            tags.append("#stopped-out")
        if "SQUAREOFF" in notes:
            tags.append("#squareoff")
    return tags


def write_journal(account: str, trades: list, market_summary: str, premarket_path: Path):
    today = datetime.now(IST).strftime("%Y-%m-%d")
    journal_path = REPO_ROOT / "data" / "journal.md"

    closed = [t for t in trades if t.get("status") == "closed"]
    total_pnl = sum(t.get("pnl") or 0 for t in closed)
    wins = [t for t in closed if (t.get("pnl") or 0) > 0]
    losses = [t for t in closed if (t.get("pnl") or 0) <= 0]

    best = max(closed, key=lambda t: t.get("pnl") or 0) if closed else None
    worst = min(closed, key=lambda t: t.get("pnl") or 0) if closed else None

    all_tags = []
    for t in closed:
        all_tags.extend(tag_trade(t))
    tags_str = " ".join(sorted(set(all_tags)))

    # Load premarket context
    premarket_context = ""
    if premarket_path.exists():
        try:
            pm = json.loads(premarket_path.read_text())
            premarket_context = f"Global bias was {pm.get('global', {}).get('bias', 'unknown').upper()}. "
            skipped = pm.get("skipped_event_risk", [])
            if skipped:
                premarket_context += f"Skipped event-risk stocks: {', '.join(skipped)}."
        except Exception:
            pass

    # Edge assessment
    if len(closed) == 0:
        edge_note = "No trades today — no signals fired."
    elif len(wins) / max(len(closed), 1) > 0.6:
        edge_note = "Win rate >60% — strategy showing edge. Verify it wasn't just market trend."
    elif len(losses) / max(len(closed), 1) > 0.6:
        edge_note = "Loss rate >60% — check if market was choppy/low-volume. Review signal quality."
    else:
        edge_note = "Mixed results — sample too small to conclude. Keep logging."

    # Recurring pattern check (last 20 entries)
    loss_pattern_warning = ""
    if journal_path.exists():
        content = journal_path.read_text()
        stopped_count = content.count("#stopped-out")
        if stopped_count >= 3:
            loss_pattern_warning = f"\n> WARNING: #stopped-out appears {stopped_count}x in recent journal. Researcher should review stoploss width."

    entry = f"""
## {today} ({account})
**Strategy:** {', '.join(set(t.get('strategy','orb') for t in closed)) or 'none'}
**Trades:** {len(closed)} ({len(wins)}W / {len(losses)}L)
**PnL:** {'+'if total_pnl>=0 else ''}Rs{total_pnl:.2f}

**Market:** {market_summary}

**Context:** {premarket_context}

**Best trade:** {f"{best['symbol']} {'+'if(best['pnl']or 0)>=0 else ''}Rs{best['pnl']:.2f} ({best.get('notes','')})" if best else 'none'}
**Worst trade:** {f"{worst['symbol']} {'+'if(worst['pnl']or 0)>=0 else ''}Rs{worst['pnl']:.2f} ({worst.get('notes','')})" if worst else 'none'}

**Edge check:** {edge_note}
{loss_pattern_warning}

**Tags:** {tags_str}

---"""

    with open(journal_path, "a", encoding="utf-8") as f:
        f.write(entry)

    return total_pnl, len(closed), len(wins), len(losses)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True)
    args = ap.parse_args()

    today_str = datetime.now(IST).strftime("%Y%m%d")
    premarket_path = REPO_ROOT / "data" / f"premarket_{today_str}.json"

    print(f"\n{'='*50}")
    print(f"POSTMARKET — {datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')}")
    print(f"{'='*50}\n")

    tg(f"*POSTMARKET ANALYSIS STARTING*\nAccount: {args.account}")

    print("Fetching market summary...")
    market_summary = fetch_market_summary()

    print("Reading today's trades...")
    trades = get_today_trades(args.account)
    closed = [t for t in trades if t.get("status") == "closed"]

    print(f"Found {len(closed)} closed trades. Writing journal...")
    total_pnl, n, wins, losses = write_journal(
        args.account, trades, market_summary, premarket_path
    )

    # Telegram report
    pct = total_pnl / 10000 * 100  # assume 10k capital
    report = (
        f"*EOD REPORT — {args.account}*\n"
        f"Date: {datetime.now(IST).strftime('%d %b %Y')}\n\n"
        f"Trades: {n} ({wins}W / {losses}L)\n"
        f"PnL: {'+'if total_pnl>=0 else ''}Rs{total_pnl:.2f} ({'+'if pct>=0 else ''}{pct:.2f}%)\n\n"
        f"*Market:* {market_summary[:200]}\n\n"
        f"Journal updated. Sunday researcher will review patterns."
    )
    tg(report)
    print(f"\nDone. Journal written. Telegram sent.")
    print(f"PnL today: {'+'if total_pnl>=0 else ''}Rs{total_pnl:.2f}")

    # Write completion marker so scheduler won't re-run on restart
    import json as _json
    marker = REPO_ROOT / "data" / f"postmarket_{today_str}.json"
    marker.write_text(_json.dumps({"done": True, "pnl": total_pnl, "trades": n}))


if __name__ == "__main__":
    main()

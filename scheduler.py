"""Master scheduler. Run this ONCE and leave it running all day.

What it manages:
- 08:00 IST: morning scanner (Perplexity news + Claude Opus 4.7 catalyst scoring)
- 08:30 IST: premarket intelligence (VIX, FII, strategist config update)
- 09:15 IST: starts executor (ML-driven signals, dynamic watchlist)
- 16:00 IST: postmarket Claude routine (journal, reflection)
- Sunday 10:00: weekly Claude routine (researcher + critic + PR)

Usage:
    python scheduler.py --account tester
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pytz
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent
IST = pytz.timezone("Asia/Kolkata")
load_dotenv(REPO_ROOT / ".env")


LOG_DIR = REPO_ROOT / "logs"

def ist_now() -> datetime:
    return datetime.now(IST)


def log(msg: str):
    line = f"[{ist_now().strftime('%H:%M:%S')} IST] {msg}"
    print(line, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        today = ist_now().strftime("%Y%m%d")
        with open(LOG_DIR / f"scheduler_{today}.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


CLAUDE_CMD = r"C:\Users\athar\AppData\Roaming\npm\claude.cmd"


def run(cmd: list, blocking: bool = True, shell: bool = False):
    log(f"Running: {' '.join(str(c) for c in cmd)}")
    if blocking:
        subprocess.run(cmd, cwd=REPO_ROOT, shell=shell)
    else:
        return subprocess.Popen(cmd, cwd=REPO_ROOT, shell=shell)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True)
    args = ap.parse_args()

    log(f"Scheduler started for account={args.account}")
    log("Watching for: 08:30 premarket | 09:15 executor | 16:00 postmarket | Sun 10:00 weekly")

    scanner_done = False
    premarket_done = False
    executor_proc = None
    postmarket_done = False
    weekly_done = False
    last_date = ist_now().date()

    try:
        while True:
            now = ist_now()
            today = now.date()

            # Reset flags at midnight for new day
            if today != last_date:
                scanner_done = False
                premarket_done = False
                postmarket_done = False
                weekly_done = False
                executor_proc = None
                last_date = today
                log("New day — flags reset.")

            hm = now.hour * 100 + now.minute
            is_weekday = now.weekday() < 5
            is_sunday = now.weekday() == 6

            # 08:00 — morning scanner (Perplexity + Claude Opus 4.7)
            watchlist_file = REPO_ROOT / "data" / f"watchlist_{today.strftime('%Y%m%d')}.json"
            if watchlist_file.exists():
                scanner_done = True  # already ran today, don't re-fetch
            if is_weekday and hm >= 800 and not scanner_done:
                log("SCANNER: Running morning stock scanner...")
                run([sys.executable, "-c",
                     "from scanner.scanner import run_scanner; run_scanner()"])
                scanner_done = True

            # 08:30 — premarket intelligence (VIX, FII, strategist)
            premarket_file = REPO_ROOT / "data" / f"premarket_{today.strftime('%Y%m%d')}.json"
            if premarket_file.exists():
                premarket_done = True  # already ran today
            if is_weekday and hm >= 830 and not premarket_done:
                log("PREMARKET: Fetching VIX + FII + strategist config update...")
                run([sys.executable, "premarket.py", "--account", args.account])
                premarket_done = True

            # 09:15 — start executor (only during market hours)
            if is_weekday and 915 <= hm <= 1515 and executor_proc is None:
                log("MARKET OPEN: Starting executor with ORB + VWAP strategies...")
                executor_proc = run(
                    [sys.executable, "-m", "executor.executor",
                     "--account", args.account,
                     "--loop-seconds", "5"],
                    blocking=False
                )

            # Check executor health
            if executor_proc and executor_proc.poll() is not None:
                log("WARNING: Executor crashed. Restarting...")
                executor_proc = run(
                    [sys.executable, "-m", "executor.executor",
                     "--account", args.account,
                     "--loop-seconds", "5"],
                    blocking=False
                )

            # 16:00 — postmarket analysis (Python) + Claude journaler
            postmarket_file = REPO_ROOT / "data" / f"postmarket_{today.strftime('%Y%m%d')}.json"
            if postmarket_file.exists():
                postmarket_done = True  # already ran today
            if is_weekday and hm >= 1600 and not postmarket_done:
                log("POSTMARKET: Running news summary + journal writer...")
                run([sys.executable, "postmarket.py", "--account", args.account])
                log("POSTMARKET: Running Claude deep analysis...")
                run([
                    CLAUDE_CMD, "-p",
                    f"run postmarket for account={args.account}. "
                    f"Read data/journal.md last entry and data/trades.db today's trades. "
                    f"Use journaler subagent to add insights and pattern tags.",
                    "--dangerously-skip-permissions"
                ], shell=True)
                log("RETRAIN: Running daily ML retrainer...")
                run([sys.executable, "-m", "ml.daily_retrain"])
                postmarket_done = True

            # Sunday 10:00 — weekly Claude routine (researcher + critic)
            if is_sunday and hm >= 1000 and not weekly_done:
                log("WEEKLY: Running Claude researcher + critic + backtester...")
                run([
                    CLAUDE_CMD, "-p",
                    f"run weekly for account={args.account}. "
                    f"Read data/journal.md last 7 entries and data/trades.db last 7 days. "
                    f"Use researcher subagent to propose improvements, then critic to review. "
                    f"Run backtest.py on any surviving proposals. Open git PR.",
                    "--dangerously-skip-permissions"
                ], shell=True)
                weekly_done = True

            time.sleep(30)  # check every 30 seconds

    except KeyboardInterrupt:
        log("Scheduler stopped.")
        if executor_proc and executor_proc.poll() is None:
            log("Stopping executor...")
            executor_proc.terminate()


if __name__ == "__main__":
    main()

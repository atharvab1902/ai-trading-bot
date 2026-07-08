"""Master scheduler. Run this ONCE and leave it running all day.

Timing is derived automatically from the account config's market_open/market_close
and timezone — works for both India (IST, NSE) and US (ET, NYSE) accounts.

Schedule computed from config:
  [open - 75 min]  morning scanner (India only; has_scanner: true)
  [open - 45 min]  premarket intelligence
  [open]           executor starts
  [close]          executor window ends
  [close + 45 min] postmarket analysis + ML retrain
  Sunday 10:00 (local market time): weekly Claude routine

Usage:
    python scheduler.py --account tester
    python scheduler.py --account us_trader
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pytz
import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent
load_dotenv(REPO_ROOT / ".env")

_market_tz = pytz.timezone("Asia/Kolkata")  # overridden from config in main()


def market_now() -> datetime:
    return datetime.now(_market_tz)


def _hm_add(h: int, m: int, offset_min: int) -> int:
    """Return HHMM integer after adding offset_min (may be negative) to h:m."""
    total = h * 60 + m + offset_min
    return (total // 60) * 100 + (total % 60)


def is_market_holiday(date, holiday_file: str) -> tuple[bool, str]:
    holidays_path = REPO_ROOT / "data" / holiday_file
    if not holidays_path.exists():
        return False, ""
    try:
        data = json.loads(holidays_path.read_text())
        year_holidays = data.get(str(date.year), [])
        date_str = date.strftime("%Y-%m-%d")
        for h in year_holidays:
            if h["date"] == date_str:
                return True, h["name"]
    except Exception:
        pass
    return False, ""


LOG_DIR = REPO_ROOT / "logs"


def log(msg: str):
    tz_label = _market_tz.zone.split("/")[-1]
    line = f"[{market_now().strftime('%H:%M:%S')} {tz_label}] {msg}"
    print(line, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        today = market_now().strftime("%Y%m%d")
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
    global _market_tz

    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True)
    args = ap.parse_args()

    # Load account config to get timezone + market hours
    cfg_path = REPO_ROOT / "config" / "accounts" / f"{args.account}.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    _market_tz = pytz.timezone(cfg.get("timezone", "Asia/Kolkata"))

    # Parse market open/close from config
    _open_h, _open_m = map(int, str(cfg.get("market_open", "09:15")).split(":"))
    _close_h, _close_m = map(int, str(cfg.get("market_close", "15:15")).split(":"))

    MARKET_OPEN_HM  = _open_h * 100 + _open_m
    MARKET_CLOSE_HM = _close_h * 100 + _close_m
    SCANNER_HM      = _hm_add(_open_h, _open_m, -75)   # 75 min before open
    PREMARKET_HM    = _hm_add(_open_h, _open_m, -45)   # 45 min before open
    POSTMARKET_HM   = _hm_add(_close_h, _close_m, 45)  # 45 min after close

    holiday_file    = cfg.get("holiday_file", "nse_holidays.json")
    premarket_script = cfg.get("premarket_script", "premarket.py")
    has_scanner     = cfg.get("has_scanner", True)

    tz_label = _market_tz.zone
    log(f"Scheduler started for account={args.account} | tz={tz_label}")
    log(f"Market: {_open_h:02d}:{_open_m:02d}-{_close_h:02d}:{_close_m:02d} | "
        f"Scanner:{SCANNER_HM} Premarket:{PREMARKET_HM} Postmarket:{POSTMARKET_HM}")

    scanner_done   = not has_scanner  # skip scanner if config says so
    premarket_done = False
    executor_proc  = None
    postmarket_done = False
    weekly_done    = False
    last_date      = market_now().date()

    try:
        while True:
            now   = market_now()
            today = now.date()

            # Reset flags at midnight (local market time) for new day
            if today != last_date:
                scanner_done    = not has_scanner
                premarket_done  = False
                postmarket_done = False
                weekly_done     = False
                executor_proc   = None
                last_date       = today
                log("New day — flags reset.")

            hm         = now.hour * 100 + now.minute
            is_weekday = now.weekday() < 5
            is_sunday  = now.weekday() == 6

            # Market holiday check
            holiday, holiday_name = is_market_holiday(today, holiday_file)
            if holiday:
                if hm == PREMARKET_HM:
                    log(f"MARKET HOLIDAY: {holiday_name} — no trading today.")
                time.sleep(30)
                continue

            # Scanner — India only (has_scanner: true in config)
            if has_scanner:
                watchlist_file = REPO_ROOT / "data" / f"watchlist_{today.strftime('%Y%m%d')}.json"
                if watchlist_file.exists():
                    scanner_done = True
                if is_weekday and hm >= SCANNER_HM and not scanner_done:
                    log("SCANNER: Running morning stock scanner...")
                    run([sys.executable, "-c",
                         "from scanner.scanner import run_scanner; run_scanner()"])
                    scanner_done = True

            # Premarket intelligence
            premarket_file = REPO_ROOT / "data" / f"premarket_{args.account}_{today.strftime('%Y%m%d')}.json"
            if premarket_file.exists():
                premarket_done = True
            if is_weekday and hm >= PREMARKET_HM and not premarket_done:
                log(f"PREMARKET: Running {premarket_script}...")
                run([sys.executable, premarket_script, "--account", args.account])
                premarket_done = True

            # Executor — start at market open, run until close
            if is_weekday and MARKET_OPEN_HM <= hm <= MARKET_CLOSE_HM and executor_proc is None:
                log("MARKET OPEN: Starting executor...")
                executor_proc = run(
                    [sys.executable, "-m", "executor.executor",
                     "--account", args.account,
                     "--loop-seconds", "5"],
                    blocking=False
                )

            # Executor health check
            if executor_proc and executor_proc.poll() is not None:
                if is_weekday and MARKET_OPEN_HM <= hm <= MARKET_CLOSE_HM:
                    log("WARNING: Executor crashed. Restarting...")
                    executor_proc = run(
                        [sys.executable, "-m", "executor.executor",
                         "--account", args.account,
                         "--loop-seconds", "5"],
                        blocking=False
                    )
                else:
                    executor_proc = None  # market closed, don't restart

            # Postmarket analysis
            postmarket_file = REPO_ROOT / "data" / f"postmarket_{args.account}_{today.strftime('%Y%m%d')}.json"
            if postmarket_file.exists():
                postmarket_done = True
            if is_weekday and hm >= POSTMARKET_HM and not postmarket_done:
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
                retrain_mod = ("ml.daily_retrain_us"
                               if cfg.get("broker", "dhan") == "alpaca"
                               else "ml.daily_retrain")
                run([sys.executable, "-m", retrain_mod, "--account", args.account])
                postmarket_done = True

            # Weekly Claude routine — Sunday 10:00 local market time
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

            time.sleep(30)

    except KeyboardInterrupt:
        log("Scheduler stopped.")
        if executor_proc and executor_proc.poll() is None:
            log("Stopping executor...")
            executor_proc.terminate()


if __name__ == "__main__":
    main()

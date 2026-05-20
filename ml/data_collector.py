"""Pull 90-day 1-min historical data for Nifty 100 from Dhan, store in DuckDB.

Usage:
    python -m ml.data_collector          # full pull (all 97 stocks)
    python -m ml.data_collector --update # only fetch latest missing bars
"""
import argparse
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd
import pytz
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent.parent
IST = pytz.timezone("Asia/Kolkata")
DB_PATH = REPO_ROOT / "data" / "market.duckdb"
IDS_PATH = REPO_ROOT / "data" / "nifty100_security_ids.json"

load_dotenv(REPO_ROOT / ".env")
log = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS ohlcv_1min (
    symbol      VARCHAR NOT NULL,
    ts          TIMESTAMP NOT NULL,
    open        DOUBLE,
    high        DOUBLE,
    low         DOUBLE,
    close       DOUBLE,
    volume      BIGINT,
    PRIMARY KEY (symbol, ts)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_ts ON ohlcv_1min (symbol, ts);
"""


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute(SCHEMA)
    return con


def pull_stock(client, symbol: str, security_id: int,
               start: datetime, end: datetime) -> pd.DataFrame:
    resp = client.intraday_minute_data(
        security_id=str(security_id),
        exchange_segment="NSE_EQ",
        instrument_type="EQUITY",
        from_date=start.strftime("%Y-%m-%d"),
        to_date=end.strftime("%Y-%m-%d"),
        interval=1,
    )
    if resp.get("status") != "success":
        raise ValueError(f"API error for {symbol}: {resp}")

    data = resp.get("data", {})
    timestamps = data.get("timestamp", [])
    if not timestamps:
        return pd.DataFrame()

    df = pd.DataFrame({
        "symbol": symbol,
        "ts": pd.to_datetime(timestamps, unit="s", utc=True).tz_convert("Asia/Kolkata").tz_localize(None),
        "open":   data.get("open",   [None] * len(timestamps)),
        "high":   data.get("high",   [None] * len(timestamps)),
        "low":    data.get("low",    [None] * len(timestamps)),
        "close":  data.get("close",  [None] * len(timestamps)),
        "volume": data.get("volume", [0]    * len(timestamps)),
    })
    # Keep only market hours 9:15–15:30
    df = df[(df["ts"].dt.hour * 60 + df["ts"].dt.minute >= 9 * 60 + 15) &
            (df["ts"].dt.hour * 60 + df["ts"].dt.minute <= 15 * 60 + 30)]
    return df


def upsert(con, df: pd.DataFrame):
    if df.empty:
        return 0
    con.execute("""
        INSERT OR REPLACE INTO ohlcv_1min
        SELECT symbol, ts, open, high, low, close, volume FROM df
    """)
    return len(df)


def latest_ts(con, symbol: str):
    row = con.execute(
        "SELECT MAX(ts) FROM ohlcv_1min WHERE symbol=?", [symbol]
    ).fetchone()
    return row[0] if row and row[0] else None


def run(update_only: bool = False):
    from dhanhq import dhanhq
    client = dhanhq(os.environ["DHAN_CLIENT_ID"], os.environ["DHAN_ACCESS_TOKEN"])

    with open(IDS_PATH) as f:
        ids = json.load(f)

    con = get_db()
    end = datetime.now(IST).replace(tzinfo=None)
    full_start = (datetime.now(IST) - timedelta(days=89)).replace(tzinfo=None)

    total_bars = 0
    failed = []

    for i, (symbol, sid) in enumerate(ids.items()):
        if update_only:
            last = latest_ts(con, symbol)
            start = (last + timedelta(minutes=1)) if last else full_start
            if start.date() >= end.date():
                log.debug(f"{symbol}: already up to date")
                continue
        else:
            start = full_start

        try:
            df = pull_stock(client, symbol, sid,
                            start.replace(tzinfo=IST) if start.tzinfo is None
                            else start,
                            end.replace(tzinfo=IST) if end.tzinfo is None
                            else end)
            bars = upsert(con, df)
            total_bars += bars
            log.info(f"[{i+1}/{len(ids)}] {symbol}: {bars} bars")
            print(f"  [{i+1}/{len(ids)}] {symbol}: {bars} bars")
        except Exception as e:
            log.error(f"{symbol} FAILED: {e}")
            failed.append(symbol)
            print(f"  [{i+1}/{len(ids)}] {symbol}: FAILED — {e}")

        time.sleep(0.8)  # stay well under rate limit

    con.close()
    print(f"\nDone. Total bars: {total_bars:,} | Failed: {failed or 'none'}")
    return total_bars, failed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true")
    args = ap.parse_args()
    run(update_only=args.update)

"""Backtesting engine using Dhan historical intraday data.

Used by the researcher agent every Sunday to validate strategy changes.

Usage:
    python backtest.py --strategy orb --symbol RELIANCE --days 365
    python backtest.py --strategy vwap --symbol HDFCBANK --days 90
"""

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytz
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent
IST = pytz.timezone("Asia/Kolkata")
load_dotenv(REPO_ROOT / ".env")

NSE_SECURITY_IDS = {
    "RELIANCE": 2885, "HDFCBANK": 1333, "INFY": 1594, "TCS": 11536,
    "SBIN": 3045, "ICICIBANK": 4963, "AXISBANK": 5900, "KOTAKBANK": 1922,
    "LT": 11483, "WIPRO": 3787,
}

BROKERAGE_PER_TRADE = 20  # flat ₹20 per order
STT_PCT = 0.025           # STT on sell side
SLIPPAGE_PCT = 0.05       # assumed slippage


def get_client():
    from dhanhq import dhanhq
    return dhanhq(os.environ["DHAN_CLIENT_ID"], os.environ["DHAN_ACCESS_TOKEN"])


def fetch_minute_data(client, symbol: str, days: int) -> pd.DataFrame:
    sid = NSE_SECURITY_IDS.get(symbol)
    if not sid:
        raise ValueError(f"Unknown symbol: {symbol}")

    end = datetime.now(IST)
    start = end - timedelta(days=days)
    from_date = start.strftime("%Y-%m-%d")
    to_date = end.strftime("%Y-%m-%d")

    print(f"Fetching {days}d of 1-min data for {symbol}...")
    resp = client.intraday_minute_data(
        security_id=str(sid),
        exchange_segment="NSE_EQ",
        instrument_type="EQUITY",
        from_date=from_date,
        to_date=to_date,
    )
    if resp.get("status") != "success":
        raise RuntimeError(f"Dhan API error: {resp}")

    data = resp.get("data", {})
    candles = data.get("open", [])
    if not candles:
        raise RuntimeError("No data returned")

    df = pd.DataFrame({
        "open":   data["open"],
        "high":   data["high"],
        "low":    data["low"],
        "close":  data["close"],
        "volume": data["volume"],
        "ts":     pd.to_datetime(data["timestamp"], unit="s", utc=True).tz_convert(IST),
    })
    df = df.set_index("ts").sort_index()
    return df


def backtest_orb(df: pd.DataFrame, params: dict) -> dict:
    range_min = params.get("range_minutes", 15)
    sl_pct = params.get("stoploss_pct", 0.5)
    tgt_pct = params.get("target_pct", 1.0)
    buf_pct = params.get("entry_buffer_pct", 0.05)
    allow_short = params.get("allow_short", True)
    position_inr = params.get("position_size_inr", 10000)
    latest_h, latest_m = map(int, params.get("latest_entry", "10:00").split(":"))

    import datetime as dt_mod

    trades = []
    for day, day_df in df.groupby(df.index.date):
        if len(day_df) < range_min + 5:
            continue

        # Daily bias: skip choppy days for ORB; only trade with trend
        day_open = day_df.iloc[0]["open"]
        day_close = day_df.iloc[-1]["close"]
        day_bias_pct = (day_close - day_open) / day_open * 100
        if abs(day_bias_pct) < 0.3:
            continue  # choppy day, ORB signals unreliable
        day_bullish = day_bias_pct > 0

        range_window = day_df.iloc[:range_min]
        rng_high = range_window["high"].max()
        rng_low = range_window["low"].min()
        rest = day_df.iloc[range_min:]

        entry = sl = tgt = qty = None
        side = None
        for ts, row in rest.iterrows():
            price = row["close"]
            if entry is None:
                if ts.time() > dt_mod.time(latest_h, latest_m):
                    break  # past latest entry window
                buf = rng_high * buf_pct / 100
                if day_bullish and price > rng_high + buf:
                    entry = price * (1 + SLIPPAGE_PCT / 100)
                    sl = entry * (1 - sl_pct / 100)
                    tgt = entry * (1 + tgt_pct / 100)
                    qty = max(1, int(position_inr / entry))
                    side = "BUY"
                elif allow_short and not day_bullish and price < rng_low - buf:
                    entry = price * (1 - SLIPPAGE_PCT / 100)
                    sl = entry * (1 + sl_pct / 100)
                    tgt = entry * (1 - tgt_pct / 100)
                    qty = max(1, int(position_inr / entry))
                    side = "SELL"
            else:
                if side == "BUY":
                    if price <= sl:
                        pnl = (sl - entry) * qty - BROKERAGE_PER_TRADE * 2 - entry * qty * STT_PCT / 100
                        trades.append({"day": str(day), "result": "SL", "pnl": pnl, "side": side})
                        break
                    elif price >= tgt:
                        pnl = (tgt - entry) * qty - BROKERAGE_PER_TRADE * 2 - tgt * qty * STT_PCT / 100
                        trades.append({"day": str(day), "result": "TGT", "pnl": pnl, "side": side})
                        break
                else:  # SELL
                    if price >= sl:
                        pnl = (entry - sl) * qty - BROKERAGE_PER_TRADE * 2 - sl * qty * STT_PCT / 100
                        trades.append({"day": str(day), "result": "SL", "pnl": pnl, "side": side})
                        break
                    elif price <= tgt:
                        pnl = (entry - tgt) * qty - BROKERAGE_PER_TRADE * 2 - tgt * qty * STT_PCT / 100
                        trades.append({"day": str(day), "result": "TGT", "pnl": pnl, "side": side})
                        break

    return _summarize(trades)


def backtest_vwap(df: pd.DataFrame, params: dict) -> dict:
    threshold = params.get("entry_threshold_pct", 0.3)
    sl_pct = params.get("stoploss_pct", 0.4)
    tgt_pct = params.get("target_pct", 0.25)
    allow_short = params.get("allow_short", True)
    position_inr = params.get("position_size_inr", 10000)

    trades = []
    for day, day_df in df.groupby(df.index.date):
        if len(day_df) < 30:
            continue

        # Daily bias: only trade direction aligned with the day's trend
        day_open = day_df.iloc[0]["open"]
        day_close = day_df.iloc[-1]["close"]
        day_bias_pct = (day_close - day_open) / day_open * 100
        day_bullish = day_bias_pct > 0.1
        day_bearish = day_bias_pct < -0.1

        cum_pv = 0
        cum_v = 0
        prev_price = None
        traded = False

        for ts, row in day_df.iloc[15:].iterrows():  # skip first 15 min
            price = row["close"]
            vol = row["volume"]
            cum_pv += price * max(vol, 1)
            cum_v += max(vol, 1)
            vwap = cum_pv / cum_v

            if prev_price is None:
                prev_price = price
                continue

            dev = (price - vwap) / vwap * 100
            momentum_up = price > prev_price
            momentum_dn = price < prev_price
            prev_price = price

            if traded:
                continue

            # Long: price below VWAP, bouncing up — only on bullish/neutral days
            if day_bullish and dev <= -threshold and momentum_up:
                entry = price * (1 + SLIPPAGE_PCT / 100)
                sl = entry * (1 - sl_pct / 100)
                tgt = entry * (1 + tgt_pct / 100)
                qty = max(1, int(position_inr / entry))
                traded = True
                for _, exit_row in day_df[ts:].iterrows():
                    ep = exit_row["close"]
                    if ep <= sl:
                        pnl = (sl - entry) * qty - BROKERAGE_PER_TRADE * 2 - entry * qty * STT_PCT / 100
                        trades.append({"day": str(day), "result": "SL", "pnl": pnl, "side": "BUY"})
                        break
                    elif ep >= tgt:
                        pnl = (tgt - entry) * qty - BROKERAGE_PER_TRADE * 2 - tgt * qty * STT_PCT / 100
                        trades.append({"day": str(day), "result": "TGT", "pnl": pnl, "side": "BUY"})
                        break

            # Short: price above VWAP, rolling down — only on bearish/neutral days
            elif allow_short and day_bearish and dev >= threshold and momentum_dn:
                entry = price * (1 - SLIPPAGE_PCT / 100)
                sl = entry * (1 + sl_pct / 100)
                tgt = entry * (1 - tgt_pct / 100)
                qty = max(1, int(position_inr / entry))
                traded = True
                for _, exit_row in day_df[ts:].iterrows():
                    ep = exit_row["close"]
                    if ep >= sl:
                        pnl = (entry - sl) * qty - BROKERAGE_PER_TRADE * 2 - sl * qty * STT_PCT / 100
                        trades.append({"day": str(day), "result": "SL", "pnl": pnl, "side": "SELL"})
                        break
                    elif ep <= tgt:
                        pnl = (entry - tgt) * qty - BROKERAGE_PER_TRADE * 2 - tgt * qty * STT_PCT / 100
                        trades.append({"day": str(day), "result": "TGT", "pnl": pnl, "side": "SELL"})
                        break

    return _summarize(trades)


def backtest_ema(df: pd.DataFrame, params: dict) -> dict:
    fast_period = params.get("fast_period", 9)
    slow_period = params.get("slow_period", 21)
    sl_pct = params.get("stoploss_pct", 0.3)
    tgt_pct = params.get("target_pct", 0.4)
    start_h, start_m = map(int, params.get("start_time", "10:00").split(":"))
    end_h, end_m = map(int, params.get("end_time", "14:30").split(":"))
    cooldown_min = params.get("cooldown_minutes", 10)
    position_inr = params.get("position_size_inr", 10000)

    import datetime as dt_mod

    def _ema(prev, price, period):
        k = 2 / (period + 1)
        return price * k + prev * (1 - k)

    trades = []

    for day, day_df in df.groupby(df.index.date):
        if len(day_df) < slow_period + 5:
            continue

        fast = slow = prev_fast = prev_slow = None
        in_trade = False
        entry = sl = tgt = side = qty = None
        cooldown_until = None
        candle_count = 0

        for ts, row in day_df.iterrows():
            price = row["close"]
            t = ts.time()

            # Always update EMAs
            if fast is None:
                fast = slow = price
            else:
                prev_fast, prev_slow = fast, slow
                fast = _ema(fast, price, fast_period)
                slow = _ema(slow, price, slow_period)
            candle_count += 1

            active = dt_mod.time(start_h, start_m) <= t <= dt_mod.time(end_h, end_m)
            if not active or candle_count < slow_period or prev_fast is None:
                continue
            if cooldown_until and ts < cooldown_until:
                continue

            if in_trade:
                if side == "BUY":
                    if price <= sl:
                        pnl = (sl - entry) * qty - BROKERAGE_PER_TRADE * 2 - entry * qty * STT_PCT / 100
                        trades.append({"day": str(day), "result": "SL", "pnl": pnl})
                        in_trade = False
                        cooldown_until = ts + pd.Timedelta(minutes=cooldown_min)
                    elif price >= tgt:
                        pnl = (tgt - entry) * qty - BROKERAGE_PER_TRADE * 2 - tgt * qty * STT_PCT / 100
                        trades.append({"day": str(day), "result": "TGT", "pnl": pnl})
                        in_trade = False
                        cooldown_until = ts + pd.Timedelta(minutes=cooldown_min)
                else:
                    if price >= sl:
                        pnl = (entry - sl) * qty - BROKERAGE_PER_TRADE * 2 - sl * qty * STT_PCT / 100
                        trades.append({"day": str(day), "result": "SL", "pnl": pnl})
                        in_trade = False
                        cooldown_until = ts + pd.Timedelta(minutes=cooldown_min)
                    elif price <= tgt:
                        pnl = (entry - tgt) * qty - BROKERAGE_PER_TRADE * 2 - tgt * qty * STT_PCT / 100
                        trades.append({"day": str(day), "result": "TGT", "pnl": pnl})
                        in_trade = False
                        cooldown_until = ts + pd.Timedelta(minutes=cooldown_min)
            else:
                # Golden cross → BUY
                if prev_fast <= prev_slow and fast > slow:
                    entry = price * (1 + SLIPPAGE_PCT / 100)
                    sl = entry * (1 - sl_pct / 100)
                    tgt = entry * (1 + tgt_pct / 100)
                    qty = max(1, int(position_inr / entry))
                    side = "BUY"
                    in_trade = True
                # Death cross → SELL
                elif prev_fast >= prev_slow and fast < slow:
                    entry = price * (1 - SLIPPAGE_PCT / 100)
                    sl = entry * (1 + sl_pct / 100)
                    tgt = entry * (1 - tgt_pct / 100)
                    qty = max(1, int(position_inr / entry))
                    side = "SELL"
                    in_trade = True

        # Close at EOD if still open
        if in_trade:
            last = day_df.iloc[-1]["close"]
            if side == "BUY":
                pnl = (last - entry) * qty - BROKERAGE_PER_TRADE * 2 - last * qty * STT_PCT / 100
            else:
                pnl = (entry - last) * qty - BROKERAGE_PER_TRADE * 2 - last * qty * STT_PCT / 100
            trades.append({"day": str(day), "result": "EOD", "pnl": pnl})

    return _summarize(trades)


def _summarize(trades: list) -> dict:
    if not trades:
        return {"trades": 0, "note": "No trades generated"}

    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    total = sum(pnls)
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    expectancy = (len(wins) / len(pnls)) * avg_win + (len(losses) / len(pnls)) * avg_loss if pnls else 0

    # Sharpe (simplified)
    import statistics
    if len(pnls) > 1:
        sharpe = (sum(pnls) / len(pnls)) / (statistics.stdev(pnls) + 0.001)
    else:
        sharpe = 0

    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1),
        "total_pnl": round(total, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy_per_trade": round(expectancy, 2),
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(min(pnls), 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", choices=["orb", "vwap", "ema"], required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--params", type=str, default="{}", help="JSON params override")
    args = ap.parse_args()

    import json
    params = json.loads(args.params)

    client = get_client()
    df = fetch_minute_data(client, args.symbol.upper(), args.days)

    if args.strategy == "orb":
        result = backtest_orb(df, params)
    elif args.strategy == "vwap":
        result = backtest_vwap(df, params)
    else:
        result = backtest_ema(df, params)

    print(f"\n{'='*50}")
    print(f"BACKTEST: {args.strategy.upper()} | {args.symbol} | {args.days}d")
    print(f"{'='*50}")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print(f"{'='*50}\n")

    # Save result
    out = REPO_ROOT / "data" / f"backtest_{args.strategy}_{args.symbol}_{args.days}d.json"
    out.write_text(json.dumps({
        "strategy": args.strategy, "symbol": args.symbol,
        "days": args.days, "params": params, "result": result,
        "ts": datetime.now(IST).isoformat()
    }, indent=2))
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()

"""Main trade executor. Runs during market hours. No LLM calls."""
import argparse
import json
import logging
import os
import time
import traceback
from datetime import datetime
from pathlib import Path

import pytz
import yaml
from dotenv import load_dotenv

from . import db, risk
from .broker import make_broker
from .candle_builder import CandleBuilder
from .logger import setup_logging
from .regime import detect_regime, load_regime
from .sectors import has_sector_conflict
from .strategies import get_strategy
from .telegram_bot import Telegram
from ml.scorer import MLScorer


REPO_ROOT = Path(__file__).parent.parent
IST = pytz.timezone("Asia/Kolkata")
_market_tz = IST  # overridden at startup from account config timezone field
_currency = "Rs"  # overridden at startup: "$" for Alpaca/US, "Rs" for Dhan/India
log = logging.getLogger(__name__)


def state_file_path(account: str) -> Path:
    return REPO_ROOT / "data" / f"strategy_state_{account}_{datetime.now(IST).strftime('%Y%m%d')}.json"


def save_state(account: str, strategies: dict):
    try:
        state = {"date": datetime.now(IST).strftime("%Y-%m-%d"), "strategies": {}}
        for name, strat in strategies.items():
            if hasattr(strat, "get_state"):
                state["strategies"][name] = strat.get_state()
        state_file_path(account).write_text(json.dumps(state))
    except Exception as e:
        log.warning(f"Failed to save strategy state: {e}")


def load_state(account: str, strategies: dict):
    path = state_file_path(account)
    if not path.exists():
        log.info("No state file for today — will try log replay")
        return False
    try:
        state = json.loads(path.read_text())
        if state.get("date") != datetime.now(IST).strftime("%Y-%m-%d"):
            log.info("State file is from a different day — ignoring")
            return False
        for name, strat in strategies.items():
            if name in state["strategies"] and hasattr(strat, "load_state"):
                strat.load_state(state["strategies"][name])
        log.info(f"Strategy state loaded from {path.name}")
        return True
    except Exception as e:
        log.warning(f"Failed to load state file: {e}")
        return False


def replay_from_log(account: str, strategies: dict, market_open: str):
    """Parse today's log file and replay all quotes through strategies to rebuild state."""
    import re
    from glob import glob

    # Use most recent log file for this account — machine local time may differ from IST
    log_pattern = str(REPO_ROOT / "logs" / f"executor_{account}_*.log")
    log_files = sorted(glob(log_pattern))

    if not log_files:
        log.info("No log file found — starting fresh")
        return

    # Find the log file that contains today's IST date session
    today_ist = datetime.now(IST).strftime("%Y-%m-%d")
    today_date = datetime.now(IST).date()
    log_file = None
    for lf in reversed(log_files):  # most recent first
        try:
            # Peek at first 2000 bytes to check if it has today's market session
            with open(lf, encoding="utf-8") as f:
                head = f.read(2000)
            if "LOOP 1" in head:  # has market session data
                log_file = lf
                break
        except Exception:
            continue

    if not log_file:
        log_file = log_files[-1]  # fallback to most recent
    log.info(f"Replaying quotes from {Path(log_file).name} to rebuild strategy state...")

    quote_re = re.compile(
        r"\[(\d{2}:\d{2}:\d{2})\].*QUOTE (\w+) \| ltp=([\d.]+) vol=(\d+)"
    )
    # Detect local->IST offset from LOOP lines: "[HH:MM:SS] ... LOOP N | HH:MM:SS IST"
    loop_re = re.compile(r"\[(\d{2}:\d{2}:\d{2})\].*LOOP \d+ \| (\d{2}:\d{2}:\d{2})")
    ist_offset_seconds = 0
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            lm = loop_re.search(line)
            if lm:
                local_t, ist_t = lm.groups()
                lh, lmin, ls = map(int, local_t.split(":"))
                ih, imin, is_ = map(int, ist_t.split(":"))
                local_secs = lh * 3600 + lmin * 60 + ls
                ist_secs = ih * 3600 + imin * 60 + is_
                diff = ist_secs - local_secs
                # Handle day boundary (e.g. local=22:45, ist=09:15 next day → diff=-48600 → +38400?)
                if diff < -43200:
                    diff += 86400
                elif diff > 43200:
                    diff -= 86400
                ist_offset_seconds = diff
                break
    ist_offset_hours = ist_offset_seconds / 3600
    log.info(f"Detected local->IST offset: {ist_offset_hours:+.1f}h")

    today_date = datetime.now(IST).date()
    replayed = 0

    with open(log_file, encoding="utf-8") as f:
        for line in f:
            m = quote_re.search(line)
            if not m:
                continue
            time_str, symbol, ltp_str, vol_str = m.groups()
            ltp = float(ltp_str)
            volume = int(vol_str)
            if ltp <= 0:
                continue

            h, m_min, s = map(int, time_str.split(":"))
            local_secs = h * 3600 + m_min * 60 + s
            ist_secs = (local_secs + ist_offset_seconds) % 86400
            ist_h = ist_secs // 3600
            ist_m = (ist_secs % 3600) // 60
            ist_s = ist_secs % 60
            import datetime as dt_mod
            tick_time = datetime.combine(today_date, dt_mod.time(ist_h, ist_m, ist_s))

            for strat_name, strat in strategies.items():
                try:
                    if strat_name == "vwap":
                        strat.on_tick(symbol, ltp, volume, tick_time, position_open=False)
                    else:
                        strat.on_tick(symbol, ltp, tick_time, position_open=False)
                except Exception:
                    pass
            replayed += 1

    log.info(f"Log replay complete — {replayed} ticks replayed into strategies (IST offset={ist_offset_hours:+.1f}h)")


def init_orb_from_api(broker, orb_strategy, watchlist: list, now: datetime):
    """
    If bot starts after the ORB range window (9:15-9:30), fetch 1-min candles
    from Dhan to reconstruct the opening range so ORB can still fire signals.
    """
    range_end = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if now < range_end:
        return  # still in range window — live ticks will build it

    from .broker import PaperBroker, DhanBroker
    live = broker.live if isinstance(broker, PaperBroker) else broker
    if not isinstance(live, DhanBroker):
        return

    today = now.strftime("%Y-%m-%d")
    log.info("ORB: started after 09:30 — fetching opening range from Dhan API...")

    for sym in watchlist:
        r = orb_strategy._range.get(sym, {})
        if "high" in r and "low" in r:
            continue  # range already set from state/log-replay
        try:
            sid = str(live._security_id(sym))
            resp = live.client.intraday_minute_data(
                security_id=sid,
                exchange_segment="NSE_EQ",
                instrument_type="EQUITY",
                from_date=today,
                to_date=today,
                interval=1,
            )
            if not resp or resp.get("status") != "success":
                log.warning(f"ORB API range: {sym} failed — {resp}")
                continue
            data = resp.get("data", {})
            # Dhan returns Unix epoch floats under 'timestamp' key
            timestamps = data.get("timestamp", data.get("start_Time", []))
            highs = data.get("high", [])
            lows = data.get("low", [])
            if not timestamps:
                log.warning(f"ORB {sym}: API returned 0 candles for {today} (same-day data not available — bot must start before 09:15)")
                continue
            import datetime as dt_mod
            range_high = None
            range_low = None
            for ts_epoch, h, l in zip(timestamps, highs, lows):
                dt_ist = datetime.fromtimestamp(float(ts_epoch), tz=IST)
                hhmm = dt_ist.strftime("%H:%M")
                if "09:15" <= hhmm < "09:30":
                    range_high = max(range_high, h) if range_high is not None else h
                    range_low = min(range_low, l) if range_low is not None else l
            if range_high is not None and range_low is not None:
                orb_strategy._range[sym] = {"high": range_high, "low": range_low}
                log.info(f"ORB {sym}: range recovered via API — {range_low:.2f}-{range_high:.2f}")
            else:
                log.warning(f"ORB {sym}: no 09:15-09:30 candles in API response")
        except Exception as e:
            log.warning(f"ORB range recovery {sym}: {e}")


def ist_now() -> datetime:
    return datetime.now(_market_tz)


def in_market_hours(cfg: dict) -> bool:
    now = ist_now()
    if now.weekday() >= 5:
        return False
    open_h, open_m = map(int, str(cfg["market_open"]).split(":"))
    close_h, close_m = map(int, str(cfg["market_close"]).split(":"))
    open_t = now.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
    close_t = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
    return open_t <= now <= close_t


def is_past_market_close(cfg: dict) -> bool:
    """True any time at or after market close — survives restarts after 15:15."""
    now = ist_now()
    close_h, close_m = map(int, str(cfg["market_close"]).split(":"))
    close_t = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
    return now >= close_t


def load_scanner_watchlist(cfg: dict) -> tuple[list, dict]:
    """Load today's watchlist from scanner output.
    Falls back to config watchlist if scanner hasn't run yet.
    Returns (watchlist_symbols, catalyst_scores_dict)
    """
    date_str = datetime.now(IST).strftime("%Y%m%d")
    path = REPO_ROOT / "data" / f"watchlist_{date_str}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
            watchlist = data.get("watchlist", [])
            symbols = [s["symbol"] for s in watchlist]
            catalyst = {s["symbol"]: s for s in watchlist}
            if symbols:
                log.info(f"SCANNER WATCHLIST loaded: {symbols}")
                return symbols, catalyst
        except Exception as e:
            log.warning(f"Scanner watchlist load failed: {e}")
    log.info("No scanner watchlist found — using config watchlist")
    return cfg.get("watchlist", []), {}


def load_config(account: str) -> dict:
    path = REPO_ROOT / "config" / "accounts" / f"{account}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path) as f:
        cfg = yaml.safe_load(f)
    return cfg


def fire_floor_manager(trigger: str, context: dict, telegram: Telegram):
    alerts_dir = REPO_ROOT / "data" / "alerts"
    alerts_dir.mkdir(parents=True, exist_ok=True)
    path = alerts_dir / f"{int(time.time())}_{trigger}.json"
    path.write_text(json.dumps({"trigger": trigger, "context": context,
                                "ts": datetime.now(IST).isoformat()}))
    telegram.send(f"FLOOR-MGR trigger: *{trigger}*\n{context}")


def check_exits(account: str, broker, tg: Telegram, dry_run: bool,
                consecutive_losses: int, quotes: dict = None) -> tuple:
    with db.conn() as c:
        open_trades = c.execute(
            "SELECT id, symbol, side, qty, entry_price, stoploss, target FROM trades "
            "WHERE account=? AND status='open'", (account,)
        ).fetchall()

    if open_trades:
        log.info(f"EXIT CHECK | {len(open_trades)} open trade(s)")

    sl_hits: set = set()   # symbols that hit SL this loop — returned for cross-strategy cooldown

    for trade in open_trades:
        trade_id = trade["id"]
        sym = trade["symbol"]
        qty = trade["qty"]
        entry = trade["entry_price"]
        sl = trade["stoploss"]
        tgt = trade["target"]
        side = trade["side"]

        # Use already-fetched batch quotes if available — avoids extra API call
        if quotes and sym in quotes:
            ltp = quotes[sym].ltp
        else:
            try:
                q = broker.get_quote(sym)
                ltp = q.ltp
            except Exception as e:
                log.error(f"EXIT CHECK | {sym} quote error: {e}")
                continue

        if ltp <= 0:
            log.warning(f"EXIT CHECK | {sym} ltp=0 — skipping")
            continue

        hit = None
        exit_price = ltp

        if side == "BUY":
            # Trailing SL: once price reaches 50% of the way to target, slide SL to breakeven
            if tgt > entry and ltp > entry:
                progress = (ltp - entry) / (tgt - entry)
                if progress >= 0.5 and sl < entry:
                    if not dry_run:
                        with db.conn() as c:
                            c.execute("UPDATE trades SET stoploss=? WHERE id=?", (entry, trade_id))
                    sl = entry
                    log.info(f"TRAILING SL | {sym} BUY moved SL to breakeven {entry:.2f} (progress={progress:.0%})")

            log.info(f"EXIT CHECK | {sym} BUY ltp={ltp:.2f} | sl={sl:.2f} tgt={tgt:.2f} | "
                     f"to_sl={((ltp-sl)/sl*100):+.2f}% to_tgt={((tgt-ltp)/ltp*100):+.2f}%")
            if ltp <= sl:
                hit = "STOPLOSS"
                exit_price = sl
            elif ltp >= tgt:
                hit = "TARGET"
                exit_price = tgt
        else:
            # Trailing SL: once price reaches 50% of way to target, slide SL to breakeven
            if tgt < entry and ltp < entry:
                progress = (entry - ltp) / (entry - tgt)
                if progress >= 0.5 and sl > entry:
                    if not dry_run:
                        with db.conn() as c:
                            c.execute("UPDATE trades SET stoploss=? WHERE id=?", (entry, trade_id))
                    sl = entry
                    log.info(f"TRAILING SL | {sym} SELL moved SL to breakeven {entry:.2f} (progress={progress:.0%})")

            log.info(f"EXIT CHECK | {sym} SELL ltp={ltp:.2f} | sl={sl:.2f} tgt={tgt:.2f} | "
                     f"to_sl={((sl-ltp)/ltp*100):+.2f}% to_tgt={((ltp-tgt)/tgt*100):+.2f}%")
            if ltp >= sl:
                hit = "STOPLOSS"
                exit_price = sl
            elif ltp <= tgt:
                hit = "TARGET"
                exit_price = tgt

        if hit:
            pnl = (exit_price - entry) * qty if side == "BUY" else (entry - exit_price) * qty
            if not dry_run:
                db.close_trade(trade_id, exit_price, pnl, notes=hit)
            if hit == "STOPLOSS":
                consecutive_losses += 1
                sl_hits.add(sym)
            else:
                consecutive_losses = 0
            log.info(f"{'TARGET HIT' if hit == 'TARGET' else 'STOPLOSS HIT'} | "
                     f"{sym} exit={exit_price:.2f} pnl={_currency}{pnl:+.2f}")
            tg.send(
                f"{'TARGET HIT' if hit=='TARGET' else 'STOPLOSS HIT'}\n"
                f"EXIT {side} {qty} *{sym}* @ {_currency}{exit_price:.2f}\n"
                f"Entry: {_currency}{entry:.2f} | PnL: {'+'if pnl>=0 else ''}{_currency}{pnl:.2f}"
            )
            if consecutive_losses >= 2:
                fire_floor_manager("LOSS_STREAK",
                                   {"consecutive": consecutive_losses, "last_symbol": sym}, tg)

    return consecutive_losses, sl_hits


def squareoff_all(account: str, broker, tg: Telegram, dry_run: bool):
    with db.conn() as c:
        open_trades = c.execute(
            "SELECT id, symbol, side, qty, entry_price FROM trades "
            "WHERE account=? AND status='open'", (account,)
        ).fetchall()

    if not open_trades:
        log.info("SQUAREOFF | no open positions")
        return

    tg.send("Market close — squaring off all open positions.")
    for trade in open_trades:
        sym = trade["symbol"]
        qty = trade["qty"]
        entry = trade["entry_price"]
        side = trade["side"]
        try:
            q = broker.get_quote(sym)
            exit_price = q.ltp if q.ltp > 0 else entry
        except Exception:
            exit_price = entry
        pnl = (exit_price - entry) * qty if side == "BUY" else (entry - exit_price) * qty
        if not dry_run:
            db.close_trade(trade["id"], exit_price, pnl, notes="SQUAREOFF")
        log.info(f"SQUAREOFF {sym} @ {exit_price:.2f} pnl={_currency}{pnl:+.2f}")
        tg.send(f"SQUAREOFF {sym} @ {_currency}{exit_price:.2f} | PnL: {'+'if pnl>=0 else ''}{_currency}{pnl:.2f}")


def send_eod_summary(account: str, capital: float, tg: Telegram):
    pnl = db.today_pnl(account)
    pct = pnl / capital * 100
    with db.conn() as c:
        trades = c.execute(
            "SELECT COUNT(*) as n, "
            "SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) as wins, "
            "SUM(CASE WHEN pnl<=0 THEN 1 ELSE 0 END) as losses "
            "FROM trades WHERE account=? AND date(ts)=date('now') AND status='closed'",
            (account,)
        ).fetchone()
    n = trades["n"] or 0
    wins = trades["wins"] or 0
    losses = trades["losses"] or 0
    log.info(f"EOD | trades={n} ({wins}W/{losses}L) pnl={_currency}{pnl:+.2f} ({pct:+.2f}%)")
    tg.send(
        f"EOD Summary — *{account}*\n"
        f"Trades: {n} ({wins}W / {losses}L)\n"
        f"PnL: {'+'if pnl>=0 else ''}{_currency}{pnl:.2f} ({'+'if pct>=0 else ''}{pct:.2f}%)"
    )


def _check_dhan_token(broker, tg: Telegram) -> bool:
    """
    Validates the Dhan access token at startup.
    Dhan tokens expire every 24h — this catches expiry before market open
    and fires a Telegram alert so the user knows to refresh .env.
    Returns True if token is valid, False if expired/invalid.
    """
    from .broker import DhanBroker, PaperBroker
    live = broker.live if isinstance(broker, PaperBroker) else broker
    if not isinstance(live, DhanBroker):
        return True  # paper-only mode with no live broker — skip check

    try:
        resp = live.client.get_fund_limits()
        if resp and resp.get("status") == "success":
            log.info("Dhan token OK")
            return True
        err = str(resp)
        log.error(f"Dhan token check failed: {err}")
        tg.send(
            "TOKEN EXPIRED — bot cannot start.\n"
            "1. Go to https://developer.dhan.co\n"
            "2. Generate a new access token\n"
            "3. Update DHAN_ACCESS_TOKEN in your .env file\n"
            "4. Restart the bot"
        )
        return False
    except Exception as e:
        log.error(f"Dhan token check error: {e}")
        tg.send(f"TOKEN CHECK FAILED: {e}\nUpdate DHAN_ACCESS_TOKEN in .env and restart.")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True)
    ap.add_argument("--loop-seconds", type=float, default=5.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    db.init_db()

    setup_logging(args.account)

    cfg = load_config(args.account)
    check = risk.validate_config(cfg)
    if not check.ok:
        raise SystemExit(f"Config failed risk validation: {check.reason}")

    # Set market timezone from config — all ist_now() calls use this from here on
    global _market_tz, _currency
    _market_tz = pytz.timezone(cfg.get("timezone", "Asia/Kolkata"))
    _currency = "$" if cfg.get("broker", "dhan") == "alpaca" else "Rs"

    tg = Telegram()
    broker = make_broker(cfg)

    # Validate Dhan token only for Dhan broker (Alpaca uses key/secret, no daily refresh)
    if cfg.get("broker", "dhan") == "dhan":
        _token_ok = _check_dhan_token(broker, tg)
        if not _token_ok:
            raise SystemExit("Dhan token invalid or expired — update DHAN_ACCESS_TOKEN in .env")

    enabled = cfg.get("strategies_enabled", [cfg["active_strategy"]])
    strategies = {}
    for name in enabled:
        cls = get_strategy(name)
        strategies[name] = cls(
            cfg["strategy_params"].get(name, {}),
            market_open=str(cfg["market_open"])
        )

    mode_label = "DRY-RUN" if args.dry_run else cfg["mode"].upper()

    # Restore strategy state from today's JSON, or replay from today's log
    state_loaded = load_state(args.account, strategies)
    if not state_loaded:
        replay_from_log(args.account, strategies, str(cfg["market_open"]))

    # If ORB is active and bot started after 9:30, recover opening range from Dhan API
    if "orb" in strategies:
        try:
            init_orb_from_api(broker, strategies["orb"], cfg.get("watchlist", []), ist_now())
        except Exception as e:
            log.warning(f"ORB API init failed (non-fatal): {e}")

    # Load ML scorer once at startup
    ml_scorer = MLScorer(account=args.account)
    candle_builder = CandleBuilder()

    # Load today's scanner watchlist (replaces fixed config watchlist)
    active_watchlist, catalyst_map = load_scanner_watchlist(cfg)

    log.info(f"=== EXECUTOR STARTED | account={args.account} mode={mode_label} ===")
    log.info(f"Strategies: {list(strategies.keys())}")
    log.info(f"Watchlist ({len(active_watchlist)} stocks from scanner): {active_watchlist}")
    log.info(f"max_positions={cfg['max_positions']} capital={_currency}{cfg['capital']}")
    log.info(f"ORB params: {cfg['strategy_params'].get('orb', {})}")
    log.info(f"VWAP params: {cfg['strategy_params'].get('vwap', {})}")
    log.info(f"Market hours: {cfg.get('market_open','09:15')}-{cfg.get('market_close','15:15')} ({cfg.get('timezone','Asia/Kolkata')})")

    tg.send(
        f"Executor up: *{args.account}* | mode=*{mode_label}* | "
        f"strategies=*{','.join(strategies.keys())}* | {len(active_watchlist)} stocks"
    )
    db.log_event(args.account, "INFO", "startup",
                 f"strategies={list(strategies.keys())} mode={mode_label}")

    consecutive_losses = 0
    eod_sent = False
    last_config_mtime = (REPO_ROOT / "config" / "accounts" / f"{args.account}.yaml").stat().st_mtime
    last_watchlist_date = datetime.now(IST).date()
    loop_count = 0
    quotes_history: dict = {}  # {symbol: [ltp, ...]} rolling 30-min buffer for regime detection
    sl_cooldown: dict = {}     # {symbol: datetime} — no new entries on symbol for N min after SL hit
    # Persist refresh timestamps across restarts via a small state file
    _refresh_state_path = REPO_ROOT / "data" / "refresh_state.json"
    def _load_refresh_state():
        try:
            if _refresh_state_path.exists():
                return json.load(open(_refresh_state_path))
        except Exception:
            pass
        return {}
    def _save_refresh_state(state: dict):
        try:
            _refresh_state_path.write_text(json.dumps(state))
        except Exception:
            pass

    _refresh_state = _load_refresh_state()
    last_intraday_refresh = _refresh_state.get("last_intraday_refresh", 0)
    intraday_context: dict = {}  # latest intraday context from Perplexity

    # Load last intraday context from disk if available (survive restarts)
    _intraday_ctx_path = REPO_ROOT / "data" / "intraday_context.json"
    if _intraday_ctx_path.exists():
        try:
            intraday_context = json.loads(_intraday_ctx_path.read_text())
        except Exception:
            pass

    try:
        while True:
            now_ist = ist_now()
            loop_count += 1

            # Hot-reload config
            cfg_path = REPO_ROOT / "config" / "accounts" / f"{args.account}.yaml"
            try:
                mtime = cfg_path.stat().st_mtime
                if mtime != last_config_mtime:
                    cfg = load_config(args.account)
                    last_config_mtime = mtime
                    # Propagate updated strategy params to live strategy objects
                    for sname, strat in strategies.items():
                        new_params = cfg.get("strategy_params", {}).get(sname, {})
                        if new_params and hasattr(strat, "update_params"):
                            strat.update_params(new_params)
                    log.info("CONFIG RELOADED — strategy params updated")
                    db.log_event(args.account, "INFO", "config_reload", "config reloaded")
                    tg.send(f"Config reloaded: {args.account}")
            except Exception as e:
                log.error(f"Config reload error: {e}")

            # Square-off — checked BEFORE market-hours gate so a restart after
            # 15:15 still closes any lingering positions on the first loop tick
            if is_past_market_close(cfg) and not eod_sent:
                log.info("SQUAREOFF — market closed, closing all open positions")
                squareoff_all(args.account, broker, tg, args.dry_run)
                send_eod_summary(args.account, cfg["capital"], tg)
                eod_sent = True
                for strat in strategies.values():
                    strat.reset_for_new_day()
                candle_builder.reset()
                log.info("EOD done. Waiting for next session.")

            # Reset eod_sent at market open so next day works correctly
            _open_h, _open_m = map(int, str(cfg["market_open"]).split(":"))
            if now_ist.hour == _open_h and now_ist.minute == _open_m:
                eod_sent = False

            if not in_market_hours(cfg):
                # Heartbeat every 5 minutes while waiting
                if loop_count % 60 == 1:
                    log.info(f"Outside market hours | {now_ist.strftime('%H:%M:%S IST')} weekday={now_ist.weekday()}")
                time.sleep(args.loop_seconds)
                continue

            # Reload scanner watchlist on new day
            if now_ist.date() != last_watchlist_date:
                active_watchlist, catalyst_map = load_scanner_watchlist(cfg)
                last_watchlist_date = now_ist.date()
                candle_builder.reset()
                log.info(f"Watchlist refreshed for new day: {active_watchlist}")

            # Intraday Perplexity refresh — every 90 min during market hours
            import time as _time
            _now_ts = _time.time()
            _ist_hm = now_ist.hour * 100 + now_ist.minute
            _open_hm = int(str(cfg["market_open"]).replace(":", ""))
            _close_hm = int(str(cfg["market_close"]).replace(":", ""))
            if _open_hm <= _ist_hm <= _close_hm and _now_ts - last_intraday_refresh > 5400:
                try:
                    from perplexity_finance import intraday_refresh
                    intraday_context = intraday_refresh(active_watchlist)
                    last_intraday_refresh = _now_ts
                    _save_refresh_state({"last_intraday_refresh": _now_ts})
                    if intraday_context.get("macro_shock"):
                        log.warning("MACRO SHOCK detected — tightening entry gate")
                    if intraday_context.get("commodity_shock"):
                        log.warning("COMMODITY SHOCK detected — commodity stocks flagged")
                except Exception as _e:
                    log.warning(f"Intraday refresh failed (non-fatal): {_e}")

            # Fetch quotes via REST (Data API subscription required)
            try:
                quotes = broker.get_quotes(active_watchlist)
            except Exception as e:
                log.error(f"get_quotes failed: {e}")
                time.sleep(args.loop_seconds)
                continue

            if not quotes:
                log.warning("get_quotes returned empty — skipping loop")
                time.sleep(args.loop_seconds)
                continue

            # Feed REST quotes into CandleBuilder → ML scorer
            for sym, q in quotes.items():
                if q.ltp > 0:
                    completed = candle_builder.update(sym, q.ltp, q.volume, now_ist.replace(tzinfo=None))
                    if completed:
                        bars = candle_builder.get_all_bars(sym)
                        if len(bars) >= 2:
                            ml_scorer.update(sym, bars[-2])

            log.info(f"QUOTES | {' | '.join(f'{s}={q.ltp:.2f}' for s, q in quotes.items())}")

            # Resolve any blocked signals whose 30-min window has passed
            current_prices = {s: q.ltp for s, q in quotes.items() if q.ltp > 0}
            resolved = db.resolve_blocked_signals(args.account, current_prices)
            for r in resolved:
                outcome = f"{r['hit']} pnl={r['pnl_pct']:+.2f}%"
                log.info(f"FEEDBACK | {r['symbol']} {r['side']} | ml_prob={r['ml_prob']:.3f} "
                         f"catalyst={r['catalyst_score']} | outcome={outcome} "
                         f"(entry={r['entry']:.2f} -> {r['outcome_price']:.2f})")

            # Update rolling price history for regime detection
            # (CandleBuilder + ML scorer are updated from the feed thread via bar_queue)
            for sym, q in quotes.items():
                if q.ltp > 0:
                    buf = quotes_history.setdefault(sym, [])
                    buf.append(q.ltp)
                    if len(buf) > 360:
                        buf.pop(0)

            # Re-detect regime every 30 loops (~2.5 min)
            if loop_count % 30 == 0 and quotes_history:
                try:
                    regime_data = detect_regime(quotes_history, account=args.account)
                    log.info(f"REGIME UPDATED | {regime_data['regime']} | {regime_data['reason']}")
                except Exception as e:
                    log.error(f"Regime detection error: {e}")

            regime = load_regime(account=args.account)
            regime_strats = regime.get("strategies", {})
            pos_size_mult = regime_strats.get("position_size_multiplier", 1.0)

            # Strategist can further reduce size (e.g. high VIX day set 0.5x at premarket)
            try:
                import json as _json
                date_str = now_ist.strftime("%Y%m%d")
                override_path = REPO_ROOT / "data" / f"strategy_override_{date_str}.json"
                if override_path.exists():
                    ov = _json.loads(override_path.read_text())
                    strat_mult = float(ov.get("pos_size_multiplier", 1.0))
                    pos_size_mult = min(pos_size_mult, strat_mult)  # take the more conservative
            except Exception:
                pass

            log.info(f"REGIME | {regime['regime']} | size_mult={pos_size_mult:.1f} | {regime.get('reason', '')}")

            # Monitor exits — returns symbols that hit SL this loop for cooldown tracking
            consecutive_losses, sl_hits_this_loop = check_exits(
                args.account, broker, tg, args.dry_run, consecutive_losses, quotes
            )
            sl_cooldown_minutes = cfg.get("cooldown_after_sl_minutes", 15)
            for sym_hit in sl_hits_this_loop:
                sl_cooldown[sym_hit] = now_ist.replace(tzinfo=None)
                log.info(f"SL COOLDOWN | {sym_hit} blocked for {sl_cooldown_minutes}min (just hit stoploss)")

            # Risk check + current state
            entry_check = risk.can_open_new_position(cfg)
            open_ct = db.open_positions_count(args.account)
            open_by_symbol = db.open_positions_by_symbol(args.account)
            today_pnl = db.today_pnl(args.account)

            # Auto-halt: too many consecutive losses → stop new entries for the day
            halt_threshold = cfg.get("halt_after_consecutive_losses", 3)
            session_halted = consecutive_losses >= halt_threshold

            log.info(
                f"LOOP {loop_count} | {now_ist.strftime('%H:%M:%S')} | "
                f"open={open_ct}/{risk.effective_max_positions(cfg)} | pnl={_currency}{today_pnl:+.2f} | "
                f"sl_streak={consecutive_losses} | "
                f"{'HALTED' if session_halted else ('entry=OK' if entry_check.ok else 'entry=BLOCKED: ' + entry_check.reason)}"
            )

            if session_halted:
                if loop_count % 60 == 0:
                    log.warning(f"SESSION HALTED | {consecutive_losses} consecutive SLs — no new entries today")
                    tg.send(f"SESSION HALTED — {consecutive_losses} consecutive SLs. Monitoring exits only.")
                save_state(args.account, strategies)
                time.sleep(args.loop_seconds)
                continue

            for sym in active_watchlist:
                q = quotes.get(sym)
                if not q:
                    log.warning(f"QUOTE {sym} missing from batch response")
                    continue

                if q.ltp <= 0:
                    log.warning(f"QUOTE {sym} ltp=0 — skipping (data issue?)")
                    continue

                # Always process ticks through ALL strategies so their internal state stays
                # current — needed for confluence checks even when regime deactivates a strategy
                raw_signals = {}
                for strat_name, strat in strategies.items():
                    try:
                        if strat_name == "vwap":
                            s = strat.on_tick(
                                sym, q.ltp, getattr(q, 'volume', 0),
                                now_ist.replace(tzinfo=None),
                                position_open=open_ct >= risk.effective_max_positions(cfg)
                            )
                        else:
                            s = strat.on_tick(
                                sym, q.ltp,
                                now_ist.replace(tzinfo=None),
                                position_open=open_ct >= risk.effective_max_positions(cfg)
                            )
                        if s:
                            raw_signals[strat_name] = s
                    except Exception as e:
                        log.error(f"STRATEGY {strat_name} error on {sym}: {e}")
                        log.error(traceback.format_exc())

                sig = None
                fired_strategy = None
                for strat_name, raw_sig in raw_signals.items():
                    strat_regime_cfg = regime_strats.get(strat_name, {})

                    # Block if regime deactivated this strategy
                    if not strat_regime_cfg.get("active", True):
                        log.debug(f"REGIME SKIP | {strat_name} signal blocked in {regime['regime']} for {sym}")
                        continue

                    # Block direction against regime rules
                    if raw_sig.action == "SELL" and not strat_regime_cfg.get("allow_short", True):
                        log.info(f"REGIME FILTER | SELL {sym} blocked — no shorts in {regime['regime']}")
                        continue
                    if raw_sig.action == "BUY" and not strat_regime_cfg.get("allow_long", True):
                        log.info(f"REGIME FILTER | BUY {sym} blocked — no longs in {regime['regime']}")
                        continue

                    # Signal confluence: VWAP signals require EMA trend confirmation
                    if strat_name == "vwap" and "ema" in strategies:
                        ema_strat = strategies["ema"]
                        fast = ema_strat._fast_ema.get(sym, 0)
                        slow = ema_strat._slow_ema.get(sym, 0)
                        candles = len(ema_strat._candles.get(sym, []))
                        if candles >= ema_strat.slow_period and fast > 0 and slow > 0:
                            if raw_sig.action == "BUY" and fast < slow:
                                log.info(f"CONFLUENCE REJECT | {sym} VWAP BUY but EMA bearish "
                                         f"(fast={fast:.2f} slow={slow:.2f})")
                                continue
                            if raw_sig.action == "SELL" and fast > slow:
                                log.info(f"CONFLUENCE REJECT | {sym} VWAP SELL but EMA bullish "
                                         f"(fast={fast:.2f} slow={slow:.2f})")
                                continue
                            log.debug(f"CONFLUENCE OK | {sym} VWAP {raw_sig.action} confirmed by EMA "
                                      f"(fast={fast:.2f} slow={slow:.2f})")

                    sig = raw_sig
                    fired_strategy = strat_name
                    break

                if not sig:
                    continue

                # Cross-strategy SL cooldown — don't re-enter a symbol that just hit stoploss
                if sym in sl_cooldown:
                    elapsed_min = (now_ist.replace(tzinfo=None) - sl_cooldown[sym]).total_seconds() / 60
                    cooldown_min = cfg.get("cooldown_after_sl_minutes", 15)
                    if elapsed_min < cooldown_min:
                        log.info(f"SL COOLDOWN | {sym} {sig.action} blocked — {cooldown_min - elapsed_min:.0f}min remaining after stoploss")
                        sig = None
                        continue
                    else:
                        del sl_cooldown[sym]  # cooldown expired, clean up

                log.info(f"SIGNAL {sig.action} {sym} @ {sig.price:.2f} sl={sig.stoploss:.2f} tgt={sig.target:.2f} | {sig.reason}")

                # Block conflicting position — no opposing trades on same symbol across any strategy
                existing_side = open_by_symbol.get(sym)
                if existing_side and existing_side != sig.action:
                    log.warning(f"SIGNAL BLOCKED | {sym}: already {existing_side}, refusing opposite {sig.action} (conflict between strategies)")
                    db.log_event(args.account, "INFO", "signal_blocked_conflict",
                                 f"{sym}: open={existing_side} new={sig.action}")
                    continue

                # Also block if already long/short on this symbol (no doubling up)
                if existing_side and existing_side == sig.action:
                    log.warning(f"SIGNAL BLOCKED | {sym}: already {existing_side}, no doubling up")
                    continue

                # Sector correlation check — no two stocks from same sector open simultaneously
                conflict, conflict_reason = has_sector_conflict(sym, open_by_symbol)
                if conflict:
                    log.warning(f"SIGNAL BLOCKED | sector conflict: {conflict_reason}")
                    db.log_event(args.account, "INFO", "signal_blocked_sector", conflict_reason)
                    continue

                # ── Filter 0: Intraday macro/commodity shock gate ──────────
                if intraday_context.get("macro_shock"):
                    log.info(f"MACRO SHOCK GATE | {sym} blocked — macro shock active")
                    continue
                if intraday_context.get("commodity_shock"):
                    commodity_syms = {"VEDL", "COALINDIA", "ONGC", "BPCL", "GAIL",
                                      "SAIL", "TATASTEEL", "JSWSTEEL", "HINDALCO", "ADANIENT"}
                    if sym in commodity_syms:
                        log.info(f"COMMODITY SHOCK GATE | {sym} blocked — commodity shock active")
                        continue
                if sym in intraday_context.get("symbol_alerts", {}):
                    log.info(f"SYMBOL ALERT GATE | {sym} blocked — breaking news: "
                             f"{intraday_context['symbol_alerts'][sym][:60]}")
                    continue

                # ── Filter 1: Catalyst direction conflict ──────────────────
                # Don't go LONG when catalyst says SHORT and vice versa
                cat_direction = catalyst_map.get(sym, {}).get("direction", "NEUTRAL")
                if cat_direction == "SHORT" and sig.action == "BUY":
                    log.info(f"CATALYST CONFLICT | {sym} BUY blocked — catalyst says SHORT")
                    db.log_event(args.account, "INFO", "signal_blocked_catalyst",
                                 f"{sym}: BUY vs SHORT catalyst")
                    continue
                if cat_direction == "LONG" and sig.action == "SELL":
                    log.info(f"CATALYST CONFLICT | {sym} SELL blocked — catalyst says LONG")
                    db.log_event(args.account, "INFO", "signal_blocked_catalyst",
                                 f"{sym}: SELL vs LONG catalyst")
                    continue

                # ── Filter 2: RSI extreme gate ─────────────────────────────
                # No BUY when RSI >= 75 (overbought), no SELL when RSI <= 25 (oversold)
                buf = ml_scorer._bars.get(sym, [])
                if len(buf) >= 14:
                    from ml.features import compute_rsi
                    import pandas as pd
                    closes = pd.Series([b["close"] for b in buf])
                    rsi_val = float(compute_rsi(closes, 14).iloc[-1])
                    rsi_buy_block  = cfg.get("rsi_buy_block", 75)
                    rsi_sell_block = cfg.get("rsi_sell_block", 25)
                    if sig.action == "BUY" and rsi_val >= rsi_buy_block:
                        log.info(f"RSI GATE | {sym} BUY blocked — RSI={rsi_val:.1f} >= {rsi_buy_block} (overbought)")
                        db.log_event(args.account, "INFO", "signal_blocked_rsi",
                                     f"{sym}: BUY at RSI={rsi_val:.1f}")
                        continue
                    if sig.action == "SELL" and rsi_val <= rsi_sell_block:
                        log.info(f"RSI GATE | {sym} SELL blocked — RSI={rsi_val:.1f} <= {rsi_sell_block} (oversold)")
                        db.log_event(args.account, "INFO", "signal_blocked_rsi",
                                     f"{sym}: SELL at RSI={rsi_val:.1f}")
                        continue

                # ── Filter 3: Per-symbol SL cooldown (90 min after loss) ───
                # Already handled by sl_cooldown dict — extended to 90 min via config
                if not entry_check.ok:
                    log.warning(f"SIGNAL BLOCKED | {sym}: {entry_check.reason}")
                    db.log_event(args.account, "INFO", "signal_skipped", f"{sym}: {entry_check.reason}")
                    continue

                qty = risk.position_size(cfg, sig.price)
                if pos_size_mult != 1.0:
                    qty = max(1, int(qty * pos_size_mult))
                _budget = cfg.get("max_position_size") or cfg.get("max_position_size_inr", 0)
                log.info(f"POSITION SIZE | budget={_budget} price={sig.price:.2f} qty={qty} regime_mult={pos_size_mult:.1f}")

                if qty <= 0:
                    log.warning(f"SKIP {sym} | qty=0 (price too high for position size)")
                    db.log_event(args.account, "WARN", "qty_zero", f"{sym}: price too high")
                    continue

                # Minimum reward:risk ratio check
                potential_gain = abs(sig.target - sig.price)
                potential_loss = abs(sig.price - sig.stoploss)
                rr = potential_gain / potential_loss if potential_loss > 0 else 0
                min_rr = cfg.get("min_rr_ratio", 1.0)
                if rr < min_rr:
                    log.warning(f"SKIP {sym} | R:R={rr:.2f} below minimum {min_rr:.1f} (gain={potential_gain:.2f} risk={potential_loss:.2f})")
                    continue

                # ML gate — score signal through model before placing
                direction = "long" if sig.action == "BUY" else "short"
                catalyst_info = catalyst_map.get(sym, {})
                catalyst_score = catalyst_info.get("catalyst_score", 5)
                ml_prob, ml_ok, ml_features = ml_scorer.score(sym, direction, catalyst_score)
                if not cfg.get("use_ml", True):
                    ml_ok = True  # bypass ML gate — use strategy + regime filter only

                # Filter 1 — Regime-bias: block counter-trend trades when market has direction.
                # avg_move > +0.15% = market drifting up → don't short (SELL).
                # avg_move < -0.15% = market drifting down → don't buy (BUY).
                if ml_ok:
                    avg_move_pct = regime.get("avg_move_pct", 0.0)
                    is_counter_trend = (
                        (sig.action == "SELL" and avg_move_pct > 0.15) or
                        (sig.action == "BUY"  and avg_move_pct < -0.15)
                    )
                    if is_counter_trend:
                        ml_ok = False
                        log.info(f"REGIME BLOCKED | {sym} {sig.action} "
                                 f"counter-trend (avg_move={avg_move_pct:+.2f}%)")

                # Filter 2 — Stock character filters based on bars_above_vwap.
                # 160-trade analysis:
                #   BUY  + bars_above < 45%     → 31% WR (54 trades) — stock downtrending, skip
                #   SELL + bars_above 30-55%    → 0%  WR (12 trades) — no conviction zone, skip
                #   SELL + bars_above <30% or >55% → 48-57% WR — allowed
                if ml_ok:
                    bars_above = ml_features.get("bars_above_vwap_pct", 50) if ml_features else 50
                    if sig.action == "BUY" and bars_above < 45:
                        ml_ok = False
                        log.info(f"VWAP-BIAS BLOCKED | {sym} BUY "
                                 f"bars_above={bars_above:.0f}% (stock bearish, skip long)")
                    elif sig.action == "SELL" and 30 <= bars_above < 55:
                        ml_ok = False
                        log.info(f"VWAP-BIAS BLOCKED | {sym} SELL "
                                 f"bars_above={bars_above:.0f}% (no conviction zone, 0% WR in 160 trades)")

                # Filter 3 — Time cutoff: stop new entries after configured hour.
                # India default 13 (13:00 IST) — 160-trade analysis showed 29% WR after.
                # US default 15 (15:00 ET) — 1 hour before close.
                if ml_ok:
                    entry_hour = now_ist.hour
                    entry_min  = now_ist.minute
                    cutoff_hour = cfg.get("entry_cutoff_hour", 13)
                    if entry_hour >= cutoff_hour:
                        ml_ok = False
                        log.info(f"TIME BLOCKED | {sym} {sig.action} "
                                 f"past {cutoff_hour}:00 cutoff ({entry_hour}:{entry_min:02d})")

                if not ml_ok:
                    log.info(f"ML BLOCKED | {sym} {sig.action} prob={ml_prob:.3f} catalyst={catalyst_score} — skipping")
                    db.log_event(args.account, "INFO", "ml_blocked",
                                 f"{sym} {sig.action} prob={ml_prob:.3f} catalyst={catalyst_score}")
                    # Log for feedback loop — check outcome in 30 min
                    from datetime import timedelta
                    resolve_at = (datetime.now(IST) + timedelta(minutes=30)).isoformat()
                    db.record_blocked_signal(
                        account=args.account, symbol=sym,
                        side=sig.action,
                        entry_price=sig.price, stoploss=sig.stoploss, target=sig.target,
                        strategy=strat_name, ml_prob=ml_prob, catalyst_score=catalyst_score,
                        resolve_after_iso=resolve_at,
                    )
                    continue

                if args.dry_run:
                    log.info(f"DRY-RUN | {sig.action} {qty} {sym} @ {sig.price:.2f}")
                    db.log_event(args.account, "INFO", "dry_run_signal",
                                 f"{sig.action} {qty} {sym} @ {sig.price:.2f}")
                    tg.send(
                        f"[DRY] {sig.action} {qty} *{sym}* @ {_currency}{sig.price:.2f}\n"
                        f"SL {_currency}{sig.stoploss:.2f} / TGT {_currency}{sig.target:.2f}"
                    )
                    continue

                log.info(f"PLACING ORDER | {sig.action} {qty} {sym}")
                res = broker.place_market(sym, sig.action, qty)
                log.info(f"ORDER RESULT | status={res.status} fill={res.fill_price:.2f} id={res.order_id}")

                if res.status != "filled":
                    log.error(f"ORDER FAILED | {sym}: {res.message}")
                    fire_floor_manager("EXECUTION_ERROR",
                                       {"symbol": sym, "side": sig.action, "result": str(res)}, tg)
                    continue

                # Build signal features snapshot for ML training data
                # ml_features contains all 14 FEATURE_COLS values for retraining
                signal_features = {
                    "ts": now_ist.isoformat(),
                    "strategy": fired_strategy,
                    "ml_prob": round(ml_prob, 4),
                    "catalyst_score": catalyst_score,
                    "catalyst_direction": catalyst_info.get("direction", "NEUTRAL"),
                    "catalyst_reason": catalyst_info.get("reason", ""),
                    "regime": regime.get("regime"),
                    "regime_avg_move_pct": regime.get("avg_move_pct"),
                    "price": sig.price,
                    "stoploss_pct": round(abs(sig.price - sig.stoploss) / sig.price * 100, 3),
                    "target_pct": round(abs(sig.target - sig.price) / sig.price * 100, 3),
                    "rr_ratio": round(rr, 3),
                    "open_positions_before": open_ct,
                    "today_pnl_before": round(today_pnl, 2),
                    "consecutive_losses": consecutive_losses,
                    "volume": getattr(q, "volume", 0),
                    "reason": sig.reason,
                    "ml_features": ml_features,  # full 14-feature vector for retraining
                }
                # Attach market context (VIX, FII) if available from premarket
                try:
                    import json as _json
                    ctx_path = REPO_ROOT / "data" / f"market_context_{args.account}.json"
                    if ctx_path.exists():
                        ctx = _json.loads(ctx_path.read_text())
                        signal_features["vix"] = ctx.get("vix")
                        signal_features["fii_net_cr"] = ctx.get("fii_net_cr")
                        signal_features["global_bias"] = ctx.get("global_bias")
                        signal_features["stock_sentiment"] = ctx.get("sentiments", {}).get(sym)
                except Exception:
                    pass

                try:
                    db.record_trade(
                        account=args.account,
                        mode=cfg["mode"],
                        symbol=sym,
                        side=sig.action,
                        qty=qty,
                        entry_price=res.fill_price,
                        stoploss=sig.stoploss,
                        target=sig.target,
                        strategy=fired_strategy or cfg.get("strategies_enabled", ["orb"])[0],
                        broker_order_id=res.order_id,
                        signal_features=signal_features,
                    )
                except ValueError as e:
                    log.error(f"TRADE NOT RECORDED | {sym}: {e}")
                    continue
                open_ct += 1
                # Tell strategy the trade was placed so it starts cooldown now (not when signal was generated)
                strat_obj = strategies.get(fired_strategy)
                if strat_obj and hasattr(strat_obj, "notify_traded"):
                    strat_obj.notify_traded(sym, now_ist.replace(tzinfo=None))
                log.info(f"TRADE ENTERED | {sig.action} {qty} {sym} @ {res.fill_price:.2f} | open_ct={open_ct}")
                tg.send(
                    f"ENTRY {sig.action} {qty} *{sym}* @ {_currency}{res.fill_price:.2f}\n"
                    f"SL {_currency}{sig.stoploss:.2f} / TGT {_currency}{sig.target:.2f}\n"
                    f"{sig.reason}"
                )

            save_state(args.account, strategies)
            time.sleep(args.loop_seconds)

    except KeyboardInterrupt:
        tg.send(f"Executor stopped: *{args.account}*")
        log.info("Executor stopped by user.")


if __name__ == "__main__":
    main()

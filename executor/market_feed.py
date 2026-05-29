"""Dhan WebSocket market feed.

Replaces the REST quote_data API (requires paid Data APIs subscription)
with DhanFeed WebSocket (free with any Dhan trading account).

Architecture:
- Runs in a background daemon thread
- Feeds ticks into CandleBuilder for real 1-min OHLCV bars
- Pushes completed bars onto a queue for the ML scorer
- Main executor loop reads quotes and drains the bar queue

Fallback: if WebSocket goes down, executor falls back to the candle
builder's last known data (stale but better than crashing).
"""
import json
import logging
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import pytz

from .broker import Quote
from .candle_builder import CandleBuilder

log = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

_IDS_PATH = Path(__file__).parent.parent / "data" / "nifty100_security_ids.json"
NSE_SECURITY_IDS: dict = json.loads(_IDS_PATH.read_text()) if _IDS_PATH.exists() else {}
SID_TO_SYMBOL: dict = {str(v): k for k, v in NSE_SECURITY_IDS.items()}


class MarketFeed:
    """
    Real-time WebSocket feed for all watchlist symbols.
    Free with Dhan trading account — no Data APIs subscription needed.

    Usage:
        feed = MarketFeed(client_id, access_token)
        feed.start(symbols, candle_builder, completed_bar_queue)
        ...
        quotes = feed.get_quotes(symbols)   # in main loop
    """

    def __init__(self, client_id: str, access_token: str):
        self.client_id = client_id
        self.access_token = access_token
        self._lock = threading.Lock()
        self._raw: dict = {}        # {symbol: {ltp, atp, volume, high, low, open, ts}}
        self._connected = False
        self._last_tick_ts = 0.0
        self._symbols: list = []
        self._candle_builder: CandleBuilder | None = None
        self._bar_queue: queue.Queue | None = None
        self._thread: threading.Thread | None = None

    def start(self, symbols: list, candle_builder: CandleBuilder,
              bar_queue: queue.Queue):
        self._symbols = symbols
        self._candle_builder = candle_builder
        self._bar_queue = bar_queue
        self._thread = threading.Thread(
            target=self._run_forever, name="DhanFeed", daemon=True
        )
        self._thread.start()
        log.info(f"MarketFeed thread started — {len(symbols)} symbols")

    # ── Thread entry point ────────────────────────────────────────────────

    def _run_forever(self):
        delay = 10
        while True:
            try:
                self._connect()
                delay = 10  # reset backoff on clean exit
            except Exception as e:
                err = str(e)
                if "429" in err:
                    delay = min(delay * 2, 300)  # 429 = rate limited, back off hard
                    log.error(f"MarketFeed error: {e} — rate limited, reconnecting in {delay}s")
                else:
                    delay = min(delay * 2, 120)
                    log.error(f"MarketFeed error: {e} — reconnecting in {delay}s")
            self._connected = False
            time.sleep(delay)

    def _connect(self):
        import asyncio
        # Python 3.10+ doesn't auto-create event loops in background threads
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            from dhanhq import marketfeed
        except ImportError:
            log.error("dhanhq not installed — cannot start MarketFeed")
            time.sleep(60)
            return

        instruments = []
        for sym in self._symbols:
            sid = NSE_SECURITY_IDS.get(sym)
            if sid:
                instruments.append((marketfeed.NSE, str(sid), marketfeed.Quote))
            else:
                log.warning(f"MarketFeed: no security ID for {sym} — skipping")

        if not instruments:
            log.error("MarketFeed: no valid instruments to subscribe")
            time.sleep(60)
            return

        # Don't connect before 9:00 AM IST — Dhan rejects WebSocket before pre-open
        now_ist = datetime.now(IST)
        if now_ist.hour < 9:
            wait = (9 * 60 - now_ist.hour * 60 - now_ist.minute) * 60
            log.info(f"MarketFeed: waiting {wait//60}min until 09:00 IST before connecting")
            time.sleep(wait)

        log.info(f"MarketFeed: connecting ({len(instruments)} instruments)")
        feed = marketfeed.DhanFeed(
            client_id=self.client_id,
            access_token=self.access_token,
            instruments=instruments,
            version="v2",
        )
        # run_forever() connects + subscribes, then returns (non-blocking after handshake)
        feed.run_forever()
        self._connected = True
        log.info("MarketFeed: WebSocket connected, polling for ticks")

        # Poll loop — get_data() blocks until next tick arrives from the server
        while True:
            tick = feed.get_data()
            if tick:
                self._on_ticks(tick)

    # ── Tick handler (runs in feed thread) ────────────────────────────────

    def _on_ticks(self, tick):
        now = datetime.now(IST).replace(tzinfo=None)
        self._last_tick_ts = time.time()

        try:
            sid = str(tick.get("security_id", ""))
            sym = SID_TO_SYMBOL.get(sid)
            if not sym:
                return
            ltp = float(tick.get("LTP", 0))   # comes as string "1234.56" from API
            if ltp <= 0:
                return
            atp = float(tick.get("avg_price", ltp))  # avg_price = intraday VWAP from Dhan
            vol = int(tick.get("volume", 0))

            with self._lock:
                self._raw[sym] = {
                    "ltp": ltp, "atp": atp, "volume": vol,
                    "high": float(tick.get("high", ltp)),
                    "low":  float(tick.get("low",  ltp)),
                    "open": float(tick.get("open", ltp)),
                    "ts":   self._last_tick_ts,
                }

            # Feed candle builder; push completed bar to queue for ML scorer
            if self._candle_builder is not None:
                completed = self._candle_builder.update(sym, ltp, vol, now)
                if completed and self._bar_queue is not None:
                    bars = self._candle_builder.get_all_bars(sym)
                    if len(bars) >= 2:
                        self._bar_queue.put_nowait((sym, bars[-2]))

        except Exception as e:
            log.debug(f"MarketFeed tick error: {e}")

    # ── Public API (called from main executor thread) ─────────────────────

    def get_quotes(self, symbols: list) -> dict:
        """
        Returns {symbol: Quote} for all symbols with fresh data.
        Same format as broker.get_quotes() so executor needs no logic change.
        """
        with self._lock:
            out = {}
            for sym in symbols:
                raw = self._raw.get(sym)
                if raw:
                    out[sym] = Quote(
                        symbol=sym,
                        ltp=raw["ltp"],
                        bid=raw["ltp"],
                        ask=raw["ltp"],
                        volume=raw["volume"],
                        ts=raw["ts"],
                    )
            return out

    @property
    def is_live(self) -> bool:
        """True if we got a tick in the last 30 seconds."""
        return self._connected and (time.time() - self._last_tick_ts) < 30

    @property
    def staleness_s(self) -> float:
        return time.time() - self._last_tick_ts if self._last_tick_ts > 0 else 9999

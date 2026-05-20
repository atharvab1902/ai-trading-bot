"""Broker adapter. Wraps Dhan API; also provides a paper-trading stub."""
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

log = logging.getLogger(__name__)


@dataclass
class Quote:
    symbol: str
    ltp: float
    bid: float
    ask: float
    volume: int
    ts: float


@dataclass
class OrderResult:
    order_id: str
    status: str  # filled | rejected | pending
    fill_price: float
    message: str = ""


class Broker(ABC):
    @abstractmethod
    def get_quote(self, symbol: str) -> Quote: ...

    @abstractmethod
    def get_quotes(self, symbols: List[str]) -> Dict[str, Quote]: ...

    @abstractmethod
    def place_market(self, symbol: str, side: str, qty: int) -> OrderResult: ...

    @abstractmethod
    def place_limit(self, symbol: str, side: str, qty: int, price: float) -> OrderResult: ...

    @abstractmethod
    def cancel(self, order_id: str) -> bool: ...

    @abstractmethod
    def get_positions(self) -> list: ...


class PaperBroker(Broker):
    """Paper trading — real quotes from live broker, simulated fills."""

    def __init__(self, live_broker: Broker = None, slippage_pct: float = 0.05):
        self.live = live_broker
        self.slippage_pct = slippage_pct
        self._orders = {}
        self._positions = {}
        self._seq = 0
        self._cache: Dict[str, Quote] = {}  # last known quotes, avoids extra API calls

    def get_quote(self, symbol: str) -> Quote:
        # Use cache if fresh (within 30s) to avoid extra API calls
        cached = self._cache.get(symbol)
        if cached and (time.time() - cached.ts) < 30:
            return cached
        if self.live:
            q = self.live.get_quote(symbol)
            self._cache[symbol] = q
            return q
        return Quote(symbol, 100.0, 99.95, 100.05, 0, time.time())

    def get_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        if self.live:
            quotes = self.live.get_quotes(symbols)
            self._cache.update(quotes)  # keep cache fresh after every batch
            return quotes
        return {s: Quote(s, 100.0, 99.95, 100.05, 0, time.time()) for s in symbols}

    def _fill_price(self, quote: Quote, side: str) -> float:
        slip = quote.ltp * self.slippage_pct / 100
        return quote.ltp + slip if side == "BUY" else quote.ltp - slip

    def place_market(self, symbol: str, side: str, qty: int) -> OrderResult:
        self._seq += 1
        order_id = f"PAPER-{self._seq}"
        # Prefer fresh cache from the main loop's batch get_quotes() call
        q = self._cache.get(symbol)
        if q is None or q.ltp <= 0:
            q = self.get_quote(symbol)
        if q is None or q.ltp <= 0:
            log.error(f"PAPER ORDER REJECTED | {symbol} {side} — no valid quote, refusing fill at 0")
            return OrderResult(order_id, "rejected", 0.0, "no valid quote")
        price = self._fill_price(q, side)
        self._orders[order_id] = {"symbol": symbol, "side": side, "qty": qty, "price": price}
        return OrderResult(order_id, "filled", price)

    def place_limit(self, symbol: str, side: str, qty: int, price: float) -> OrderResult:
        return self.place_market(symbol, side, qty)

    def cancel(self, order_id: str) -> bool:
        return self._orders.pop(order_id, None) is not None

    def get_positions(self) -> list:
        return list(self._positions.values())


# Load all 97 Nifty security IDs from the data file
import json as _json
_IDS_PATH = Path(__file__).parent.parent / "data" / "nifty100_security_ids.json"
NSE_SECURITY_IDS: dict = _json.loads(_IDS_PATH.read_text()) if _IDS_PATH.exists() else {}


class DhanBroker(Broker):
    """Real Dhan integration using dhanhq SDK."""

    def __init__(self, client_id: str, access_token: str):
        from dhanhq import dhanhq
        self.client = dhanhq(client_id, access_token)

    def _security_id(self, symbol: str) -> int:
        sid = NSE_SECURITY_IDS.get(symbol.upper())
        if not sid:
            raise ValueError(f"No security ID for {symbol}. Add it to NSE_SECURITY_IDS in broker.py.")
        return sid

    def _parse_nse_data(self, resp: dict) -> dict:
        """Extract NSE_EQ dict from Dhan response. Path: resp.data.data.NSE_EQ"""
        return resp.get("data", {}).get("data", {}).get("NSE_EQ", {})

    def get_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        """Fetch all symbols in ONE API call to avoid rate limiting."""
        sids = {s: self._security_id(s) for s in symbols}
        resp = None
        for attempt in range(3):
            resp = self.client.quote_data({"NSE_EQ": list(sids.values())})
            if resp.get("status") == "success":
                break
            log.error(f"quote_data batch failed (attempt {attempt+1}/3): {resp}")
            if attempt < 2:
                time.sleep(2 ** attempt)  # 1s then 2s backoff

        if not resp or resp.get("status") != "success":
            return {}

        nse_data = self._parse_nse_data(resp)
        if not nse_data:
            log.error(f"quote_data: empty NSE_EQ in response: {resp}")
            return {}

        quotes = {}
        for sym, sid in sids.items():
            data = nse_data.get(str(sid), {})
            if not data:
                log.warning(f"No data for {sym} (sid={sid}) in batch response")
                continue
            ltp = float(data.get("last_price", 0))
            quotes[sym] = Quote(
                symbol=sym,
                ltp=ltp,
                bid=float(data.get("buy_quantity", ltp) and data.get("depth", {}).get("buy", [{}])[0].get("price", ltp) or ltp),
                ask=float(data.get("depth", {}).get("sell", [{}])[0].get("price", ltp) or ltp),
                volume=int(data.get("volume", 0)),
                ts=time.time(),
            )
            log.debug(f"QUOTE {sym} | ltp={ltp:.2f} vol={data.get('volume', 0)}")

        return quotes

    def get_quote(self, symbol: str) -> Quote:
        """Single symbol quote. Prefer get_quotes() for multiple symbols."""
        quotes = self.get_quotes([symbol])
        if symbol in quotes:
            return quotes[symbol]
        return Quote(symbol, 0.0, 0.0, 0.0, 0, time.time())

    def place_market(self, symbol: str, side: str, qty: int) -> OrderResult:
        from dhanhq import dhanhq as dhan_const
        sid = self._security_id(symbol)
        resp = self.client.place_order(
            security_id=str(sid),
            exchange_segment=dhan_const.NSE,
            transaction_type=dhan_const.BUY if side == "BUY" else dhan_const.SELL,
            quantity=qty,
            order_type=dhan_const.MARKET,
            product_type=dhan_const.INTRA,
            price=0,
        )
        order_id = resp.get("data", {}).get("orderId", "")
        status = "filled" if resp.get("status") == "success" else "rejected"
        fill_price = resp.get("data", {}).get("price", 0)
        return OrderResult(order_id, status, float(fill_price), str(resp.get("remarks", "")))

    def place_limit(self, symbol: str, side: str, qty: int, price: float) -> OrderResult:
        from dhanhq import dhanhq as dhan_const
        sid = self._security_id(symbol)
        resp = self.client.place_order(
            security_id=str(sid),
            exchange_segment=dhan_const.NSE,
            transaction_type=dhan_const.BUY if side == "BUY" else dhan_const.SELL,
            quantity=qty,
            order_type=dhan_const.LIMIT,
            product_type=dhan_const.INTRA,
            price=price,
        )
        order_id = resp.get("data", {}).get("orderId", "")
        status = "filled" if resp.get("status") == "success" else "rejected"
        return OrderResult(order_id, status, price, str(resp.get("remarks", "")))

    def cancel(self, order_id: str) -> bool:
        resp = self.client.cancel_order(order_id)
        return resp.get("status") == "success"

    def get_positions(self) -> list:
        resp = self.client.get_positions()
        return resp.get("data", [])


def make_broker(cfg: dict) -> Broker:
    mode = cfg.get("mode", "paper")
    client_id = os.environ.get("DHAN_CLIENT_ID", "")
    token = os.environ.get("DHAN_ACCESS_TOKEN", "")

    if mode == "paper":
        if client_id and token:
            live = DhanBroker(client_id, token)
            return PaperBroker(live_broker=live)
        return PaperBroker(live_broker=None)

    if mode == "live":
        if not client_id or not token:
            raise EnvironmentError("DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN required for live mode")
        return DhanBroker(client_id, token)

    raise ValueError(f"Unknown mode: {mode}")

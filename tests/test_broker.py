"""Tests for executor/broker.py."""
import pytest
from unittest.mock import MagicMock, patch
from executor.broker import PaperBroker, Quote, OrderResult, make_broker


def _make_quote(symbol="TSLA", ltp=400.0):
    return Quote(symbol=symbol, ltp=ltp, bid=ltp - 0.1, ask=ltp + 0.1, volume=1000, ts=0.0)


class MockLiveBroker:
    def get_quote(self, symbol):
        return _make_quote(symbol)

    def get_quotes(self, symbols):
        return {s: _make_quote(s) for s in symbols}

    def place_market(self, symbol, side, qty):
        return OrderResult("mock_id", "filled", 400.0)

    def place_limit(self, symbol, side, qty, price):
        return OrderResult("mock_id", "filled", price)

    def cancel(self, order_id):
        return True

    def get_positions(self):
        return []


# ── PaperBroker ───────────────────────────────────────────────────────────────

def test_paper_broker_buy_returns_filled():
    broker = PaperBroker(live_broker=MockLiveBroker(), slippage_pct=0.05)
    result = broker.place_market("TSLA", "BUY", 10)
    assert result.status == "filled"
    assert result.fill_price > 0


def test_paper_broker_sell_returns_filled():
    broker = PaperBroker(live_broker=MockLiveBroker(), slippage_pct=0.05)
    result = broker.place_market("TSLA", "SELL", 10)
    assert result.status == "filled"


def test_paper_broker_buy_slippage_increases_price():
    broker = PaperBroker(live_broker=MockLiveBroker(), slippage_pct=0.05)
    result = broker.place_market("TSLA", "BUY", 10)
    assert result.fill_price >= 400.0


def test_paper_broker_sell_slippage_decreases_price():
    broker = PaperBroker(live_broker=MockLiveBroker(), slippage_pct=0.05)
    result = broker.place_market("TSLA", "SELL", 10)
    assert result.fill_price <= 400.0


def test_paper_broker_get_quote():
    broker = PaperBroker(live_broker=MockLiveBroker())
    q = broker.get_quote("TSLA")
    assert q.symbol == "TSLA"
    assert q.ltp == 400.0


def test_paper_broker_get_quotes():
    broker = PaperBroker(live_broker=MockLiveBroker())
    quotes = broker.get_quotes(["TSLA", "AAPL"])
    assert "TSLA" in quotes
    assert "AAPL" in quotes


def test_paper_broker_cancel_known_order():
    broker = PaperBroker(live_broker=MockLiveBroker(), slippage_pct=0.05)
    result = broker.place_market("TSLA", "BUY", 10)
    assert broker.cancel(result.order_id) is True


def test_paper_broker_cancel_unknown_order_returns_false():
    broker = PaperBroker(live_broker=MockLiveBroker())
    assert broker.cancel("nonexistent_order") is False


def test_paper_broker_get_positions_initially_empty():
    broker = PaperBroker(live_broker=MockLiveBroker())
    assert broker.get_positions() == []


# ── make_broker ───────────────────────────────────────────────────────────────

def test_make_broker_dhan_paper(monkeypatch):
    monkeypatch.setenv("DHAN_CLIENT_ID", "test_client")
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "test_token")
    with patch("executor.broker.DhanBroker") as mock_cls:
        mock_cls.return_value = MagicMock()
        broker = make_broker({"broker": "dhan", "mode": "paper"})
    assert isinstance(broker, PaperBroker)


def test_make_broker_dhan_paper_no_creds_still_works(monkeypatch):
    """Paper mode with no Dhan credentials returns PaperBroker with no live feed."""
    monkeypatch.delenv("DHAN_CLIENT_ID", raising=False)
    monkeypatch.delenv("DHAN_ACCESS_TOKEN", raising=False)
    broker = make_broker({"broker": "dhan", "mode": "paper"})
    assert isinstance(broker, PaperBroker)


def test_make_broker_dhan_live_missing_creds_raises(monkeypatch):
    """Live Dhan mode with no credentials must raise."""
    monkeypatch.delenv("DHAN_CLIENT_ID", raising=False)
    monkeypatch.delenv("DHAN_ACCESS_TOKEN", raising=False)
    with pytest.raises(EnvironmentError):
        make_broker({"broker": "dhan", "mode": "live"})


def test_make_broker_alpaca_paper(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "test_key")
    monkeypatch.setenv("ALPACA_API_SECRET", "test_secret")
    with patch("alpaca.trading.client.TradingClient", MagicMock()), \
         patch("alpaca.data.historical.StockHistoricalDataClient", MagicMock()):
        broker = make_broker({"broker": "alpaca", "mode": "paper"})
    from executor.broker import AlpacaBroker
    assert isinstance(broker, AlpacaBroker)


def test_make_broker_missing_alpaca_key_raises(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET", raising=False)
    with pytest.raises(Exception):
        make_broker({"broker": "alpaca", "mode": "paper"})

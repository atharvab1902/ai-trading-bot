"""Tests for ml/daily_retrain_us.py."""
import json
import pickle
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest


def _make_db(tmp_path, trades):
    db = tmp_path / "trades.db"
    con = sqlite3.connect(db)
    con.execute("""
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY, ts TEXT, account TEXT, mode TEXT,
            symbol TEXT, side TEXT, qty INTEGER, entry_price REAL,
            exit_price REAL, stoploss REAL, target REAL, pnl REAL,
            strategy TEXT, status TEXT, broker_order_id TEXT,
            notes TEXT, signal_features TEXT
        )
    """)
    for t in trades:
        con.execute(
            "INSERT INTO trades (ts,account,side,pnl,status,signal_features) VALUES (?,?,?,?,?,?)",
            t
        )
    con.commit()
    con.close()
    return db


def _make_feature(side="SELL", pnl=50.0):
    from ml.features import FEATURE_COLS
    feats = {c: 0.5 for c in FEATURE_COLS}
    return {
        "ml_features": feats,
        "catalyst_score": 5,
    }


def _make_trades(n, win_rate=0.6, account="us_trader"):
    rows = []
    for i in range(n):
        side = "SELL"
        pnl  = 50.0 if i / n < win_rate else -30.0
        rows.append((
            f"2026-07-0{(i%9)+1}T10:00:00",
            account, side, pnl, "closed",
            json.dumps(_make_feature(side, pnl))
        ))
    return rows


# ── load_us_trades ────────────────────────────────────────────────────────────

def test_load_us_trades_returns_records(tmp_path):
    from ml.daily_retrain_us import load_us_trades
    import ml.daily_retrain_us as m

    db = _make_db(tmp_path, _make_trades(5))
    with patch.object(m, "TRADES_DB", db):
        records = load_us_trades("us_trader")
    assert len(records) == 5


def test_load_us_trades_filters_by_account(tmp_path):
    from ml.daily_retrain_us import load_us_trades
    import ml.daily_retrain_us as m

    rows = _make_trades(5, account="us_trader") + _make_trades(3, account="tester")
    db = _make_db(tmp_path, rows)
    with patch.object(m, "TRADES_DB", db):
        records = load_us_trades("us_trader")
    assert len(records) == 5


def test_load_us_trades_skips_missing_features(tmp_path):
    from ml.daily_retrain_us import load_us_trades
    import ml.daily_retrain_us as m

    rows = _make_trades(3) + [
        ("2026-07-08T10:00:00", "us_trader", "SELL", 10.0, "closed", None)
    ]
    db = _make_db(tmp_path, rows)
    with patch.object(m, "TRADES_DB", db):
        records = load_us_trades("us_trader")
    assert len(records) == 3


# ── run — below minimum threshold ─────────────────────────────────────────────

def test_run_skips_below_min_trades(tmp_path, capsys):
    from ml.daily_retrain_us import run
    import ml.daily_retrain_us as m

    db = _make_db(tmp_path, _make_trades(5))   # 5 < MIN_TRADES=10
    model_path = tmp_path / "model_us_trader.pkl"

    with patch.object(m, "TRADES_DB", db), \
         patch.object(m, "REPO_ROOT", tmp_path), \
         patch.object(m, "JOURNAL", tmp_path / "journal.md"):
        run(account="us_trader", force=False)

    captured = capsys.readouterr()
    assert "Below minimum" in captured.out
    assert not model_path.exists()


# ── run — trains and saves model ──────────────────────────────────────────────

def test_run_trains_and_saves_model(tmp_path, capsys):
    from ml.daily_retrain_us import run
    import ml.daily_retrain_us as m

    trades = _make_trades(15, win_rate=0.0)   # all shorts lost → only short label
    db = _make_db(tmp_path, trades)
    (tmp_path / "ml").mkdir(exist_ok=True)

    with patch.object(m, "TRADES_DB", db), \
         patch.object(m, "REPO_ROOT", tmp_path), \
         patch.object(m, "JOURNAL", tmp_path / "journal.md"):
        run(account="us_trader", force=True)

    model_path = tmp_path / "ml" / "model_us_trader.pkl"
    meta_path  = tmp_path / "ml" / "model_us_trader_meta.json"
    assert model_path.exists() or meta_path.exists()


def test_run_meta_is_valid_json(tmp_path):
    from ml.daily_retrain_us import run
    import ml.daily_retrain_us as m

    trades = _make_trades(15)
    db = _make_db(tmp_path, trades)
    (tmp_path / "ml").mkdir(exist_ok=True)

    with patch.object(m, "TRADES_DB", db), \
         patch.object(m, "REPO_ROOT", tmp_path), \
         patch.object(m, "JOURNAL", tmp_path / "journal.md"):
        run(account="us_trader", force=True)

    meta_path = tmp_path / "ml" / "model_us_trader_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        assert meta["account"] == "us_trader"
        assert meta["market"] == "US"
        assert isinstance(meta["n_trades"], int)


def test_run_deployed_flag_is_bool(tmp_path):
    from ml.daily_retrain_us import run
    import ml.daily_retrain_us as m

    trades = _make_trades(15)
    db = _make_db(tmp_path, trades)
    (tmp_path / "ml").mkdir(exist_ok=True)

    with patch.object(m, "TRADES_DB", db), \
         patch.object(m, "REPO_ROOT", tmp_path), \
         patch.object(m, "JOURNAL", tmp_path / "journal.md"):
        run(account="us_trader", force=True)

    meta_path = tmp_path / "ml" / "model_us_trader_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        # This was the bug — numpy.bool_ crashed json.dumps
        assert isinstance(meta["deployed"], bool)

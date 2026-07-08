"""Shared fixtures for all tests."""
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def trades_db(tmp_path):
    """In-memory trades DB with schema matching the real one."""
    db_path = tmp_path / "trades.db"
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, account TEXT, mode TEXT,
            symbol TEXT, side TEXT, qty INTEGER,
            entry_price REAL, exit_price REAL,
            stoploss REAL, target REAL, pnl REAL,
            strategy TEXT, status TEXT,
            broker_order_id TEXT, notes TEXT, signal_features TEXT
        )
    """)
    con.commit()
    con.close()
    return db_path


@pytest.fixture
def sample_trade(trades_db):
    """Insert one closed winning trade and return the db path."""
    con = sqlite3.connect(trades_db)
    con.execute("""
        INSERT INTO trades
            (ts, account, mode, symbol, side, qty, entry_price, exit_price, pnl, status, notes, signal_features)
        VALUES
            ('2026-07-08T10:00:00', 'us_trader', 'paper', 'TSLA', 'SELL', 10, 400.0, 396.0, 40.0, 'closed', 'TARGET',
             '{"ml_features": {"gap_pct": 0.1, "vol_surge_5d": 1.2, "mom_30m_pct": -0.5,
               "mom_15m_pct": -0.3, "vol_ratio_5m": 1.1, "vwap_dev_pct": 0.5,
               "ema9_21_spread": -0.1, "rsi14_feat": 55.0, "atr14_pct": 0.8,
               "orb_width_pct": 0.4, "time_bucket": 2, "is_first_30min": 0,
               "is_last_hour": 0, "bars_above_vwap_pct": 40.0,
               "sym_win_rate_10": 0.6, "vix_level": 0.5,
               "universe_move_30m_pct": -0.2, "stock_vs_universe_30m": -0.3,
               "catalyst_score_feat": 0.5}}')
    """)
    con.commit()
    con.close()
    return trades_db


@pytest.fixture
def env_file(tmp_path):
    """A minimal .env file."""
    p = tmp_path / ".env"
    p.write_text(
        "DHAN_CLIENT_ID=12345\n"
        "DHAN_ACCESS_TOKEN=dhan_tok_abc123xyz\n"
        "ALPACA_API_KEY=ALPA1234abcd\n"
        "ALPACA_SECRET_KEY=secret_xyz789\n"
        "TELEGRAM_BOT_TOKEN=8770abc123\n"
        "TELEGRAM_CHAT_ID=8424749759\n"
        "PERPLEXITY_API_KEY=pplx_key123\n"
    )
    return p


@pytest.fixture
def base_cfg():
    """Minimal valid account config."""
    return {
        "name": "test_acct",
        "broker": "dhan",
        "mode": "paper",
        "capital": 100000,
        "daily_loss_limit_pct": 2.0,
        "max_positions": 3,
        "max_position_size": 10000,
        "active_strategy": "vwap",
        "strategy_params": {
            "vwap": {
                "stoploss_pct": 0.5,
                "target_pct": 0.5,
                "entry_threshold_pct": 0.4,
                "warmup_minutes": 45,
            }
        },
    }

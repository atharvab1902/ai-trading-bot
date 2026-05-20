import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytz

DB_PATH = Path(__file__).parent.parent / "data" / "trades.db"
_IST = pytz.timezone("Asia/Kolkata")


def _now_ist() -> str:
    return datetime.now(_IST).isoformat()

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    account TEXT NOT NULL,
    mode TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    stoploss REAL,
    target REAL,
    pnl REAL,
    strategy TEXT NOT NULL,
    status TEXT NOT NULL,
    broker_order_id TEXT,
    notes TEXT,
    signal_features TEXT
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER REFERENCES trades(id),
    symbol TEXT NOT NULL,
    qty INTEGER NOT NULL,
    avg_price REAL NOT NULL,
    status TEXT NOT NULL,
    opened_ts TEXT NOT NULL,
    closed_ts TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    account TEXT NOT NULL,
    level TEXT NOT NULL,
    kind TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blocked_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    account TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price REAL NOT NULL,
    stoploss REAL NOT NULL,
    target REAL NOT NULL,
    strategy TEXT NOT NULL,
    ml_prob REAL NOT NULL,
    catalyst_score INTEGER NOT NULL,
    resolve_after TEXT NOT NULL,
    resolved INTEGER DEFAULT 0,
    outcome_price REAL,
    outcome_pnl_pct REAL,
    would_have_hit TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_ts ON trades(ts);
CREATE INDEX IF NOT EXISTS idx_trades_account ON trades(account);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_blocked_resolved ON blocked_signals(resolved);
"""


@contextmanager
def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)


def log_event(account: str, level: str, kind: str, message: str):
    with conn() as c:
        c.execute(
            "INSERT INTO events (ts, account, level, kind, message) VALUES (?, ?, ?, ?, ?)",
            (_now_ist(), account, level, kind, message),
        )


def record_trade(
    account: str,
    mode: str,
    symbol: str,
    side: str,
    qty: int,
    entry_price: float,
    stoploss: float,
    target: float,
    strategy: str,
    broker_order_id: str = None,
    signal_features: dict = None,
) -> int:
    import json as _json
    import numpy as _np

    class _NpEncoder(_json.JSONEncoder):
        def default(self, o):
            if isinstance(o, _np.integer): return int(o)
            if isinstance(o, _np.floating): return float(o)
            if isinstance(o, _np.ndarray): return o.tolist()
            return super().default(o)

    features_json = _json.dumps(signal_features, cls=_NpEncoder) if signal_features else None
    with conn() as c:
        # Safety guard: never allow two open positions on the same symbol
        existing = c.execute(
            "SELECT id FROM trades WHERE account=? AND symbol=? AND status='open'",
            (account, symbol)
        ).fetchone()
        if existing:
            raise ValueError(f"Duplicate blocked at DB: open position already exists for {symbol} (id={existing['id']})")

        # Add signal_features column if it doesn't exist yet (migration)
        try:
            c.execute("ALTER TABLE trades ADD COLUMN signal_features TEXT")
        except Exception:
            pass  # column already exists

        cur = c.execute(
            """INSERT INTO trades (ts, account, mode, symbol, side, qty, entry_price,
               stoploss, target, strategy, status, broker_order_id, signal_features)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
            (_now_ist(), account, mode, symbol, side, qty,
             entry_price, stoploss, target, strategy, broker_order_id, features_json),
        )
        return cur.lastrowid


def close_trade(trade_id: int, exit_price: float, pnl: float, notes: str = ""):
    with conn() as c:
        c.execute(
            "UPDATE trades SET exit_price=?, pnl=?, status='closed', notes=? WHERE id=?",
            (exit_price, pnl, notes, trade_id),
        )


def today_pnl(account: str) -> float:
    with conn() as c:
        row = c.execute(
            "SELECT COALESCE(SUM(pnl), 0) AS p FROM trades "
            "WHERE account=? AND date(ts)=date('now') AND status='closed'",
            (account,),
        ).fetchone()
        return float(row["p"])


def open_positions_count(account: str) -> int:
    with conn() as c:
        row = c.execute(
            "SELECT COUNT(*) AS n FROM trades WHERE account=? AND status='open'",
            (account,),
        ).fetchone()
        return int(row["n"])


def record_blocked_signal(
    account: str, symbol: str, side: str,
    entry_price: float, stoploss: float, target: float,
    strategy: str, ml_prob: float, catalyst_score: int,
    resolve_after_iso: str,
) -> int:
    """Log a signal the ML blocked. resolve_after_iso = when to check outcome."""
    with conn() as c:
        try:
            c.execute("ALTER TABLE blocked_signals ADD COLUMN resolve_after TEXT")
        except Exception:
            pass
        cur = c.execute(
            """INSERT INTO blocked_signals
               (ts, account, symbol, side, entry_price, stoploss, target,
                strategy, ml_prob, catalyst_score, resolve_after, resolved)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (_now_ist(), account, symbol, side,
             entry_price, stoploss, target, strategy,
             ml_prob, catalyst_score, resolve_after_iso),
        )
        return cur.lastrowid


def resolve_blocked_signals(account: str, current_prices: dict) -> list:
    """
    Check any unresolved blocked signals whose resolve_after time has passed.
    current_prices: {symbol: price}
    Returns list of resolved rows for logging.
    """
    now = _now_ist()
    resolved = []
    with conn() as c:
        rows = c.execute(
            """SELECT * FROM blocked_signals
               WHERE account=? AND resolved=0 AND resolve_after <= ?""",
            (account, now),
        ).fetchall()
        for row in rows:
            price = current_prices.get(row["symbol"])
            if price is None:
                continue
            entry = row["entry_price"]
            sl = row["stoploss"]
            tgt = row["target"]
            side = row["side"]

            # Simulate: did it hit target, stoploss, or neither?
            if side == "BUY":
                pnl_pct = (price - entry) / entry * 100
                if price >= tgt:
                    hit = "TARGET"
                elif price <= sl:
                    hit = "STOPLOSS"
                else:
                    hit = "OPEN"
            else:
                pnl_pct = (entry - price) / entry * 100
                if price <= tgt:
                    hit = "TARGET"
                elif price >= sl:
                    hit = "STOPLOSS"
                else:
                    hit = "OPEN"

            c.execute(
                """UPDATE blocked_signals
                   SET resolved=1, outcome_price=?, outcome_pnl_pct=?, would_have_hit=?
                   WHERE id=?""",
                (price, round(pnl_pct, 3), hit, row["id"]),
            )
            resolved.append({
                "symbol": row["symbol"], "side": side,
                "ml_prob": row["ml_prob"], "catalyst_score": row["catalyst_score"],
                "entry": entry, "outcome_price": price,
                "pnl_pct": round(pnl_pct, 3), "hit": hit,
            })
    return resolved


def open_positions_by_symbol(account: str) -> dict:
    """Returns {symbol: side} for all currently open trades."""
    with conn() as c:
        rows = c.execute(
            "SELECT symbol, side FROM trades WHERE account=? AND status='open'",
            (account,),
        ).fetchall()
    return {row["symbol"]: row["side"] for row in rows}

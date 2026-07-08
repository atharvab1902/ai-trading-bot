"""Tests for dashboard.py — every route and API endpoint."""
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import dashboard as dash
from dashboard import app


@pytest.fixture(autouse=True)
def patch_repo_root(tmp_path):
    """Point dashboard at a temp directory so tests don't touch real data."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create a minimal trades.db
    db = data_dir / "trades.db"
    con = sqlite3.connect(db)
    con.execute("""
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, account TEXT, mode TEXT, symbol TEXT, side TEXT,
            qty INTEGER, entry_price REAL, exit_price REAL,
            stoploss REAL, target REAL, pnl REAL, strategy TEXT,
            status TEXT, broker_order_id TEXT, notes TEXT, signal_features TEXT
        )
    """)
    con.commit()
    con.close()

    # Patch REPO_ROOT and CLAUDE_CREDS in dashboard module
    import dashboard as d
    original_root  = d.REPO_ROOT
    original_creds = d.CLAUDE_CREDS
    original_home  = d.CLAUDE_HOME
    d.REPO_ROOT    = tmp_path
    d.CLAUDE_HOME  = tmp_path / "data" / "claude-home"
    d.CLAUDE_CREDS = tmp_path / "data" / "claude-home" / ".claude" / ".credentials.json"

    yield tmp_path

    d.REPO_ROOT    = original_root
    d.CLAUDE_CREDS = original_creds
    d.CLAUDE_HOME  = original_home


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def env_in_tmp(patch_repo_root):
    env = patch_repo_root / ".env"
    env.write_text(
        "DHAN_CLIENT_ID=12345\n"
        "DHAN_ACCESS_TOKEN=dhan_tok_abc123\n"
        "ALPACA_API_KEY=ALPA1234\n"
        "ALPACA_SECRET_KEY=secret_xyz\n"
        "TELEGRAM_BOT_TOKEN=8770tok\n"
        "TELEGRAM_CHAT_ID=99999\n"
        "PERPLEXITY_API_KEY=pplx_123\n"
    )
    return env


# ── GET / ─────────────────────────────────────────────────────────────────────

def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_index_contains_both_bots(client):
    resp = client.get("/")
    body = resp.data.decode()
    assert "India" in body
    assert "US" in body


def test_index_shows_start_button(client):
    resp = client.get("/")
    assert b"Start Bot" in resp.data


# ── GET /settings ─────────────────────────────────────────────────────────────

def test_settings_returns_200(client):
    resp = client.get("/settings")
    assert resp.status_code == 200


def test_settings_shows_all_sections(client):
    body = client.get("/settings").data.decode()
    assert "Dhan" in body
    assert "Alpaca" in body
    assert "Telegram" in body
    assert "Perplexity" in body
    assert "Claude Code" in body


def test_settings_shows_saved_values_masked(client, env_in_tmp):
    body = client.get("/settings").data.decode()
    # Dhan token: first 4 chars visible, rest masked
    assert "dhan" in body.lower()
    assert "•" in body


def test_settings_shows_not_set_badge_when_key_missing(client, patch_repo_root):
    # .env has no keys
    env = patch_repo_root / ".env"
    env.write_text("DHAN_CLIENT_ID=12345\n")
    body = client.get("/settings").data.decode()
    assert "Not set" in body


def test_settings_shows_saved_badge_when_key_exists(client, env_in_tmp):
    body = client.get("/settings").data.decode()
    assert "Saved" in body


# ── POST /settings ────────────────────────────────────────────────────────────

def test_settings_post_saves_new_key(client, patch_repo_root):
    resp = client.post("/settings", data={
        "DHAN_CLIENT_ID": "99999",
        "DHAN_ACCESS_TOKEN": "new_token_xyz",
        "ALPACA_API_KEY": "", "ALPACA_SECRET_KEY": "",
        "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "",
        "PERPLEXITY_API_KEY": "",
    })
    assert resp.status_code == 200
    env_content = (patch_repo_root / ".env").read_text()
    assert "new_token_xyz" in env_content
    assert "99999" in env_content


def test_settings_post_blank_field_keeps_existing(client, env_in_tmp, patch_repo_root):
    # Only update DHAN_CLIENT_ID, leave token blank
    client.post("/settings", data={
        "DHAN_CLIENT_ID": "NEW_ID",
        "DHAN_ACCESS_TOKEN": "",   # blank — should keep existing
        "ALPACA_API_KEY": "", "ALPACA_SECRET_KEY": "",
        "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "",
        "PERPLEXITY_API_KEY": "",
    })
    env_content = (patch_repo_root / ".env").read_text()
    assert "dhan_tok_abc123" in env_content   # original token kept
    assert "NEW_ID" in env_content


def test_settings_post_shows_saved_banner(client, patch_repo_root):
    resp = client.post("/settings", data={
        "DHAN_CLIENT_ID": "1", "DHAN_ACCESS_TOKEN": "",
        "ALPACA_API_KEY": "", "ALPACA_SECRET_KEY": "",
        "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "",
        "PERPLEXITY_API_KEY": "",
    })
    assert b"saved successfully" in resp.data.lower()


# ── GET /api/status ───────────────────────────────────────────────────────────

def test_api_status_returns_both_accounts(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "tester" in data
    assert "us_trader" in data


def test_api_status_structure(client):
    data = json.loads(client.get("/api/status").data)
    for account in ("tester", "us_trader"):
        acct = data[account]
        assert "running" in acct
        assert "pnl" in acct
        assert "trades" in acct
        assert "wins" in acct
        assert "losses" in acct
        assert "open" in acct
        assert isinstance(acct["running"], bool)


def test_api_status_not_running_initially(client):
    data = json.loads(client.get("/api/status").data)
    assert data["tester"]["running"] is False
    assert data["us_trader"]["running"] is False


def test_api_status_pnl_zero_no_trades(client):
    data = json.loads(client.get("/api/status").data)
    assert data["tester"]["pnl"] == 0.0
    assert data["us_trader"]["trades"] == 0


# ── POST /api/start/:account ──────────────────────────────────────────────────

def test_api_start_valid_account(client):
    with patch("dashboard.start_bot") as mock_start, \
         patch("dashboard.is_running", return_value=True):
        resp = client.post("/api/start/tester")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["running"] is True


def test_api_start_invalid_account(client):
    resp = client.post("/api/start/nonexistent")
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert "error" in data


def test_api_start_us_trader(client):
    with patch("dashboard.start_bot"), \
         patch("dashboard.is_running", return_value=True):
        resp = client.post("/api/start/us_trader")
    assert resp.status_code == 200


# ── POST /api/stop/:account ───────────────────────────────────────────────────

def test_api_stop_valid_account(client):
    with patch("dashboard.stop_bot"), \
         patch("dashboard.is_running", return_value=False):
        resp = client.post("/api/stop/tester")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["running"] is False


def test_api_stop_invalid_account(client):
    resp = client.post("/api/stop/badaccount")
    assert resp.status_code == 400


# ── GET /api/claude/status ────────────────────────────────────────────────────

def test_claude_status_not_connected_initially(client):
    resp = client.get("/api/claude/status")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["connected"] is False


def test_claude_status_connected_with_valid_creds(client, patch_repo_root):
    import dashboard as d
    from datetime import datetime, timezone
    creds_dir = patch_repo_root / "data" / "claude-home" / ".claude"
    creds_dir.mkdir(parents=True)
    future_ms = int(datetime.now(timezone.utc).timestamp() * 1000) + 3600_000
    creds = {
        "claudeAiOauth": {
            "accessToken": "tok_abc",
            "refreshToken": "ref_xyz",
            "expiresAt": future_ms,
            "scopes": ["user:profile"],
        }
    }
    (creds_dir / ".credentials.json").write_text(json.dumps(creds))
    d.CLAUDE_CREDS = creds_dir / ".credentials.json"

    resp = client.get("/api/claude/status")
    data = json.loads(resp.data)
    assert data["connected"] is True
    assert data["expired"] is False


def test_claude_status_expired(client, patch_repo_root):
    import dashboard as d
    creds_dir = patch_repo_root / "data" / "claude-home" / ".claude"
    creds_dir.mkdir(parents=True)
    expired_ms = 1000  # epoch 1970 — definitely expired
    creds = {"claudeAiOauth": {"accessToken": "x", "refreshToken": "y", "expiresAt": expired_ms}}
    (creds_dir / ".credentials.json").write_text(json.dumps(creds))
    d.CLAUDE_CREDS = creds_dir / ".credentials.json"

    data = json.loads(client.get("/api/claude/status").data)
    assert data["connected"] is False
    assert data["expired"] is True


# ── POST /api/claude/oauth/start ─────────────────────────────────────────────

def test_claude_oauth_start_returns_url(client):
    resp = client.post("/api/claude/oauth/start")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "url" in data
    assert "claude.ai/oauth/authorize" in data["url"]


def test_claude_oauth_start_url_has_pkce(client):
    data = json.loads(client.post("/api/claude/oauth/start").data)
    url = data["url"]
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert "client_id=" in url
    assert "state=" in url


def test_claude_oauth_start_stores_pkce(client):
    client.post("/api/claude/oauth/start")
    assert "current" in dash._pkce_store
    assert "verifier" in dash._pkce_store["current"]
    assert "state" in dash._pkce_store["current"]


# ── POST /api/claude/oauth/exchange ──────────────────────────────────────────

def test_claude_oauth_exchange_no_code(client):
    resp = client.post("/api/claude/oauth/exchange",
                       json={}, content_type="application/json")
    assert resp.status_code == 400
    assert b"code" in resp.data.lower()


def test_claude_oauth_exchange_no_pkce_session(client):
    dash._pkce_store.clear()
    resp = client.post("/api/claude/oauth/exchange",
                       json={"code": "abc123"}, content_type="application/json")
    assert resp.status_code == 400
    assert b"Connect first" in resp.data or b"login in progress" in resp.data


def test_claude_oauth_exchange_strips_state_suffix(client):
    """Code may arrive as 'actualcode#statevalue' — only the part before # is sent."""
    dash._pkce_store["current"] = {"verifier": "v", "state": "s"}
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "access_token": "at_xyz",
        "refresh_token": "rt_abc",
        "expires_in": 3600,
    }
    with patch("dashboard._requests.post", return_value=mock_resp):
        resp = client.post("/api/claude/oauth/exchange",
                           json={"code": "real_code#state_garbage"},
                           content_type="application/json")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True


def test_claude_oauth_exchange_saves_credentials(client, patch_repo_root):
    import dashboard as d
    dash._pkce_store["current"] = {"verifier": "v", "state": "s"}
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "access_token": "at_xyz", "refresh_token": "rt_abc", "expires_in": 3600
    }
    with patch("dashboard._requests.post", return_value=mock_resp):
        client.post("/api/claude/oauth/exchange",
                    json={"code": "real_code"},
                    content_type="application/json")

    assert d.CLAUDE_CREDS.exists()
    saved = json.loads(d.CLAUDE_CREDS.read_text())
    assert saved["claudeAiOauth"]["accessToken"] == "at_xyz"


def test_claude_oauth_exchange_error_from_claude(client):
    dash._pkce_store["current"] = {"verifier": "v", "state": "s"}
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"error": "invalid_grant", "error_description": "Bad code"}
    with patch("dashboard._requests.post", return_value=mock_resp):
        resp = client.post("/api/claude/oauth/exchange",
                           json={"code": "bad_code"},
                           content_type="application/json")
    assert resp.status_code == 400


# ── POST /api/claude/logout ───────────────────────────────────────────────────

def test_claude_logout_removes_credentials(client, patch_repo_root):
    import dashboard as d
    creds_dir = patch_repo_root / "data" / "claude-home" / ".claude"
    creds_dir.mkdir(parents=True)
    cred_file = creds_dir / ".credentials.json"
    cred_file.write_text('{"claudeAiOauth": {"accessToken": "x"}}')
    d.CLAUDE_CREDS = cred_file

    resp = client.post("/api/claude/logout")
    assert resp.status_code == 200
    assert not cred_file.exists()


def test_claude_logout_ok_when_no_creds(client):
    resp = client.post("/api/claude/logout")
    assert resp.status_code == 200
    assert json.loads(resp.data)["ok"] is True


def test_claude_logout_does_not_touch_system_creds(client, patch_repo_root):
    """Disconnect must NOT delete ~/.claude/.credentials.json."""
    import dashboard as d
    system_creds = Path.home() / ".claude" / ".credentials.json"
    system_existed = system_creds.exists()

    client.post("/api/claude/logout")

    assert system_creds.exists() == system_existed


# ── pnl with real trade data ──────────────────────────────────────────────────

def test_api_status_reflects_trades(client, patch_repo_root):
    db_path = patch_repo_root / "data" / "trades.db"
    from datetime import datetime
    import pytz
    today = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y-%m-%d")
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO trades (ts, account, mode, symbol, side, qty, entry_price, "
        "exit_price, pnl, status, notes) VALUES (?, 'us_trader', 'paper', "
        "'TSLA', 'SELL', 10, 400.0, 396.0, 40.0, 'closed', 'TARGET')",
        (f"{today}T10:00:00",)
    )
    con.commit()
    con.close()

    data = json.loads(client.get("/api/status").data)
    assert data["us_trader"]["pnl"] == 40.0
    assert data["us_trader"]["trades"] == 1
    assert data["us_trader"]["wins"] == 1
    assert data["us_trader"]["losses"] == 0

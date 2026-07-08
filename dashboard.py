"""Web dashboard for AI Trading Bot.

Usage:
    python dashboard.py
    Then open http://localhost:5000 in your browser.
"""

import base64
import hashlib
import json
import secrets
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import psutil
import pytz
import requests as _requests
from dotenv import dotenv_values
from flask import Flask, jsonify, render_template, request

REPO_ROOT = Path(__file__).parent
app = Flask(__name__)
app.secret_key = "trading-bot-dash"

ACCOUNTS = {
    "tester":    {"label": "India (NSE)", "currency": "₹", "tz": "Asia/Kolkata", "flag": "🇮🇳"},
    "us_trader": {"label": "US (NYSE)",   "currency": "$", "tz": "US/Eastern",   "flag": "🇺🇸"},
}

_procs: dict = {}

ENV_KEYS = [
    "DHAN_CLIENT_ID", "DHAN_ACCESS_TOKEN",
    "ALPACA_API_KEY", "ALPACA_SECRET_KEY",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
    "PERPLEXITY_API_KEY",
]
PLAIN_KEYS = {"DHAN_CLIENT_ID", "TELEGRAM_CHAT_ID"}

# ── Claude OAuth constants (same as job-search app) ──────────────────────────
_CLAUDE_CLIENT_ID    = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
_CLAUDE_REDIRECT_URI = "https://platform.claude.com/oauth/code/callback"
_CLAUDE_SCOPES       = "org:create_api_key user:profile user:inference user:sessions:claude_code"
_CLAUDE_TOKEN_URL    = "https://platform.claude.com/v1/oauth/token"

# Dashboard-owned credentials — completely separate from the terminal ~/.claude/
CLAUDE_HOME  = REPO_ROOT / "data" / "claude-home"
CLAUDE_CREDS = CLAUDE_HOME / ".claude" / ".credentials.json"

_pkce_store: dict = {}   # single-user dashboard, just one slot needed


# ── Claude helpers ────────────────────────────────────────────────────────────

def _generate_pkce() -> tuple[str, str]:
    verifier  = secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def claude_connection() -> dict:
    if not CLAUDE_CREDS.exists():
        return {"connected": False, "account": None, "expired": False}
    try:
        data  = json.loads(CLAUDE_CREDS.read_text())
        oauth = data.get("claudeAiOauth", {})
        exp   = oauth.get("expiresAt")
        expired = bool(exp and int(exp) < datetime.now(timezone.utc).timestamp() * 1000)
        acct  = oauth.get("account")
        email = acct.get("emailAddress") if isinstance(acct, dict) else None
        return {"connected": not expired, "account": email, "expired": expired}
    except Exception:
        return {"connected": False, "account": None, "expired": False}


def _write_claude_creds(access_token: str, refresh_token: str, expires_in: int):
    CLAUDE_CREDS.parent.mkdir(parents=True, exist_ok=True)
    creds = {
        "claudeAiOauth": {
            "accessToken":  access_token,
            "refreshToken": refresh_token,
            "expiresAt":    int(datetime.now(timezone.utc).timestamp() * 1000) + expires_in * 1000,
            "scopes":       _CLAUDE_SCOPES.split(),
        }
    }
    CLAUDE_CREDS.write_text(json.dumps(creds, indent=2))


# ── process management ────────────────────────────────────────────────────────

def _pid_file(account: str) -> Path:
    return REPO_ROOT / "data" / f"scheduler_{account}.pid"


def start_bot(account: str):
    if is_running(account):
        return
    proc = subprocess.Popen(
        [sys.executable, "scheduler.py", "--account", account],
        cwd=REPO_ROOT,
    )
    _procs[account] = proc
    _pid_file(account).write_text(str(proc.pid))


def stop_bot(account: str):
    pids = set()
    proc = _procs.pop(account, None)
    if proc:
        pids.add(proc.pid)
    pf = _pid_file(account)
    if pf.exists():
        try:
            pids.add(int(pf.read_text().strip()))
        except ValueError:
            pass
        pf.unlink(missing_ok=True)
    for pid in pids:
        try:
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
        except psutil.NoSuchProcess:
            pass


def is_running(account: str) -> bool:
    proc = _procs.get(account)
    if proc and proc.poll() is None:
        return True
    pf = _pid_file(account)
    if pf.exists():
        try:
            pid = int(pf.read_text().strip())
            if psutil.pid_exists(pid):
                return True
        except (ValueError, Exception):
            pass
        pf.unlink(missing_ok=True)
    return False


# ── data helpers ─────────────────────────────────────────────────────────────

def _db():
    return sqlite3.connect(str(REPO_ROOT / "data" / "trades.db"))


def account_stats(account: str) -> dict:
    info  = ACCOUNTS[account]
    today = datetime.now(pytz.timezone(info["tz"])).strftime("%Y-%m-%d")
    try:
        con = _db()
        pnl_row = con.execute(
            "SELECT COALESCE(SUM(pnl),0), COUNT(*) FROM trades "
            "WHERE account=? AND status='closed' AND substr(ts,1,10)=?",
            (account, today),
        ).fetchone()
        wins = con.execute(
            "SELECT COUNT(*) FROM trades WHERE account=? AND status='closed' "
            "AND substr(ts,1,10)=? AND pnl>0", (account, today),
        ).fetchone()[0]
        losses = con.execute(
            "SELECT COUNT(*) FROM trades WHERE account=? AND status='closed' "
            "AND substr(ts,1,10)=? AND pnl<0", (account, today),
        ).fetchone()[0]
        open_rows = con.execute(
            "SELECT symbol, side, qty, entry_price FROM trades "
            "WHERE account=? AND status='open'", (account,),
        ).fetchall()
        con.close()
    except Exception:
        pnl_row = (0.0, 0)
        wins = losses = 0
        open_rows = []

    return {
        "label":    info["label"],
        "flag":     info["flag"],
        "currency": info["currency"],
        "running":  is_running(account),
        "pnl":      round(pnl_row[0] or 0.0, 2),
        "trades":   pnl_row[1] or 0,
        "wins":     wins,
        "losses":   losses,
        "open":     [
            {"symbol": r[0], "side": r[1], "qty": r[2], "entry": round(r[3], 2)}
            for r in open_rows
        ],
    }


def recent_trades(limit: int = 30) -> list:
    try:
        con  = _db()
        rows = con.execute(
            "SELECT ts, account, symbol, side, qty, entry_price, exit_price, pnl, status, notes "
            "FROM trades ORDER BY ts DESC LIMIT ?", (limit,),
        ).fetchall()
        con.close()
    except Exception:
        return []
    result = []
    for ts, acct, sym, side, qty, ep, xp, pnl, status, notes in rows:
        info = ACCOUNTS.get(acct, {})
        result.append({
            "ts":       (ts or "")[:16].replace("T", " "),
            "market":   info.get("label", acct),
            "currency": info.get("currency", ""),
            "symbol":   sym or "",
            "side":     side or "",
            "qty":      qty or 0,
            "entry":    round(ep, 2) if ep else 0,
            "exit":     round(xp, 2) if xp else None,
            "pnl":      round(pnl, 2) if pnl is not None else None,
            "status":   status or "",
            "reason":   (notes or "").strip(),
        })
    return result


# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    stats  = {acc: account_stats(acc) for acc in ACCOUNTS}
    trades = recent_trades()
    return render_template("index.html", stats=stats, trades=trades, accounts=ACCOUNTS)


@app.route("/api/status")
def api_status():
    return jsonify({acc: account_stats(acc) for acc in ACCOUNTS})


@app.route("/api/start/<account>", methods=["POST"])
def api_start(account):
    if account not in ACCOUNTS:
        return jsonify({"error": "unknown account"}), 400
    start_bot(account)
    return jsonify({"running": True})


@app.route("/api/stop/<account>", methods=["POST"])
def api_stop(account):
    if account not in ACCOUNTS:
        return jsonify({"error": "unknown account"}), 400
    stop_bot(account)
    return jsonify({"running": False})


# ── Claude OAuth routes ───────────────────────────────────────────────────────

@app.route("/api/claude/oauth/start", methods=["POST"])
def api_claude_oauth_start():
    verifier, challenge = _generate_pkce()
    state = secrets.token_hex(16)
    _pkce_store["current"] = {"verifier": verifier, "state": state}

    params = urlencode({
        "code":                  "true",
        "client_id":             _CLAUDE_CLIENT_ID,
        "response_type":         "code",
        "redirect_uri":          _CLAUDE_REDIRECT_URI,
        "scope":                 _CLAUDE_SCOPES,
        "code_challenge":        challenge,
        "code_challenge_method": "S256",
        "state":                 state,
    })
    return jsonify({"url": f"https://claude.ai/oauth/authorize?{params}"})


@app.route("/api/claude/oauth/exchange", methods=["POST"])
def api_claude_oauth_exchange():
    code = (request.json or {}).get("code", "").strip()
    if not code:
        return jsonify({"error": "No code provided"}), 400

    pkce = _pkce_store.pop("current", None)
    if not pkce:
        return jsonify({"error": "No login in progress — click Connect first"}), 400

    actual_code = code.split("#")[0].strip()

    try:
        resp = _requests.post(_CLAUDE_TOKEN_URL, json={
            "grant_type":    "authorization_code",
            "client_id":     _CLAUDE_CLIENT_ID,
            "code":          actual_code,
            "redirect_uri":  _CLAUDE_REDIRECT_URI,
            "code_verifier": pkce["verifier"],
            "state":         pkce["state"],
        }, timeout=15)
        tokens = resp.json()
    except Exception as e:
        return jsonify({"error": f"Token exchange failed: {e}"}), 500

    if "access_token" not in tokens:
        return jsonify({"error": tokens.get("error_description", "Unknown error from Claude")}), 400

    _write_claude_creds(
        tokens["access_token"],
        tokens.get("refresh_token", ""),
        tokens.get("expires_in", 3600),
    )
    return jsonify({"ok": True})


@app.route("/api/claude/logout", methods=["POST"])
def api_claude_logout():
    try:
        if CLAUDE_CREDS.exists():
            CLAUDE_CREDS.unlink()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/claude/status")
def api_claude_status():
    return jsonify(claude_connection())


# ── settings ──────────────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
def settings():
    env_path = REPO_ROOT / ".env"
    saved = False
    if request.method == "POST":
        existing = dict(dotenv_values(str(env_path))) if env_path.exists() else {}
        for key in ENV_KEYS:
            val = request.form.get(key, "").strip()
            if val:
                existing[key] = val
        with open(env_path, "w") as f:
            for k, v in existing.items():
                f.write(f"{k}={v}\n")
        saved = True

    current = dict(dotenv_values(str(env_path))) if env_path.exists() else {}
    masked  = {}
    for k in ENV_KEYS:
        v = current.get(k, "")
        if v and k not in PLAIN_KEYS:
            masked[k] = v[:4] + "•" * max(8, len(v) - 4)
        else:
            masked[k] = v

    return render_template("settings.html", masked=masked, saved=saved,
                           claude=claude_connection())


if __name__ == "__main__":
    print("Dashboard running at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)

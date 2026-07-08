"""
Postmarket Intelligence — runs after postmarket.py for both India and US accounts.

Claude reasons about today's trades, finds win/loss patterns, proposes specific
config changes with confidence scores. High-confidence minor param changes are
auto-applied. Everything else is written to the journal for weekly review.
"""

import json
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytz
import yaml

REPO_ROOT = Path(__file__).parent.parent
CLAUDE_CMD = shutil.which("claude") or r"C:\Users\athar\AppData\Roaming\npm\claude.cmd"

_SAFE_AUTO_APPLY_PATHS = {
    "strategy_params.vwap.entry_threshold_pct",
    "strategy_params.vwap.min_recovery_ratio",
    "strategy_params.orb.target_pct",
    "strategy_params.vwap.target_pct",
}


def _load_today_trades(account: str) -> list[dict]:
    db = REPO_ROOT / "data" / "trades.db"
    if not db.exists():
        return []
    today = date.today().isoformat()
    with sqlite3.connect(db) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM trades WHERE account=? AND ts LIKE ? AND status='closed' ORDER BY ts",
            (account, f"{today}%"),
        ).fetchall()
    return [dict(r) for r in rows]


def _load_recent_trades(account: str, n: int = 30) -> list[dict]:
    db = REPO_ROOT / "data" / "trades.db"
    if not db.exists():
        return []
    with sqlite3.connect(db) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT ts, symbol, side, pnl, notes, strategy FROM trades "
            "WHERE account=? AND status='closed' ORDER BY ts DESC LIMIT ?",
            (account, n),
        ).fetchall()
    return [dict(r) for r in rows]


def _load_config(account: str) -> dict:
    cfg_path = REPO_ROOT / "config" / "accounts" / f"{account}.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def _build_prompt(account: str, today_trades: list, recent_trades: list, cfg: dict) -> str:
    is_us = cfg.get("broker") == "alpaca"
    market = "US (NYSE/NASDAQ, USD)" if is_us else "India (NSE, INR)"
    currency = "$" if is_us else "Rs"

    # Today's trade summary
    if not today_trades:
        trade_lines = "  No trades placed today."
    else:
        lines = []
        for t in today_trades:
            pnl = t.get("pnl") or 0
            ml_prob = "N/A"
            try:
                sf = json.loads(t.get("signal_features") or "{}")
                ml_prob = sf.get("ml_prob", sf.get("ml_features", {}).get("ml_prob", "N/A"))
                if isinstance(ml_prob, float):
                    ml_prob = f"{ml_prob:.2f}"
            except Exception:
                pass
            lines.append(
                f"  {t['symbol']} {t['side']} | "
                f"PnL: {'+' if pnl >= 0 else ''}{currency}{pnl:.2f} | "
                f"Entry: {t.get('entry_price', '?')} → Exit: {t.get('exit_price', '?')} | "
                f"Strategy: {t.get('strategy', '?')} | Notes: {t.get('notes', '?')} | "
                f"ML prob: {ml_prob}"
            )
        trade_lines = "\n".join(lines)

    # Recent trend
    if recent_trades:
        wins = sum(1 for t in recent_trades if (t.get("pnl") or 0) > 0)
        total = len(recent_trades)
        total_pnl = sum((t.get("pnl") or 0) for t in recent_trades)
        trend = (
            f"Last {total} trades: {wins}W/{total - wins}L "
            f"({wins/total*100:.0f}% win rate), cumulative PnL={currency}{total_pnl:.2f}"
        )
    else:
        trend = "No recent trade history yet."

    # Key config
    sp = cfg.get("strategy_params", {})
    vwap = sp.get("vwap", {})
    orb = sp.get("orb", {})
    risk = {
        "daily_loss_pct": cfg.get("daily_loss_pct"),
        "max_positions": cfg.get("max_positions"),
        "ml_threshold": cfg.get("ml_threshold", 0.40),
        "entry_cutoff_time": cfg.get("entry_cutoff_time"),
        "use_ml": cfg.get("use_ml", True),
    }

    return f"""You are a quantitative trading analyst. Review today's trades for account '{account}' trading {market}.

RECENT PERFORMANCE TREND:
{trend}

TODAY'S TRADES:
{trade_lines}

CURRENT CONFIG:
Risk params: {json.dumps(risk)}
VWAP params: {json.dumps(vwap)}
ORB params:  {json.dumps(orb)}

Analyze what worked and what failed. Propose specific, evidence-based improvements.

Reply with ONLY valid JSON (no markdown fences, no text outside the JSON):
{{
  "summary": "2-3 sentence summary of today",
  "what_worked": ["concrete observation 1", "concrete observation 2"],
  "what_failed": ["concrete observation 1", "concrete observation 2"],
  "regime_assessment": "trending_up|trending_down|ranging|high_volatility|mixed",
  "proposals": [
    {{
      "param_path": "strategy_params.vwap.entry_threshold_pct",
      "current_value": 0.4,
      "proposed_value": 0.5,
      "confidence": 0.75,
      "reasoning": "one sentence why",
      "safe_to_auto_apply": false
    }}
  ],
  "risk_flags": ["only include if genuinely concerning"],
  "recommendation": "CONTINUE|REDUCE_SIZE|PAUSE"
}}

Rules:
- param_path must match actual keys in the config shown above
- confidence is 0.0-1.0; only set safe_to_auto_apply=true when confidence>=0.85 AND the change is a minor strategy threshold (not risk params, not position sizing)
- Maximum 3 proposals, only if supported by today's evidence
- If no trades today, assess the trend and give a recommendation anyway
- risk_flags only for serious patterns (3+ consecutive SLs, strategy clearly broken)"""


def _call_claude(prompt: str, timeout: int = 120) -> str | None:
    try:
        result = subprocess.run(
            [CLAUDE_CMD, "-p", prompt, "--dangerously-skip-permissions"],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except subprocess.TimeoutExpired:
        print("  Claude timed out.")
        return None
    except Exception as e:
        print(f"  Claude error: {e}")
        return None


def _parse_response(raw: str) -> dict | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]+\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return None


def _auto_apply(account: str, analysis: dict, cfg: dict) -> list[str]:
    """Apply high-confidence, safe proposals directly to config YAML."""
    applied = []
    cfg_path = REPO_ROOT / "config" / "accounts" / f"{account}.yaml"

    for prop in analysis.get("proposals", []):
        if not prop.get("safe_to_auto_apply"):
            continue
        if prop.get("confidence", 0) < 0.85:
            continue
        param_path = prop.get("param_path", "")
        if param_path not in _SAFE_AUTO_APPLY_PATHS:
            continue

        parts = param_path.split(".")
        node = cfg
        try:
            for part in parts[:-1]:
                node = node[part]
            old = node[parts[-1]]
            node[parts[-1]] = prop["proposed_value"]
            applied.append(f"{param_path}: {old} → {prop['proposed_value']}")
        except (KeyError, TypeError):
            continue

    if applied:
        with open(cfg_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)

    return applied


def _append_journal(account: str, analysis: dict, applied: list[str]):
    today = date.today().isoformat()
    journal = REPO_ROOT / "data" / "journal.md"
    journal.parent.mkdir(parents=True, exist_ok=True)

    lines = [f"\n### Intelligence — {today} ({account})\n"]
    lines.append(f"**Summary:** {analysis.get('summary', 'N/A')}\n")
    lines.append(f"**Regime:** {analysis.get('regime_assessment', '?')} | "
                 f"**Recommendation:** {analysis.get('recommendation', 'CONTINUE')}\n")

    if analysis.get("what_worked"):
        lines.append("\n**Worked:**")
        for w in analysis["what_worked"]:
            lines.append(f"\n- {w}")

    if analysis.get("what_failed"):
        lines.append("\n\n**Failed:**")
        for w in analysis["what_failed"]:
            lines.append(f"\n- {w}")

    if analysis.get("proposals"):
        lines.append("\n\n**Proposals:**")
        for p in analysis["proposals"]:
            tag = " ✓ AUTO-APPLIED" if p.get("param_path") in " ".join(applied) else ""
            lines.append(
                f"\n- `{p['param_path']}`: {p.get('current_value')} → "
                f"{p.get('proposed_value')} (confidence {p.get('confidence', 0):.0%}){tag}"
                f"\n  _{p.get('reasoning', '')}_"
            )

    if analysis.get("risk_flags"):
        lines.append("\n\n**Risk flags:**")
        for f in analysis["risk_flags"]:
            lines.append(f"\n- ⚠️ {f}")

    lines.append("\n\n---")

    with open(journal, "a", encoding="utf-8") as f:
        f.writelines(lines)


def _send_telegram(analysis: dict, account: str, applied: list[str]):
    import os, urllib.request
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return

    rec = analysis.get("recommendation", "CONTINUE")
    regime = analysis.get("regime_assessment", "?")
    flags = analysis.get("risk_flags", [])
    props = analysis.get("proposals", [])

    icon = {"CONTINUE": "✅", "REDUCE_SIZE": "⚠️", "PAUSE": "🛑"}.get(rec, "ℹ️")
    msg = (
        f"{icon} *Intelligence — {account}*\n"
        f"{analysis.get('summary', '')}\n\n"
        f"Regime: `{regime}` | Action: *{rec}*\n"
        f"Proposals: {len(props)} | Auto-applied: {len(applied)}"
    )
    if flags:
        msg += "\n⚠️ " + " | ".join(flags)
    if applied:
        msg += "\n_Applied: " + ", ".join(applied) + "_"

    payload = json.dumps({"chat_id": chat, "text": msg, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload, headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def run(account: str) -> dict | None:
    print(f"\n=== Postmarket Intelligence: {account} ===")

    today = date.today().isoformat()
    out_path = REPO_ROOT / "data" / f"analysis_{account}_{today}.json"

    if out_path.exists():
        print("  Already done today — skipping.")
        return json.loads(out_path.read_text())

    today_trades = _load_today_trades(account)
    recent_trades = _load_recent_trades(account, n=30)
    cfg = _load_config(account)

    print(f"  {len(today_trades)} today's trades, {len(recent_trades)} recent trades loaded")

    prompt = _build_prompt(account, today_trades, recent_trades, cfg)

    print("  Calling Claude for analysis...")
    raw = _call_claude(prompt, timeout=120)

    if not raw:
        print("  No response from Claude — skipping.")
        return None

    analysis = _parse_response(raw)
    if not analysis:
        print(f"  Could not parse Claude response:\n{raw[:300]}")
        return None

    out_path.write_text(json.dumps(analysis, indent=2))
    print(f"  Analysis saved → {out_path.name}")

    applied = _auto_apply(account, analysis, cfg)
    if applied:
        analysis["auto_applied"] = applied
        print(f"  Auto-applied: {applied}")

    _append_journal(account, analysis, applied)
    _send_telegram(analysis, account, applied)

    print(f"  Done. Recommendation: {analysis.get('recommendation', 'CONTINUE')}")
    return analysis


if __name__ == "__main__":
    account = sys.argv[1] if len(sys.argv) > 1 else "tester"
    run(account)

"""
Weekly Intelligence Review — runs every Sunday.

Pipeline:
  1. Aggregate last 14 days of postmarket analysis JSONs + trade data
  2. Researcher agent proposes 1-3 strategy improvements
  3. Critic agent challenges each proposal
  4. Risk officer validates anything that survives
  5. Surviving proposals saved to data/proposals_{date}.json
  6. Telegram summary sent for human review

Nothing is auto-applied here — proposals require human approval via dashboard or Telegram.
"""

import json
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
CLAUDE_CMD = shutil.which("claude") or r"C:\Users\athar\AppData\Roaming\npm\claude.cmd"


def _load_recent_trades(account: str, days: int = 14) -> list[dict]:
    db = REPO_ROOT / "data" / "trades.db"
    if not db.exists():
        return []
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with sqlite3.connect(db) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT ts, symbol, side, pnl, notes, strategy, signal_features "
            "FROM trades WHERE account=? AND status='closed' AND ts >= ? ORDER BY ts",
            (account, cutoff),
        ).fetchall()
    return [dict(r) for r in rows]


def _load_recent_analyses(account: str, days: int = 14) -> list[dict]:
    analyses = []
    for i in range(days):
        d = date.today() - timedelta(days=i)
        path = REPO_ROOT / "data" / f"analysis_{account}_{d.isoformat()}.json"
        if path.exists():
            try:
                analyses.append({"date": d.isoformat(), **json.loads(path.read_text())})
            except Exception:
                pass
    return analyses


def _load_config(account: str) -> dict:
    cfg_path = REPO_ROOT / "config" / "accounts" / f"{account}.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def _call_claude(prompt: str, timeout: int = 180) -> str | None:
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


def _parse_json(raw: str) -> dict | None:
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


def _researcher_prompt(account: str, trades: list, analyses: list, cfg: dict) -> str:
    is_us = cfg.get("broker") == "alpaca"
    currency = "$" if is_us else "Rs"
    market = "US (NYSE/NASDAQ)" if is_us else "India (NSE)"

    wins = [t for t in trades if (t.get("pnl") or 0) > 0]
    losses = [t for t in trades if (t.get("pnl") or 0) <= 0]
    total_pnl = sum((t.get("pnl") or 0) for t in trades)
    win_rate = len(wins) / max(len(trades), 1) * 100

    # Collect recurring flags from daily analyses
    all_flags = []
    all_regimes = []
    for a in analyses:
        all_flags.extend(a.get("risk_flags", []))
        if a.get("regime_assessment"):
            all_regimes.append(a["regime_assessment"])

    regime_summary = ""
    if all_regimes:
        from collections import Counter
        most_common = Counter(all_regimes).most_common(2)
        regime_summary = ", ".join(f"{r}({c}d)" for r, c in most_common)

    sp = cfg.get("strategy_params", {})

    return f"""You are the researcher agent for an AI trading company.
Review 2 weeks of {market} trading for account '{account}' and propose improvements.

PERFORMANCE SUMMARY (last {len(trades)} trades over 14 days):
- Win rate: {win_rate:.0f}% ({len(wins)}W / {len(losses)}L)
- Total PnL: {currency}{total_pnl:.2f}
- Dominant regimes observed: {regime_summary or 'insufficient data'}

RECURRING ISSUES FROM DAILY ANALYSES:
{chr(10).join('- ' + f for f in all_flags) if all_flags else '- None flagged'}

CURRENT STRATEGY PARAMS:
{json.dumps(sp, indent=2)}

CURRENT RISK PARAMS:
- daily_loss_pct: {cfg.get('daily_loss_pct')}
- max_positions: {cfg.get('max_positions')}
- ml_threshold: {cfg.get('ml_threshold', 0.40)}
- use_ml: {cfg.get('use_ml', True)}

Your job: propose 1-3 concrete, evidence-based strategy improvements.

Reply with ONLY valid JSON:
{{
  "thesis": "1-2 sentence summary of what the data shows",
  "proposals": [
    {{
      "id": "P1",
      "title": "short title",
      "param_path": "strategy_params.vwap.entry_threshold_pct",
      "current_value": 0.4,
      "proposed_value": 0.5,
      "hypothesis": "what you expect to happen and why",
      "evidence": "specific evidence from the data above",
      "expected_impact": "e.g. reduce false signals by ~20%",
      "risk": "what could go wrong with this change",
      "reversible": true
    }}
  ]
}}

Rules:
- One variable at a time per proposal
- Never increase position size or relax risk params (daily_loss_pct, max_positions)
- All proposals must be reversible
- Only propose changes supported by actual patterns in the data
- If the data is too sparse to conclude anything, say so in thesis and give 0 proposals"""


def _critic_prompt(researcher_output: dict, trades: list, cfg: dict) -> str:
    return f"""You are the critic agent for an AI trading company.
Your default stance is REJECT. Challenge the researcher's proposals rigorously.

RESEARCHER OUTPUT:
{json.dumps(researcher_output, indent=2)}

TRADE COUNT: {len(trades)} trades (over 14 days)

For each proposal, check:
1. Is the sample size statistically meaningful? (< 30 trades per signal type = fragile)
2. Could the pattern be explained by market regime rather than strategy failure?
3. Is there lookahead bias in the reasoning?
4. Are the costs/slippage accounted for?
5. Is the change truly reversible without loss?

Reply with ONLY valid JSON:
{{
  "verdicts": [
    {{
      "proposal_id": "P1",
      "verdict": "ACCEPT|REJECT|MODIFY",
      "reasoning": "specific critique",
      "modified_value": null,
      "confidence": 0.7
    }}
  ],
  "overall_assessment": "PROCEED_WITH_ACCEPTED|INSUFFICIENT_DATA|ALL_REJECTED"
}}"""


def _risk_officer_prompt(proposals: list, cfg: dict) -> str:
    return f"""You are the risk officer for an AI trading company.
Validate these proposed config changes against safety rules.

PROPOSED CHANGES:
{json.dumps(proposals, indent=2)}

CURRENT CONFIG (key risk params):
- daily_loss_pct: {cfg.get('daily_loss_pct')} (must stay <= 2%)
- max_positions: {cfg.get('max_positions')} (must stay <= 3)
- capital: {cfg.get('capital')}
- max_position_size: {cfg.get('max_position_size') or cfg.get('max_position_size_inr')}
- mode: {cfg.get('mode', 'paper')}

Hard rules:
1. daily_loss_pct must remain <= 2%
2. max_positions must remain <= 3
3. No change to capital or position size that increases exposure > 25% of capital
4. No live mode changes without explicit human approval flag
5. Each change must be reversible

Reply with ONLY valid JSON:
{{
  "cleared": [
    {{
      "proposal_id": "P1",
      "status": "CLEARED|BLOCKED",
      "reason": "why"
    }}
  ],
  "summary": "one sentence"
}}"""


# These are the only params that can NEVER be auto-applied, no matter what agents say.
_HARD_BLOCKED_PATHS = {
    "mode",
    "daily_loss_pct",
    "max_positions",
    "capital",
    "max_position_size",
    "max_position_size_inr",
}


def _apply_cleared_proposals(account: str, proposals: list, cfg: dict) -> list[str]:
    """Auto-apply every cleared proposal except hard-blocked params."""
    applied = []
    cfg_path = REPO_ROOT / "config" / "accounts" / f"{account}.yaml"

    for prop in proposals:
        param_path = prop.get("param_path", "")
        # Block any proposal touching hard-protected params
        leaf = param_path.split(".")[-1]
        if leaf in _HARD_BLOCKED_PATHS or param_path in _HARD_BLOCKED_PATHS:
            prop["skip_reason"] = "hard-protected param — needs human decision"
            continue

        parts = param_path.split(".")
        node = cfg
        try:
            for part in parts[:-1]:
                node = node[part]
            old_val = node[parts[-1]]
            node[parts[-1]] = prop["proposed_value"]
            applied.append(f"{param_path}: {old_val} → {prop['proposed_value']}")
            prop["applied"] = True
        except (KeyError, TypeError) as e:
            prop["skip_reason"] = f"path not found: {e}"

    if applied:
        with open(cfg_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)

    return applied


def _send_telegram(account: str, proposals: list, summary: str, applied: list, out_path: Path):
    import os, urllib.request
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return

    if not proposals:
        msg = f"📊 *Weekly Review — {account}*\nNo proposals survived review this week. Keep trading."
    else:
        prop_lines = "\n".join(
            f"{'✅' if p.get('applied') else '⏭'} {p.get('title', p.get('param_path', '?'))}: "
            f"{p.get('current_value')} → {p.get('proposed_value')}"
            f"{' (skipped: ' + p.get('skip_reason','') + ')' if p.get('skip_reason') else ''}"
            for p in proposals
        )
        msg = (
            f"📊 *Weekly Review — {account}*\n"
            f"{summary}\n\n"
            f"*Proposals ({len(proposals)} cleared, {len(applied)} applied):*\n{prop_lines}"
        )

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
    print(f"\n{'='*60}")
    print(f"WEEKLY REVIEW — {account} — {date.today().isoformat()}")
    print(f"{'='*60}")

    out_path = REPO_ROOT / "data" / f"proposals_{account}_{date.today().isoformat()}.json"
    if out_path.exists():
        print("Already done this week — skipping.")
        return json.loads(out_path.read_text())

    trades = _load_recent_trades(account, days=14)
    analyses = _load_recent_analyses(account, days=14)
    cfg = _load_config(account)

    print(f"Loaded {len(trades)} trades, {len(analyses)} daily analyses")

    # ── Step 1: Researcher ────────────────────────────────────────────────────
    print("\nStep 1: Researcher proposing improvements...")
    researcher_raw = _call_claude(_researcher_prompt(account, trades, analyses, cfg))
    researcher_out = _parse_json(researcher_raw or "")

    if not researcher_out or not researcher_out.get("proposals"):
        print("  Researcher found no proposals — writing summary and exiting.")
        result = {"account": account, "date": date.today().isoformat(),
                  "thesis": (researcher_out or {}).get("thesis", "Insufficient data"),
                  "proposals": [], "status": "NO_PROPOSALS"}
        out_path.write_text(json.dumps(result, indent=2))
        _send_telegram(account, [], result["thesis"], out_path)
        return result

    print(f"  Researcher proposed {len(researcher_out['proposals'])} changes")

    # ── Step 2: Critic ────────────────────────────────────────────────────────
    print("\nStep 2: Critic reviewing proposals...")
    critic_raw = _call_claude(_critic_prompt(researcher_out, trades, cfg))
    critic_out = _parse_json(critic_raw or "")

    # Filter: only proposals the critic accepted or modified
    verdicts = {}
    if critic_out:
        for v in critic_out.get("verdicts", []):
            verdicts[v["proposal_id"]] = v

    accepted_proposals = []
    for prop in researcher_out["proposals"]:
        pid = prop.get("id", "")
        verdict = verdicts.get(pid, {})
        if verdict.get("verdict") == "ACCEPT":
            accepted_proposals.append(prop)
        elif verdict.get("verdict") == "MODIFY" and verdict.get("modified_value") is not None:
            prop["proposed_value"] = verdict["modified_value"]
            prop["critic_note"] = verdict.get("reasoning", "")
            accepted_proposals.append(prop)

    print(f"  Critic accepted {len(accepted_proposals)}/{len(researcher_out['proposals'])} proposals")

    if not accepted_proposals:
        result = {
            "account": account, "date": date.today().isoformat(),
            "thesis": researcher_out.get("thesis", ""),
            "proposals": [], "status": "ALL_REJECTED_BY_CRITIC",
            "critic_assessment": (critic_out or {}).get("overall_assessment", ""),
        }
        out_path.write_text(json.dumps(result, indent=2))
        _send_telegram(account, [], result["thesis"], out_path)
        return result

    # ── Step 3: Risk Officer ──────────────────────────────────────────────────
    print("\nStep 3: Risk officer validating...")
    risk_raw = _call_claude(_risk_officer_prompt(accepted_proposals, cfg))
    risk_out = _parse_json(risk_raw or "")

    cleared = {}
    if risk_out:
        for c in risk_out.get("cleared", []):
            cleared[c["proposal_id"]] = c

    final_proposals = []
    for prop in accepted_proposals:
        pid = prop.get("id", "")
        clearance = cleared.get(pid, {})
        if clearance.get("status") == "CLEARED":
            prop["risk_clearance"] = "CLEARED"
            final_proposals.append(prop)
        else:
            prop["risk_clearance"] = "BLOCKED"
            prop["blocked_reason"] = clearance.get("reason", "Failed risk check")

    print(f"  Risk officer cleared {len(final_proposals)}/{len(accepted_proposals)}")

    # ── Auto-apply everything that cleared all 3 agents ───────────────────────
    applied = []
    if final_proposals:
        print("\nAuto-applying cleared proposals...")
        applied = _apply_cleared_proposals(account, final_proposals, cfg)
        for a in applied:
            print(f"  Applied: {a}")
        skipped = [p for p in final_proposals if p.get("skip_reason")]
        for s in skipped:
            print(f"  Skipped (hard-protected): {s.get('param_path')}")

    # ── Save + Notify ─────────────────────────────────────────────────────────
    result = {
        "account": account,
        "date": date.today().isoformat(),
        "thesis": researcher_out.get("thesis", ""),
        "proposals": final_proposals,
        "applied": applied,
        "all_proposals_with_verdicts": [
            {**p, "verdict": verdicts.get(p.get("id", ""), {}).get("verdict", "NOT_REVIEWED")}
            for p in researcher_out["proposals"]
        ],
        "status": "APPLIED" if applied else ("CLEARED_NOT_APPLIED" if final_proposals else "ALL_BLOCKED"),
    }

    out_path.write_text(json.dumps(result, indent=2))
    print(f"\nSaved → {out_path.name}")

    # Append to journal
    journal = REPO_ROOT / "data" / "journal.md"
    with open(journal, "a", encoding="utf-8") as jf:
        jf.write(f"\n## Weekly Review — {date.today().isoformat()} ({account})\n")
        jf.write(f"**Thesis:** {result['thesis']}\n\n")
        if final_proposals:
            jf.write(f"**Auto-applied ({len(applied)}/{len(final_proposals)}):**\n")
            for p in final_proposals:
                tag = "✅ APPLIED" if p.get("applied") else f"⏭ SKIPPED ({p.get('skip_reason', '')})"
                jf.write(
                    f"- [{p.get('id')}] `{p.get('param_path')}`: "
                    f"{p.get('current_value')} → {p.get('proposed_value')} {tag}\n"
                    f"  _{p.get('hypothesis', '')}_\n"
                )
        else:
            jf.write("No proposals cleared this week.\n")
        jf.write("\n---\n")

    _send_telegram(account, final_proposals, result["thesis"], applied, out_path)
    return result


if __name__ == "__main__":
    account = sys.argv[1] if len(sys.argv) > 1 else "tester"
    run(account)

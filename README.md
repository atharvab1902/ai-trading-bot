# Trading Bot

AI-augmented intraday trading bot for Indian markets (Dhan broker). Claude Code orchestrates 7 specialist subagents for research, review, and journaling. A deterministic Python executor places trades.

## Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# edit .env with Dhan API keys, Telegram bot token
cp config/accounts/tester.yaml.example config/accounts/tester.yaml
# edit with your watchlist, capital, strategy

# 3. Init database
python scripts/init_db.py

# 4. Paper trade — run executor
python -m executor.executor --account tester

# 5. Run Claude routines (scheduled or manual)
claude -p "run premarket for account=tester"
claude -p "run postmarket for account=tester"
claude -p "run weekly for account=tester"
```

## Architecture

```
Claude Code (scheduled)         Python executor (9:15-15:30 IST)
       |                                  |
       v                                  v
   edits config.yaml  ------>  reads config, places trades via Dhan API
       |                                  |
       v                                  v
   7 subagents                     logs -> SQLite + Telegram
```

## Phases

1. **Dev (laptop)** — build, unit test, mock broker
2. **Paper (laptop, 4-8 weeks)** — Dhan sandbox or `mode: paper`
3. **Live tiny (₹5-10k)** — real capital, hard daily loss limit
4. **VPS migration** — only after 3 profitable months

## Safety

- Daily loss limit: 2% (auto-halt)
- Max positions: 1 (initially)
- AI cannot: place trades directly, move money, change risk limits without PR merge
- Every trade + decision logged

See `CLAUDE.md` for full operating rules.

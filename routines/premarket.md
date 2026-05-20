# Premarket routine (runs 08:30 IST)

**Goal:** decide today's plan and write it to `config/accounts/<account>.yaml`.

Invoked as: `claude -p "run premarket for account=<name>"`

## Steps

1. **Load context**
   - Read `config/accounts/<account>.yaml`
   - Read last 7 entries of `data/journal.md` (tail -100 lines)
   - Query `data/trades.db` for last 5 trades: `SELECT * FROM trades ORDER BY ts DESC LIMIT 5`
   - Check open positions: `SELECT * FROM positions WHERE status='open'`

2. **Fetch news** (delegate to `newsdesk` subagent)
   - Overnight global markets (US close, Asia overnight)
   - RBI / SEBI / policy news
   - Per-stock news for each symbol in watchlist
   - Output: sentiment score + one-line summary per stock

3. **Macro check** (Mondays only — delegate to `macro-watch`)
   - Fed / RBI / geopolitics impact for the week

4. **Propose today's plan**
   - Pick 1–3 stocks from watchlist where news sentiment is neutral-to-positive AND no event risk (earnings today = skip)
   - Decide strategy params (usually keep current, adjust only if journal suggests)
   - Write to a candidate `config.yaml`

5. **Validate** (delegate to `risk-officer`)
   - Capital check, position size check, stoploss sanity, watchlist sanity
   - If rejected: fix and re-validate, or halt and Telegram-alert the human

6. **Commit config**
   - `git commit -am "premarket <date>: <one-line rationale>"`
   - No push required (local run)

7. **Telegram notify**
   - "Plan for <date>: long RELIANCE on ORB breakout. Max loss ₹200. News: neutral."

## Constraints

- Do NOT add new symbols to the watchlist in premarket. That's a weekly-run decision.
- Do NOT increase position size or capital.
- If news sentiment is strongly negative across the watchlist, set `active_strategy: halt` and notify.
- If confidence is low (< some threshold), pick fewer stocks, not more.

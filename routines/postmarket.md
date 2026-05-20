# Postmarket routine (runs 16:00 IST)

**Goal:** reflect on today's trades, update the journal, detect patterns.

Invoked as: `claude -p "run postmarket for account=<name>"`

## Steps

1. **Pull today's trades**
   - `SELECT * FROM trades WHERE date(ts) = date('now', 'localtime')` on `data/trades.db`
   - `SELECT SUM(pnl) FROM trades WHERE date(ts) = date('now','localtime')`

2. **Delegate to `journaler`** subagent
   - Inputs: today's trades, config used, news summary from premarket
   - Output: journal entry appended to `data/journal.md`
   - Format:
     ```
     ## YYYY-MM-DD (<account>)
     **Trades:** 3 (2W / 1L)
     **PnL:** +₹187 (+1.87%)
     **Strategy:** orb (range=15m, sl=0.5%, tgt=1%)
     **Notes:** <what went right / wrong / pattern observed>
     **Tags:** #orb #reliance #winning-day
     ```

3. **Pattern check** (inline, not a subagent)
   - Scan last 20 journal entries for recurring tags
   - If a losing pattern appears 3+ times (e.g. "#fakeout-open 4x"), flag it for Sunday researcher review

4. **Telegram summary**
   - "EOD: 3 trades, +₹187 (+1.87%). Journal updated."

## Constraints

- Do not propose strategy changes here — that's the weekly job.
- Do not edit `config.yaml` here.
- Be honest: if a winning day was luck (low volume, random gap), say so in the journal.

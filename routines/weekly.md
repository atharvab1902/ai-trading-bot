# Weekly routine (runs Sunday 10:00 IST)

**Goal:** learn from the week, propose strategy upgrades, open a PR. Human reviews before Monday.

Invoked as: `claude -p "run weekly for account=<name>"`

## Steps

1. **Aggregate the week**
   - All trades from last 7 days (SQL query on trades.db)
   - Win rate, avg win, avg loss, expectancy, max drawdown
   - Top 3 losing trades — investigate each

2. **Delegate to `researcher`**
   - Propose 1–3 specific changes. Options:
     a) parameter tweak (e.g. range_minutes 15 → 20)
     b) new filter (e.g. skip trade if ATR < X)
     c) new strategy variant in `executor/strategies/`
   - Every proposal must include:
     - Hypothesis (why this should help)
     - Backtest over last 1 year on watchlist
     - Expected improvement vs current

3. **Delegate to `critic`**
   - Adversarial review of researcher's proposals
   - Check for: lookahead bias, overfitting (too many params, suspiciously perfect backtest), survivorship bias, ignoring costs
   - Reject ruthlessly. Better to keep status quo than ship overfit changes.

4. **Open PR**
   - New branch: `weekly/<YYYY-MM-DD>`
   - Commit surviving proposals (config + code changes)
   - PR body: metrics table, hypotheses, backtest results, critic's notes
   - Label: `needs-review`

5. **Telegram**
   - "Weekly PR ready: <github-url>. 2 proposals survived critic. Review before Monday 09:00."

## Constraints

- **Never auto-merge.** Human approves.
- No more than 3 changes per week (small steps compound; big jumps overfit).
- If the week's expectancy is negative and researcher can't identify a fixable cause, propose **reducing position size by 50%**, not a new strategy.
- If 2 consecutive weeks are unprofitable, propose pausing live mode and going back to paper.

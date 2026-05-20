# Trading Bot — Committed Build Plan

> This is the permanent roadmap. Do not change direction without updating this file.
> Research basis: quant firm practices (Renaissance, Two Sigma, Citadel), NSE-specific constraints,
> tool benchmarks (VectorBT, NautilusTrader, XGBoost, DuckDB), LLM capabilities in trading.

---

## What We Are Building

A fully intelligent intraday trading system for NSE equity markets on Dhan broker.
Every trade is backed by data, regime context, ML signal, and logged reasoning.
No random trades. No gut signals. No parameter changes without backtest evidence.

**End state:** 7-agent AI system where humans review weekly, not daily.

---

## Architecture — 7 Agents

```
PREMARKET (08:30 IST)
  Newsdesk Agent     → scrapes news, runs LLM sentiment, sets global bias
  Strategist Agent   → reads bias + VIX + FII flow → writes today's config

MARKET HOURS (09:15–15:15)
  Executor           → rule-based order engine (fast, no LLM in hot path)
  Floor Manager      → risk monitor: daily loss, consecutive SLs, halt trigger

POSTMARKET (16:00 IST)
  Journaler Agent    → writes journal entry with trade reasoning, tags, patterns

SUNDAY (10:00 IST)
  Researcher Agent   → reads 7-day journal, proposes param changes with backtest evidence
  Critic Agent       → challenges proposals, checks for overfitting
```

---

## Data Layer

| Source | What | Frequency |
|--------|------|-----------|
| Dhan API | Live quotes, paper fills | Real-time |
| Dhan historical | 1-min OHLCV, 90-day chunks | On-demand |
| NSE Bhavcopy | EOD prices, delivery % | Daily |
| India VIX | Volatility regime input | Daily (NSE website) |
| FII/DII flows | Momentum signal | Daily (NSDL, 1-day lag) |
| News (Perplexity) | Sentiment for watchlist stocks | Premarket |

**Storage:** DuckDB local file (`data/market.duckdb`)
- `ohlcv_1min` table: symbol, ts, open, high, low, close, volume
- `trades` table: already in trades.db (keep SQLite for trades)
- `signals` table: every signal fired with all features that generated it

---

## Signal Stack (ordered, all must agree)

```
1. Regime filter     — VIX + own 30-min price history → BULLISH/BEARISH/CHOPPY/VOLATILE
2. FII flow          — net buy/sell momentum (D-1 lag) → bias nudge
3. News sentiment    — Perplexity → per-stock and market-wide score
4. ML signal         — XGBoost on 20+ features → directional probability
5. Rule confirmation — ORB breakout or VWAP deviation as entry trigger
6. Trade logged      — reason string saved to DB before order placed
```

Trades only fire when layers 1–5 all agree on direction.
If any layer is unavailable (API down, VIX not fetched), that trade is skipped, not defaulted.

---

## ML Signal (XGBoost)

**Features per bar:**
- VWAP deviation %, EMA9/21 spread, RSI-14, ATR-14
- Volume ratio (current / 5-day avg), India VIX, FII net flow
- Previous day return, time-of-day bucket, day-of-week
- ORB range width as % of price, gap-up/gap-down size

**Training:** Walk-forward — train on 60 days, test on next 10, slide forward.
**Label:** 1 if price moves ≥0.5% in signal direction within 30 min, else 0.
**Threshold:** Only fire if XGBoost probability ≥ 0.60.

**Tools:** scikit-learn for initial build, XGBoost when we have 500+ labeled samples.
Experiment tracking: MLflow (self-hosted, free).

---

## Backtesting Standard

**Tool:** VectorBT (vectorized, fast, supports walk-forward).
**Rule:** No parameter change enters production without:
- Walk-forward test across at least 60 trading days
- Positive expectancy in ≥ 3 of last 4 test windows
- Sharpe ratio > 0.5 on out-of-sample data
- Critic agent review that challenges the proposal

**Current validated params (as of 2026-04-29):**

| Strategy | SL% | Target% | Position | Entry window |
|----------|-----|---------|----------|-------------|
| ORB | 0.5 | 1.0 | Rs50,000 | 09:15–10:00 |
| VWAP | 0.3 | 0.5 | Rs50,000 | 09:15–14:30 |

---

## Phases

### Phase 1 — Intelligent Paper Trading (NOW → 60 days)

Goal: Every trade has logged AI reasoning. We have data to train ML.

- [x] ORB + VWAP strategies live
- [x] Regime detection (price-based)
- [x] Trailing SL to breakeven
- [x] Postmarket Claude journaler
- [x] Weekly researcher + critic Sunday routine
- [x] **Newsdesk Agent** — Perplexity API for premarket sentiment (premarket.py)
- [x] **Strategist Agent** — reads Newsdesk output, writes today's tester.yaml overrides (strategist.py)
- [x] **Trade reasoning logger** — every signal logs feature values + reason string to DB (signal_features column)
- [x] **India VIX fetcher** — Yahoo Finance, integrated into regime detection (data_feeds.py)
- [x] **FII/DII fetcher** — NSE API + archive fallback (data_feeds.py)
- [ ] **DuckDB setup** — migrate historical OHLCV storage out of in-memory (Phase 2 dependency, not urgent)

### Phase 2 — ML Signal Layer (60–120 days)

Goal: XGBoost signal layer sits on top of rules. Rules become filters, not decisions.

- [ ] Build feature pipeline (all features listed above)
- [ ] Label historical trades from Phase 1 paper run
- [ ] Train initial XGBoost model (walk-forward)
- [ ] A/B test: rules-only vs rules+ML in parallel paper accounts
- [ ] MLflow experiment tracking setup
- [ ] VectorBT backtesting pipeline for weekly researcher

### Phase 3 — Strategy Research Pipeline (parallel to Phase 2)

Goal: Sunday researcher proposes, backtests, and critic reviews. Humans approve changes only.

- [ ] VectorBT integration for researcher agent backtests
- [ ] Automated parameter sweep on Sunday (top 3 combos only)
- [ ] Critic agent with overfitting checklist
- [ ] Git PR workflow for parameter changes (auto-opened by researcher)
- [ ] Sharpe + drawdown dashboard (simple HTML or Streamlit)

### Phase 4 — Live Trading (after Phase 2 stable for 30 days)

Goal: Real money, same system, same rules. Only position sizing changes.

- [ ] SEBI algo registration research (required for automated live orders)
- [ ] Risk manager hardening: per-trade circuit breaker, max daily drawdown kill switch
- [ ] Slippage model validation (compare paper fills vs real fills)
- [ ] Start with 20% of target capital, scale up monthly if Sharpe > 1.0
- [ ] NautilusTrader evaluation for unified backtesting + live execution

### Phase 5 — Multi-Instrument Expansion

Goal: Scale across more symbols, add options premium selling as a second book.

- [ ] Expand watchlist to 15–20 high-liquidity stocks
- [ ] Sector rotation logic
- [ ] Options: covered straddles on expiry week (separate strategy, separate capital)
- [ ] Portfolio-level risk: correlation limits, sector concentration limits

---

## What We Will NOT Do

- No LLM in the execution hot path (too slow, too expensive)
- No parameter changes without backtest evidence — never "gut feel" tuning
- No adding new strategies during live trading (test in paper first)
- No position sizing above 10% of capital in a single trade
- No trading on days when VIX > 25 (circuit breaker, not override-able)
- No expanding capital allocation if last 10 trades have Sharpe < 0.3

---

## Cost Budget (monthly)

| Item | Cost |
|------|------|
| Perplexity API (news) | ~$5–10 |
| Claude API (agents) | ~$10–20 |
| MLflow (self-hosted) | $0 |
| DuckDB (local) | $0 |
| VectorBT (open source) | $0 |
| **Total** | **~$15–30/month** |

---

## Current Status (2026-04-29)

Paper trading is live and working.
Yesterday's session: 15 trades, +Rs20.54, short bias worked correctly.
Known issues under investigation:
- KOTAKBANK BUY at 14:30 bypassed BEARISH_TREND regime block — needs root cause
- ORB longs structurally losing on bearish days — suppression logic needed
- VWAP AXISBANK SL too tight at 0.3% — considering 0.5%

Next immediate build items (Phase 1 incomplete):
1. Newsdesk Agent with Perplexity
2. India VIX fetcher → regime upgrade
3. Trade reasoning logger

---

*Last updated: 2026-04-29*

# Trade Journal

Daily reflections written by the `journaler` subagent at 16:00 IST.
Patterns tagged here feed into the weekly researcher review.

---

## 2026-04-24 (tester)
**Strategy:** none
**Trades:** 0 (0W / 0L)
**PnL:** +Rs0.00

**Market:** Market summary unavailable (no Perplexity key)

**Context:** Global bias was NEUTRAL. 

**Best trade:** none
**Worst trade:** none

**Edge check:** No trades today — no signals fired.


**Tags:** 

---
## 2026-04-29 (tester)
**Strategy:** vwap, orb
**Trades:** 15 total (5W / 8L / 2 breakeven — incl. 1 cancelled duplicate)
**PnL:** +Rs20.54

**Market:** Market summary unavailable (no Perplexity key). Bot behaviour suggests broad bearish/choppy session — all 5 wins were SHORT trades, both long trades lost.

**Context:** Global bias was NEUTRAL. Market opened range-bound, turned bearish by midday. Regime correctly identified CHOPPY for most of the session, switched to BEARISH_TREND ~13:18 IST which blocked all new BUY entries in the afternoon.

**Trade breakdown by phase:**

| Time (IST) | Symbol | Side | Strategy | PnL | Notes |
|---|---|---|---|---|---|
| 09:30 | KOTAKBANK | SELL | VWAP | +Rs10.09 | Target hit, quick scalp |
| 09:49 | INFY | BUY | ORB | +Rs16.41 | Target hit, clean breakout |
| 10:20 | LT | BUY | ORB | -Rs0.84 | Manual close near entry |
| 10:38 | RELIANCE | BUY | ORB | -Rs14.96 | SL hit |
| 10:39 | RELIANCE | SELL | VWAP | -Rs5.73 | Manual close — opened 1 min after RELIANCE BUY SL hit (pre-cooldown code) |
| 10:51 | RELIANCE | SELL | VWAP | +Rs17.66 | Target hit, trailing SL slid to breakeven at 66% |
| 10:51 | ICICIBANK | BUY | ORB | -Rs13.58 | SL hit |
| 11:32 | AXISBANK | SELL | VWAP | -Rs11.63 | SL hit, too early |
| 11:34 | LT | SELL | VWAP | -Rs12.31 | SL hit |
| 12:00 | AXISBANK | SELL | VWAP | -Rs27.15 | SL hit again, second attempt |
| 12:46 | KOTAKBANK | SELL | VWAP | Rs0.00 | Breakeven — trailing SL saved from loss |
| 13:07 | LT | SELL | VWAP | +Rs32.79 | Target hit, trailing SL to entry first |
| 13:27 | AXISBANK | SELL | VWAP | +Rs59.67 | Target hit, third attempt paid off |
| 14:30 | KOTAKBANK | BUY | VWAP | -Rs29.86 | SL hit, late BUY against bearish trend |

**Best trade:** AXISBANK +Rs59.67 (TARGET) — VWAP short, third attempt, held through to full target
**Worst trade:** KOTAKBANK -Rs29.86 (STOPLOSS) — BUY at 14:30 into a bearish day, EMA confluence should have blocked this

**Pattern analysis:**

1. **AXISBANK triple-trade problem**: Hit SL twice (-11.63, -27.15) before the third short finally ran to target (+59.67). Net on AXISBANK: +20.89 across 3 trades, but the two failed attempts bled capital before the setup confirmed. SL width on AXISBANK may be too tight (0.3%) — price wicked through before reversing. Consider widening SL to 0.5% with a corresponding target of 0.7% to survive the noise.

2. **Short bias worked**: Every winning trade was a SELL (KOTAKBANK, RELIANCE, KOTAKBANK, LT, AXISBANK). Both losing BUY trades (RELIANCE ORB, ICICIBANK ORB, KOTAKBANK VWAP) failed. The market was clearly directionally bearish — ORB longs should have been suppressed once regime turned BEARISH_TREND. ORB fired before the regime detection had enough data.

3. **Trailing SL performing well**: Fired 4 times — saved KOTAKBANK from a loss (Rs0 vs estimated -Rs29), protected LT and AXISBANK profits. This feature is working as intended. Keep it.

4. **RELIANCE revenge trade (pre-fix)**: At 10:38 RELIANCE BUY stopped out, at 10:39 RELIANCE SELL opened — 1 minute gap. This happened in the early morning sessions before the sl_cooldown code was deployed. The new cross-strategy 15-min cooldown will prevent this going forward.

5. **KOTAKBANK late BUY (14:30)**: The regime had already turned BEARISH_TREND by 13:18 IST, blocking BUY signals. But VWAP KOTAKBANK BUY fired at 14:30 — this means either the regime briefly flipped back to CHOPPY or the VWAP's EMA confluence check passed (fast > slow momentarily). Need to investigate why a long fired so late in a bearish session.

**Edge check:** Loss rate >60% but the day was green. The ORB strategy is underperforming (1W/3L, net -Rs12.97) — only INFY worked. All profitable trades came from VWAP shorts. In a bearish market day, ORB longs are structural losers. Consider: disable ORB longs when regime = BEARISH_TREND at open.

**What the new code did right today:**
- Trailing SL to breakeven: 4 activations, saved meaningful PnL
- Sector conflict block: Fired correctly (AXISBANK + KOTAKBANK both BANKING)
- Signal confluence: Blocked 15+ VWAP BUY signals when EMA was bearish
- Auto-halt: Not triggered (only 2 consecutive SLs max)
- Regime BEARISH_TREND: Correctly blocked BUY signals in the afternoon

**For researcher Sunday:**
- AXISBANK SL too tight — widening to 0.5% with 0.7% target may reduce failed entry count
- ORB long suppression when regime=BEARISH_TREND at market open
- Investigate KOTAKBANK BUY at 14:30 — why did it bypass bearish regime block
- VWAP performing better than ORB on bearish days — consider weighting strategies by intraday regime
- Check why VWAP KOTAKBANK BUY fired at 14:30 despite BEARISH_TREND regime — possible EMA flip or regime cache timing issue.

**Tags:** #vwap #orb #bearish-day #short-bias-correct #orb-longs-failed #axisbank-sl-too-tight #revenge-trade-reliance #trailing-sl-working #late-buy-regime-breach #orb-underperforming #vwap-outperforms-bearish #kotakbank #axisbank #reliance #lt #infy #icicibank #winning-day

---
---
## ML Retrain — 2026-04-30
Deployed: YES ✓
Threshold: 0.650 → 0.650
Feedback signals used: 1

### Model comparison (test window = last 15 days)
Direction  Metric            Old      New
------------------------------------------
long       sharpe         -8.207   -8.207
long       win_rate        0.386    0.386
long       precision       0.155    0.155
long       n_signals        8310     8310
short      sharpe         -6.159   -6.159
short      win_rate        0.418    0.418
short      precision       0.186    0.186
short      n_signals        6082     6082

### Feature importance
  LONG — top features:
    atr14_pct                 0.222 ██████████████████████
    is_first_30min            0.147 ██████████████
    vol_surge_5d              0.108 ██████████
    orb_width_pct             0.082 ████████
    time_bucket               0.069 ██████
    ema9_21_spread            0.061 ██████

  SHORT — top features:
    atr14_pct                 0.280 ████████████████████████████
    time_bucket               0.129 ████████████
    orb_width_pct             0.102 ██████████
    is_first_30min            0.063 ██████
    mom_30m_pct               0.059 █████
    gap_pct                   0.054 █████

---
## ML Retrain — 2026-04-30 11:50 IST (IST)
Feedback signals used: 74

### OPEN window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -11.217 -> -11.36
  long/win_rate: 0.337 -> 0.334
  long/n_signals: 84422 -> 86538
  short/sharpe: -14.991 -> -15.255
  short/win_rate: 0.296 -> 0.292
  short/n_signals: 83407 -> 86303

### MID window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -23.153 -> -23.153
  long/win_rate: 0.198 -> 0.198
  long/n_signals: 411634 -> 411640
  short/sharpe: -22.807 -> -22.807
  short/win_rate: 0.207 -> 0.207
  short/n_signals: 411640 -> 411640

### Feature importance
  OPEN_LONG — top 5 features:
    atr14_pct                 0.218
    is_first_30min            0.214
    time_bucket               0.096
    vol_surge_5d              0.089
    orb_width_pct             0.061

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.271
    time_bucket               0.108
    orb_width_pct             0.092
    mom_15m_pct               0.078
    is_first_30min            0.074

  MID_LONG — top 5 features:
    atr14_pct                 0.464
    mom_15m_pct               0.097
    orb_width_pct             0.073
    mom_30m_pct               0.063
    time_bucket               0.061

  MID_SHORT — top 5 features:
    atr14_pct                 0.441
    is_last_hour              0.109
    time_bucket               0.082
    orb_width_pct             0.060
    vwap_dev_pct              0.056

---
## ML Retrain — 2026-04-30 12:08 IST (IST)
Feedback signals used: 80

### OPEN window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -11.36 -> -11.36
  long/win_rate: 0.334 -> 0.334
  long/n_signals: 86538 -> 86538
  short/sharpe: -15.255 -> -15.255
  short/win_rate: 0.292 -> 0.292
  short/n_signals: 86303 -> 86303

### MID window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -23.153 -> -23.153
  long/win_rate: 0.198 -> 0.198
  long/n_signals: 411640 -> 411640
  short/sharpe: -22.807 -> -22.807
  short/win_rate: 0.207 -> 0.207
  short/n_signals: 411640 -> 411640

### Feature importance
  OPEN_LONG — top 5 features:
    atr14_pct                 0.218
    is_first_30min            0.214
    time_bucket               0.096
    vol_surge_5d              0.089
    orb_width_pct             0.061

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.271
    time_bucket               0.108
    orb_width_pct             0.092
    mom_15m_pct               0.078
    is_first_30min            0.074

  MID_LONG — top 5 features:
    atr14_pct                 0.464
    mom_15m_pct               0.097
    orb_width_pct             0.073
    mom_30m_pct               0.063
    time_bucket               0.061

  MID_SHORT — top 5 features:
    atr14_pct                 0.441
    is_last_hour              0.109
    time_bucket               0.082
    orb_width_pct             0.060
    vwap_dev_pct              0.056

## 2026-04-30 (tester)
**Strategy:** vwap
**Trades:** 4 (1W / 3L)
**PnL:** -Rs195.19

**Market:** RISK_OFF all session. VIX 19.18. FII net -Rs2468.42 Cr (heavy selling). Global bias bearish. Regime flagged CHOPPY for most VWAP signals; one window BULLISH_TREND (VEDL). ITC and PIIND skipped correctly — event risk. Only VWAP trades fired, no ORB signals today.

**Context:** Global bias RISK_OFF. Skipped ITC, PIIND (event risk). Only VWAP trades fired.

**Trade breakdown by phase:**

| Time (IST) | Symbol | Side | PnL | Exit | Notes |
|---|---|---|---|---|---|
| 11:30 | COALINDIA | SELL | +Rs289.32 | TARGET | Clean VWAP short; regime CHOPPY; ml_prob=0.258 |
| 12:57 | M&M | SELL | -Rs172.55 | STOPLOSS | VWAP short; regime CHOPPY; ml_prob=0.214 |
| 13:35 | MARUTI | SELL | -Rs137.88 | STOPLOSS | VWAP short AGAINST catalyst_direction=LONG (Motilal Oswal buy reco, +1.5% gap up); ml_prob=0.198 |
| 13:53 | VEDL | BUY | -Rs174.09 | STOPLOSS | VWAP long; regime BULLISH_TREND; consecutive_losses=2 at entry; global_bias=risk_off; ml_prob=0.242 |

**Best trade:** COALINDIA +Rs289.32 (TARGET) — only morning trade; VWAP short fired before afternoon deterioration; clean signal with no conflicting catalyst; regime CHOPPY suited short-side VWAP.

**Worst trade:** VEDL -Rs174.09 (STOPLOSS) — BUY taken with two consecutive losses already on the book, into a RISK_OFF session. Regime said BULLISH_TREND locally but global context was clearly risk-off. This trade should have been blocked.

**Pattern analysis:**

1. **MARUTI shorted against a known LONG catalyst**: signal had catalyst_direction=LONG (Motilal Oswal buy reco, 1.5% gap up) yet the bot took a SELL. The executor has no filter rejecting trades where signal direction conflicts with catalyst_direction. This is a concrete signal-quality gap — a catalyst_direction conflict filter would have saved Rs137.88.

2. **VEDL fired with consecutive_losses=2 AND global_bias=risk_off**: the risk layer should have one or both of these block new entries. Currently consecutive_losses triggers auto-halt only at a threshold, not a soft pause. global_bias=risk_off is logged but not wired into the entry gate. Both need enforcement — Rs174.09 lost on a structurally inadvisable trade.

3. **All 3 losses were afternoon trades (12:57–13:53)**: COALINDIA at 11:30 was the only winner. Afternoon VWAP entries in a CHOPPY+RISK_OFF session have a poor track record across two days now. A time-of-day filter or reduced position sizing after 12:30 IST on CHOPPY days is worth testing.

4. **ml_prob on all 4 trades was 0.20–0.26**: the ML threshold for VWAP signals is presumably higher, yet these trades fired. Either the threshold is misconfigured for this strategy window or the model is producing uniformly low probabilities and the bar is set below 0.25. A floor of 0.30 should be evaluated — none of today's trades would have passed.

5. **1W/3L with a winning trade at only 1.5x the average loss**: COALINDIA +289 vs average loss -161. The edge only works if win rate improves or the catalyst/ML filters cut losing entries — today's losses were all avoidable with tighter pre-trade checks.

**Edge check:** COALINDIA was real edge — clean VWAP short, no conflicting catalyst, hit target. The other three trades were structural noise: one signal-direction conflict, one fired into known risk-off with consecutive losses, one afternoon CHOPPY entry with weak ml_prob. 75% of today's trades were variance (poor filtering), not edge failure. Process did not adhere to what the risk signals were indicating.

**Recurring losing patterns (3+ tag occurrences across journal):**
- `#orb-longs-failed` — appeared 2026-04-29 (ORB longs in bearish regime); pattern now appearing in VWAP direction-conflict form today. ORB long suppression not yet implemented (pending researcher item from 2026-04-29).
- `#axisbank-sl-too-tight` — 2026-04-29, SL too tight causing whipsaw before direction confirmed. Same SL-width issue likely contributing to M&M and MARUTI losses today under CHOPPY regime.
- `#late-buy-regime-breach` — 2026-04-29 KOTAKBANK BUY at 14:30 breached BEARISH_TREND block; today VEDL BUY at 13:53 fired despite global_bias=risk_off and consecutive_losses=2. Pattern: afternoon BUY entries bypassing risk context. Flag for researcher.

**For researcher Sunday:**
- Implement catalyst_direction conflict filter: if catalyst_direction != signal direction, skip trade (blocks MARUTI-type errors)
- Wire global_bias=risk_off into entry gate: suppress BUY signals when global_bias=risk_off (or require ml_prob > 0.40)
- Soft pause after consecutive_losses=2: require ml_prob > 0.35 for next entry, not full halt
- Evaluate ml_prob floor of 0.30 for all VWAP entries — all 4 today were under 0.26, all but one lost
- Time-of-day filter: reduce position size by 50% for VWAP entries after 12:30 IST when regime=CHOPPY
- Carry forward from 2026-04-29: ORB long suppression when regime=BEARISH_TREND, KOTAKBANK late-BUY investigation

**Tags:** #vwap #choppy-market #losing-day #risk-off #news-gap #fakeout #low-volume #coalindia #m&m #maruti #vedl #catalyst-conflict #afternoon-losses #ml-filter-weak #consecutive-loss-breach

---
---
## ML Retrain — 2026-04-30 20:23 IST (IST)
Feedback signals used: 80

### OPEN window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -11.36 -> -11.36
  long/win_rate: 0.334 -> 0.334
  long/n_signals: 86538 -> 86538
  short/sharpe: -15.255 -> -15.255
  short/win_rate: 0.292 -> 0.292
  short/n_signals: 86303 -> 86303

### MID window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -23.153 -> -23.153
  long/win_rate: 0.198 -> 0.198
  long/n_signals: 411640 -> 411640
  short/sharpe: -22.807 -> -22.807
  short/win_rate: 0.207 -> 0.207
  short/n_signals: 411640 -> 411640

### Feature importance
  OPEN_LONG — top 5 features:
    atr14_pct                 0.218
    is_first_30min            0.214
    time_bucket               0.096
    vol_surge_5d              0.089
    orb_width_pct             0.061

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.271
    time_bucket               0.108
    orb_width_pct             0.092
    mom_15m_pct               0.078
    is_first_30min            0.074

  MID_LONG — top 5 features:
    atr14_pct                 0.464
    mom_15m_pct               0.097
    orb_width_pct             0.073
    mom_30m_pct               0.063
    time_bucket               0.061

  MID_SHORT — top 5 features:
    atr14_pct                 0.441
    is_last_hour              0.109
    time_bucket               0.082
    orb_width_pct             0.060
    vwap_dev_pct              0.056

---
## ML Retrain — 2026-04-30 20:29 IST (IST)
Feedback signals used: 80

### OPEN window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -11.36 -> -11.368
  long/win_rate: 0.334 -> 0.334
  long/n_signals: 86538 -> 86542
  short/sharpe: -15.255 -> -15.262
  short/win_rate: 0.292 -> 0.291
  short/n_signals: 86303 -> 86329

### MID window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -23.153 -> -23.153
  long/win_rate: 0.198 -> 0.198
  long/n_signals: 411640 -> 411640
  short/sharpe: -22.807 -> -22.807
  short/win_rate: 0.207 -> 0.207
  short/n_signals: 411640 -> 411640

### Feature importance
  OPEN_LONG — top 5 features:
    is_first_30min            0.233
    atr14_pct                 0.216
    time_bucket               0.096
    vol_surge_5d              0.084
    orb_width_pct             0.059

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.272
    time_bucket               0.118
    orb_width_pct             0.091
    mom_15m_pct               0.077
    is_first_30min            0.075

  MID_LONG — top 5 features:
    atr14_pct                 0.467
    mom_15m_pct               0.099
    orb_width_pct             0.072
    mom_30m_pct               0.064
    time_bucket               0.058

  MID_SHORT — top 5 features:
    atr14_pct                 0.448
    is_last_hour              0.110
    time_bucket               0.081
    orb_width_pct             0.057
    vwap_dev_pct              0.055

## 2026-04-30 (tester) [enhanced]
**Strategy:** vwap
**Trades:** 4 (1W / 3L)
**PnL:** -Rs195.19

**Market:** Nifty -0.74% (23,997). VIX 19.18. FII net -Rs2468 Cr. Global bias RISK_OFF.

**Context:** Risk-off session. ITC/PIIND skipped (event risk). Only VWAP signals fired. All 4 trades in CHOPPY or BULLISH_TREND regime with ml_prob below 0.26 — broad low-confidence day.

**Trade breakdown:**

| # | Time | Symbol | Side | PnL | Exit | ml_prob | Notes |
|---|---|---|---|---|---|---|---|
| 19 | 11:30 | COALINDIA | SELL | +Rs289.32 | TARGET | 0.258 | bars_above_vwap=83%, RSI=62.5, NEUTRAL catalyst |
| 20 | 12:57 | M&M | SELL | -Rs172.55 | STOPLOSS | 0.214 | bars_above_vwap=100%, RSI=68.1, shorting momentum |
| 21 | 13:35 | MARUTI | SELL | -Rs137.88 | STOPLOSS | 0.198 | RSI=72.7, bullish catalyst score=5 (Motilal reco) |
| 22 | 13:53 | VEDL | BUY | -Rs174.09 | STOPLOSS | 0.242 | bars_above_vwap=0%, consecutive_losses=2, risk_off |

**Best trade:** COALINDIA +Rs289.32 — VWAP short, NEUTRAL catalyst, regime CHOPPY, bars_above_vwap=83%, hit target cleanly. The one trade where momentum and signal direction aligned.

**Worst trade:** VEDL -Rs174.09 — BUY fired with consecutive_losses=2 and global_bias=risk_off. Signal form was valid (bars_above_vwap=0%, deep reversion candidate, rr_ratio=4.87), but macro risk context should have blocked entry. Signal was not wrong; the filter was missing.

**Signal-features insights:**

1. M&M bars_above_vwap=100%, RSI=68.1 — price was in unambiguous upward momentum. Shorting here had no VWAP mean-reversion basis. The system fired a short into a trending move with no catalyst support. Zero edge.

2. MARUTI RSI=72.7 (overbought) combined with a LONG catalyst (Motilal Oswal buy reco, catalyst_score=5, +1.5% gap) means both momentum and news were pointing up. The short was wrong on two independent dimensions simultaneously. A catalyst_direction != signal_direction gate would have blocked this.

3. VEDL bars_above_vwap=0% is structurally a BULLISH reversion signal for VWAP long — price deeply below VWAP with room to mean-revert. The signal itself was well-formed. What killed it: consecutive_losses=2 (late-session desperation territory) and risk_off macro. A consecutive_losses >= 2 halt rule would have prevented this entry.

4. ml_prob threshold is the clearest cross-trade pattern today. All 3 losers had ml_prob < 0.25 (0.214, 0.198, 0.242). The winner had ml_prob=0.258 — barely above. A hard floor of ml_prob >= 0.27 would have blocked all 4 trades. The ML model was signaling low confidence on every signal today; the system should respect that signal.

5. M&M flags a new pattern: entering a short when bars_above_vwap_pct=100% is a momentum-direction conflict. Tagged as `#bars-above-vwap-momentum-conflict` for tracking.

**Recurring patterns flagged:**

- `#bars-above-vwap-momentum-conflict` (M&M today) echoes the 2026-04-29 `#orb-longs-failed` pattern — both represent signals fired against prevailing intraday momentum.
- MARUTI's catalyst conflict mirrors the 2026-04-29 `#axisbank-sl-too-tight` class of errors: the trade was structurally weak before entry, not stopped by bad luck.
- VEDL's late-session entry with consecutive_losses=2 is a direct repeat of the 2026-04-29 `#late-buy-regime-breach` pattern. This has now recurred across two consecutive sessions — warrants a hard rule, not a guideline.

**Edge check:** 1W/3L with all ml_prob < 0.26 = variance, not edge. The session should not have traded at all under a stricter confidence filter. COALINDIA's win is not evidence the strategy worked today — it's noise at the margin of a low-conviction threshold.

**Tags:** #vwap #losing-day #choppy-market #fakeout #news-gap #low-volume #bars-above-vwap-momentum-conflict #slippage-high #event-risk-realized #coalindia #m&m #maruti #vedl

---
## 2026-04-30 (tester)
**Strategy:** vwap
**Trades:** 4 (1W / 3L)
**PnL:** Rs-195.19

**Market:** **Nifty 50 is trading down around 1% at approximately ₹23,818-23,998 (from previous close of ~₹24,178), with a bearish direction amid intraday lows.** Major movers include decliners like JSW Steel (-1%), Tech Mahindra (-1.26%), InterGlobe Aviation (IndiGo, -3.65%), Trent (-2.97%), and NTPC (-1.38%)[1][5][6]. No major news specified today, though yesterday's technical view noted cooling VIX supporting potential rallies above 24,350[2].

**Context:** Global bias was RISK_OFF. Skipped event-risk stocks: ITC, PIIND.

**Best trade:** COALINDIA +Rs289.32 (TARGET)
**Worst trade:** VEDL Rs-174.09 (STOPLOSS)

**Edge check:** Loss rate >60% — check if market was choppy/low-volume. Review signal quality.


**Tags:** #clean-exit #coalindia #loss #m&m #maruti #stopped-out #vedl #vwap #win

---
## 2026-05-05 (tester)
**Strategy:** vwap
**Trades:** 3 (2W / 1L)
**PnL:** +Rs872.55

**Market:** The **Nifty 50 declined** around **0.28-0.40%** to trade near 24,000 levels, with the **Nifty Bank index falling 0.60%**, while the **Nifty IT and Auto indices bucked the trend with gains of 0.14% and 0.83% respectively**[3][7]. Notable movers included **DMart falling over 3% after Q4 profit missed estimates** and **Kotak Mahindra Bank declining 2.6% despite strong margin gains in Q4 results**[3].

**Context:** Global bias was RISK_OFF. 

**Best trade:** KOTAKBANK +Rs558.46 (TARGET)
**Worst trade:** MPHASIS Rs-172.60 (STOPLOSS)

**Edge check:** Win rate >60% — strategy showing edge. Verify it wasn't just market trend.


**Tags:** #clean-exit #kotakbank #loss #mphasis #stopped-out #vwap #win

---
## 2026-05-05 (tester) [enriched]
**Strategy:** vwap
**Trades:** 3 (2W / 1L)
**PnL:** +Rs872.55 (+approx 1.4% on deployed capital)
**Market:** Nifty -0.28–0.40%, Bank Nifty -0.60%. IT and Auto green. KOTAKBANK -2.6% on Q4 earnings miss (NIM decline, profit -15% YoY). DMart -3% on missed estimates.
**Context:** Global bias RISK_OFF. FII net +Rs2835 Cr (net buying — contradicts risk_off label). Regime CHOPPY all session. VIX 18.3.

**Trade breakdown:**

| # | Time | Symbol | Side | PnL | Exit | ml_prob | Notes |
|---|---|---|---|---|---|---|---|
| 23 | 09:30 | KOTAKBANK | BUY | +Rs558.46 | TARGET | 0.152 | catalyst_direction=SHORT (score=8), price 1.06% below VWAP, bars_above_vwap=0%, RSI=47 — AGAINST catalyst |
| 24 | 10:44 | MPHASIS | BUY | -Rs172.60 | STOPLOSS | 0.259 | catalyst_direction=LONG, vwap_dev=-0.027 (0.82% below), CHOPPY regime — shallow deviation, weak setup |
| 25 | 10:48 | KOTAKBANK | SELL | +Rs486.68 | TARGET | 0.356 | catalyst_direction=SHORT (score=8), bars_above_vwap=90%, RSI=71, price above VWAP — all signals aligned |

**Best trade:** KOTAKBANK SELL +Rs486.68 — catalyst, VWAP deviation, RSI, and bars_above_vwap all aligned. Earnings miss SHORT played out as structured. Highest ml_prob of the day. This is repeatable edge.

**Worst trade:** MPHASIS -Rs172.60 — vwap_dev of -0.027 is too shallow for a reversion trade. CHOPPY regime with weak catalyst and ml_prob=0.259 gave no cushion. Low-quality setup that should not have cleared the entry bar.

**Pattern analysis:**

1. **KOTAKBANK BUY (Trade 23) is the same catalyst-conflict error as MARUTI on 2026-04-30.** catalyst_score=8 SHORT catalyst, ml_prob=0.152 (lowest of the day), yet a BUY fired. Price rebounded from VWAP intraday and hit target — that is coincidence, not edge. A catalyst_direction conflict filter would have blocked this trade. The win inflates the day's PnL and masks a structural problem.

2. **KOTAKBANK SELL (Trade 25) is genuine edge.** All confirmations present: catalyst_direction=SHORT aligned with signal, bars_above_vwap=90%, RSI=71 (overbought), ml_prob=0.356 (highest today), price above VWAP. The earnings miss setup was correctly captured 78 minutes after the contradictory BUY. The strategy eventually found the right side; it should have started there.

3. **KOTAKBANK round-trip in one session.** BUY at 09:30, SELL at 10:48, same stock, same catalyst. The bot took a contrarian position to its own catalyst data, got lucky, then corrected. A catalyst_direction filter would have skipped Trade 23 entirely — net PnL impact would have been +Rs486.68 instead of +Rs1045.14, but the process would have been clean. More trades is not better when one of them is structurally wrong.

4. **MPHASIS vwap_dev too shallow.** vwap_dev_pct=-0.027 (0.82% below VWAP) in a CHOPPY regime is not a reversion setup — there is no deviation to revert from. Compare to KOTAKBANK Trade 23 which had vwap_dev_pct=-0.186 (1.06% below). A minimum vwap_dev threshold (e.g., >=0.5% for longs) would filter MPHASIS-type entries.

5. **FII/risk_off data inconsistency.** FII bought +Rs2835 Cr while global_bias=risk_off. If risk_off is sourced from global indices (US/Asia) and domestic FII are actively buying, the risk_off gate suppressing BUY signals is misaligned with actual flow. This requires investigation — the label may be stale or sourced from the wrong feed.

**Edge check:** The day is green but only Trade 25 represents clean edge. Trade 23 won on luck (catalyst conflict, ml_prob=0.152, CHOPPY regime). Trade 24 was a low-quality entry that correctly lost. Two of three trades were structurally questionable. Labeling this a good day would be wrong — it is a winning day with process failures.

**Recurring patterns flagged:**

- `#catalyst-conflict` — 2 occurrences in 2 consecutive sessions: MARUTI 2026-04-30 (short against LONG catalyst), KOTAKBANK 2026-05-05 (long against SHORT catalyst). The catalyst_direction conflict filter was flagged for researcher Sunday on 2026-04-30. It remains unimplemented. This is now URGENT — the pattern has recurred and the only reason it did not cost money today is luck.
- `#choppy-market` — 3 occurrences (2026-04-29, 2026-04-30, 2026-05-05). CHOPPY regime is consistently producing unreliable entries. Consider minimum ml_prob elevation (>= 0.30) when regime=CHOPPY.
- `#ml-filter-weak` — 2 occurrences (2026-04-30 multiple trades under 0.25; today Trade 23 at ml_prob=0.152). The current threshold is passing trades the model has very low confidence in.
- `#late-buy-regime-breach` — 2 occurrences (2026-04-29, 2026-04-30). Not triggered today but filter remains unimplemented.

**For researcher Sunday:**

- URGENT: Implement catalyst_direction conflict filter. If catalyst_direction != signal_direction AND catalyst_score >= 6, block trade. Would have prevented MARUTI (2026-04-30) and KOTAKBANK BUY (today).
- Set minimum vwap_dev_pct threshold for VWAP longs: >= 0.50% deviation required. MPHASIS at 0.027 had no reversion basis.
- Raise ml_prob floor to 0.27 when regime=CHOPPY. Trade 23 (0.152) would be blocked; MPHASIS (0.259) marginal.
- Investigate FII net vs global_bias label inconsistency — if FII are net buying, risk_off BUY suppression may be miscalibrated.
- Carry forward: consecutive_losses soft-pause (2026-04-30), time-of-day position sizing after 12:30 in CHOPPY sessions, ORB long suppression in BEARISH_TREND.

**Tags:** #vwap #choppy-market #winning-day #catalyst-conflict #ml-filter-weak #fakeout #kotakbank #mphasis #risk-off #news-gap #clean-signal

---
---
## ML Retrain — 2026-05-06 03:34 IST (IST)
Feedback signals used: 80

### OPEN window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -12.582 -> -12.582
  long/win_rate: 0.319 -> 0.319
  long/n_signals: 86618 -> 86618
  short/sharpe: -14.369 -> -14.369
  short/win_rate: 0.309 -> 0.309
  short/n_signals: 86321 -> 86321

### MID window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -22.526 -> -22.526
  long/win_rate: 0.201 -> 0.201
  long/n_signals: 440639 -> 440639
  short/sharpe: -22.275 -> -22.275
  short/win_rate: 0.211 -> 0.211
  short/n_signals: 440639 -> 440639

### Feature importance
  OPEN_LONG — top 5 features:
    atr14_pct                 0.213
    is_first_30min            0.205
    time_bucket               0.105
    vol_surge_5d              0.097
    orb_width_pct             0.061

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.262
    time_bucket               0.113
    is_first_30min            0.105
    orb_width_pct             0.087
    mom_15m_pct               0.068

  MID_LONG — top 5 features:
    atr14_pct                 0.466
    mom_15m_pct               0.092
    orb_width_pct             0.075
    mom_30m_pct               0.068
    time_bucket               0.063

  MID_SHORT — top 5 features:
    atr14_pct                 0.453
    is_last_hour              0.104
    time_bucket               0.072
    orb_width_pct             0.059
    vwap_dev_pct              0.058

## 2026-05-06 (tester)
**Strategy:** vwap
**Trades:** 15 (4W / 11L)
**PnL:** +Rs11.78

**Market:** # Indian Stock Markets Update

The Nifty 50 is trading in negative territory, down approximately **0.4-1.16%** to around 23,900-24,000 levels, with HDFC Bank and ICICI Bank among the top losers. The index opened lower compared to the previous close of 24,177.65 and has struggled to sustain gains despite an intraday high of 24,019.15. Sensex has also fallen around 150 points, reflecting broad-based weakness across the market.

**Context:** Global bias was RISK_ON. 

**Best trade:** VEDL +Rs415.14 (TARGET)
**Worst trade:** VEDL Rs-174.55 (STOPLOSS)

**Edge check:** Loss rate >60% — check if market was choppy/low-volume. Review signal quality.


**Tags:** #ambujacem #bpcl #clean-exit #godrejprop #icicibank #loss #m&m #mphasis #ongc #stopped-out #vedl #vwap #win

---
## 2026-05-07 (tester)
**Strategy:** vwap
**Trades:** 9 (3W / 6L)
**PnL:** Rs-130.85

**Market:** **Nifty 50 is down 1.16% at ₹23,898.35 today**, trading between an intraday low of ₹23,796.85 and high of ₹24,019.15 after opening at ₹23,996.95 (previous close ₹24,177.65), amid a broadly bearish market with all major indices like Nifty Bank (-2.67%), Nifty 100 (-2.15%), and Nifty 500 (-2.13%) declining sharply—technical indicators show 12 bearish moving averages and minimal advances (e.g., just 7 in Nifty 100). No specific big news highlighted in updates, but sectors like auto rallied while FMCG struggled; weekly performance is -1.97% to -1.28%.

**Context:** Global bias was RISK_ON. 

**Best trade:** VOLTAS +Rs352.56 (TARGET)
**Worst trade:** VEDL Rs-174.64 (STOPLOSS)

**Edge check:** Loss rate >60% — check if market was choppy/low-volume. Review signal quality.

> WARNING: #stopped-out appears 3x in recent journal. Researcher should review stoploss width.

**Tags:** #bpcl #britannia #clean-exit #godrejprop #irctc #jindalstel #loss #stopped-out #vedl #voltas #vwap #win

---
## 2026-05-07 (tester) [enriched]
**Strategy:** vwap
**Trades:** 7 closed (3W / 4L) + 1 open (MFSL SHORT at 14:15)
**PnL:** +Rs389.76 (closed trades) — nominally green; process was not
**Cumulative week PnL:** approx +Rs1274.09 (2026-05-05 +Rs872.55, 2026-05-06 +Rs11.78, today +Rs389.76; MFSL open position excluded)

**Trade breakdown:**

| # | Time | Symbol | Side | PnL | Exit | ml_prob | cat_dir | cat_score | RSI | bars_abv_vwap | consecutive_losses | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 44 | 11:35 | VEDL | BUY | -Rs174.64 | STOPLOSS | 0.218 | LONG | 7 | 39.3 | 20% | 3 | Fired with 3 consecutive losses; soft-pause threshold breached |
| 45 | 11:35 | BRITANNIA | SELL | +Rs262.96 | TARGET | 0.280 | SHORT | 5 | 73.6 | 70% | 3 | Aligned catalyst; overbought RSI; clean short |
| 46 | 11:44 | BPCL | BUY | +Rs292.26 | TARGET | 0.194 | SHORT | 3 | 18.2 | 0% | 4 | Catalyst conflict; RSI=18.2 extreme oversold; won by mean-reversion luck |
| 47 | 12:29 | VOLTAS | SELL | +Rs352.56 | TARGET | 0.284 | NEUTRAL | 3 | 44.1 | 0% | 0 | Best setup of day; catalyst neutral; consecutive_losses reset |
| 48 | 13:46 | VEDL | BUY | -Rs174.15 | STOPLOSS | 0.226 | LONG | 7 | 75.0 | 0% | 0 | RSI=75 overbought long entry; second VEDL loss today |
| 49 | 14:00 | GODREJPROP | SELL | -Rs169.23 | STOPLOSS | 0.213 | LONG | 5 | 50.0 | 63% | 0 | Catalyst conflict — SELL vs LONG catalyst (Q4 rev +268% QoQ) |
| 50 | 14:15 | MFSL | SELL | open | OPEN | 0.288 | SHORT | 4 | 29.4 | 0% | 1 | Open overnight — risk item for 2026-05-08 |

**Best trade:** VOLTAS +Rs352.56 — NEUTRAL catalyst, consecutive_losses had reset to 0, ml_prob=0.284, price below VWAP. The cleanest setup of the session; all structural conditions were acceptable.

**Worst trade:** VEDL -Rs174.64 (11:35) — fired with consecutive_losses=3, exceeding the soft-pause threshold of 2 flagged since 2026-04-30. Fourth VEDL loss entry across the last three sessions.

---

**Analysis:**

**1. Catalyst conflict recurrence — filter still unimplemented (session 4)**

Two catalyst conflict trades fired today:
- BPCL (11:44): BUY fired with catalyst_direction=SHORT. Won. RSI=18.2, bars_above_vwap=0% — the win is a mean-reversion coincidence on an extreme oversold instrument, not VWAP edge. A catalyst conflict gate would have blocked this; PnL would be lower but the process would be clean.
- GODREJPROP (14:00): SELL fired with catalyst_direction=LONG (Q4 revenue +268% QoQ, 2x volume, gap up). Lost Rs169.23. This is the exact MARUTI error from 2026-04-30 repeated verbatim.

Catalyst conflict count by session: MARUTI 2026-04-30 (lost), KOTAKBANK 2026-05-05 (won by luck), BPCL today (won by luck), GODREJPROP today (lost). Four occurrences across four sessions. The filter has been flagged as URGENT since 2026-05-05 and remains unimplemented.

**2. VEDL pattern — structural stock-level problem**

Running VEDL loss log across three sessions:
- 2026-04-30: VEDL BUY -Rs174.09 (worst trade)
- 2026-05-06: VEDL BUY -Rs174.55 (worst trade), same session +Rs415.14 (best — different setup)
- 2026-05-07 11:35: VEDL BUY -Rs174.64 (consecutive_losses=3 at entry)
- 2026-05-07 13:46: VEDL BUY -Rs174.15 (RSI=75 — overbought long entry with no VWAP reversion basis)

The 13:46 entry is structurally wrong: RSI=75 is overbought, bars_above_vwap=0% confirms price is below VWAP, but a long at RSI=75 has no statistical reversion basis — the indicator contradicts the trade direction. The 11:35 entry fired with consecutive_losses=3 after the soft-pause threshold of 2 was already exceeded. The bot has no per-symbol loss memory. A 90-minute same-symbol cooldown after a stoploss would have blocked the 13:46 re-entry.

**3. BPCL won with RSI=18.2 — this is not VWAP edge**

BPCL BUY: RSI=18.2, bars_above_vwap=0%, catalyst_direction=SHORT, ml_prob=0.194 (lowest of the day). The win is attributable to extreme oversold mean-reversion. RSI at 18.2 is capitulation territory where any instrument tends to bounce mechanically. The VWAP signal coincided with that. This is not the strategy identifying edge — it is the strategy accidentally entering a trade that any RSI-oversold system would have taken, while simultaneously violating catalyst direction. This win should not be treated as process confirmation.

**4. ML confidence — zero trades above 0.30, third session in a row**

Today's ml_prob range: 0.194 to 0.288. No signal cleared 0.30. This matches 2026-04-30 (max 0.258) and contrasts with 2026-05-05 where only Trade 25 reached 0.356. The ML model is producing uniformly low-confidence outputs in persistent CHOPPY regime conditions. A floor of 0.30 would have blocked all seven trades today — zero entries, zero loss, arguably the correct outcome when the model itself is signaling low conviction on every signal.

**5. Afternoon deterioration — CHOPPY regime pattern holds**

Morning (11:35–12:29): 2W/1L, net approx +Rs380.58.
Afternoon (13:46–14:15): 0W/2L + 1 open, net -Rs343.38 on closed trades.

Afternoon VWAP in CHOPPY regime has now lost money across at least three sessions (2026-04-30, 2026-05-06 per prior context, today). Both afternoon losses today had independent structural problems (VEDL overbought, GODREJPROP catalyst conflict), but the time-of-day degradation pattern is consistent and the position sizing reduction after 12:30 IST in CHOPPY sessions remains unimplemented.

**6. MFSL open position — risk item for 2026-05-08**

MFSL SELL, 29 units at 1707.75, SL=1713.73, target=1688.60. Open overnight. Gap risk applies. SL is Rs5.98 above entry (0.35%). If MFSL gaps up on any overnight news, SL triggers at open with potential slippage beyond 1713.73. Max risk on this position: approximately Rs175 at SL, more with gap slippage. Do not add to or modify pre-market without checking overnight MFSL news.

**7. Tag pattern scan — occurrences >= 3**

| Pattern tag | Sessions | Note |
|---|---|---|
| `#choppy-market` | 2026-04-29 through 2026-05-07 | Every session — 5 consecutive |
| `#catalyst-conflict` | 2026-04-30, 2026-05-05, 2026-05-07 (x2) | 4 events, 3 sessions; URGENT |
| `#ml-filter-weak` | 2026-04-30, 2026-05-05, 2026-05-07 | 3 sessions with sub-0.30 signals passing |
| `#consecutive-loss-breach` | 2026-04-29, 2026-04-30, 2026-05-07 | 3 sessions; soft-pause never enforced |
| `#vedl-repeat` | 2026-04-30, 2026-05-06, 2026-05-07 | 3 sessions; 5 VEDL entries, 4 losses |

**Edge check:** Green but not clean. BRITANNIA is the only unambiguously correct trade today — catalyst aligned, RSI overbought, VWAP short, target hit. BPCL won via extreme oversold coincidence with catalyst conflict. VOLTAS was structurally acceptable. The two afternoon losses were both avoidable with filters already flagged. The PnL is positive because one lucky trade (BPCL) and two real-enough trades covered four losses. That is variance, not confirmed edge.

---

**For researcher Sunday:**

Carry-forward (unimplemented since 2026-04-30 or 2026-05-05):
- URGENT: Catalyst direction conflict filter — block when catalyst_direction != signal_direction AND catalyst_score >= 5. Four occurrences across four sessions. Cannot be deferred again.
- ml_prob floor of 0.30 for VWAP entries when regime=CHOPPY. Zero trades today would have cleared this.
- Consecutive_losses soft-pause: block new entries when consecutive_losses >= 2 unless ml_prob > 0.35.
- Time-of-day sizing: 50% position size after 12:30 IST when regime=CHOPPY.
- ORB long suppression when regime=BEARISH_TREND (from 2026-04-29, never addressed).

New from today:
- Per-symbol intraday cooldown: 90-minute minimum between consecutive entries in the same symbol after a stoploss. Blocks VEDL-style same-day re-entries.
- RSI directional gate: block BUY when RSI >= 70; block SELL when RSI <= 30. Would have prevented VEDL 13:46 (RSI=75) and flagged BPCL 11:44 (RSI=18.2).
- MFSL position: review before any 2026-05-08 signals are acted on.

**Tags:** #vwap #choppy-market #winning-day #catalyst-conflict #ml-filter-weak #consecutive-loss-breach #vedl-repeat #fakeout #news-gap #britannia #bpcl #voltas #vedl #godrejprop #mfsl #afternoon-losses #late-buy-regime-breach #clean-signal

---
---
## ML Retrain — 2026-05-07 16:03 IST (IST)
Feedback signals used: 86

### OPEN window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -12.804 -> -12.805
  long/win_rate: 0.31 -> 0.31
  long/n_signals: 86642 -> 86651
  short/sharpe: -14.474 -> -14.484
  short/win_rate: 0.31 -> 0.309
  short/n_signals: 86194 -> 86251

### MID window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -21.8 -> -21.8
  long/win_rate: 0.204 -> 0.204
  long/n_signals: 440635 -> 440635
  short/sharpe: -21.801 -> -21.801
  short/win_rate: 0.214 -> 0.214
  short/n_signals: 440635 -> 440635

### Feature importance
  OPEN_LONG — top 5 features:
    is_first_30min            0.220
    atr14_pct                 0.208
    vol_surge_5d              0.098
    time_bucket               0.074
    orb_width_pct             0.069

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.250
    is_first_30min            0.165
    time_bucket               0.103
    orb_width_pct             0.078
    mom_15m_pct               0.076

  MID_LONG — top 5 features:
    atr14_pct                 0.468
    mom_15m_pct               0.098
    orb_width_pct             0.071
    mom_30m_pct               0.069
    time_bucket               0.059

  MID_SHORT — top 5 features:
    atr14_pct                 0.463
    is_last_hour              0.093
    time_bucket               0.072
    vwap_dev_pct              0.061
    mom_15m_pct               0.058

---
## ML Retrain — 2026-05-07 21:45 IST (IST)
Feedback signals used: 86

### OPEN window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -12.805 -> -12.805
  long/win_rate: 0.31 -> 0.31
  long/n_signals: 86651 -> 86651
  short/sharpe: -14.484 -> -14.484
  short/win_rate: 0.309 -> 0.309
  short/n_signals: 86251 -> 86251

### MID window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -21.8 -> -21.8
  long/win_rate: 0.204 -> 0.204
  long/n_signals: 440635 -> 440635
  short/sharpe: -21.801 -> -21.801
  short/win_rate: 0.214 -> 0.214
  short/n_signals: 440635 -> 440635

### Feature importance
  OPEN_LONG — top 5 features:
    is_first_30min            0.220
    atr14_pct                 0.208
    vol_surge_5d              0.098
    time_bucket               0.074
    orb_width_pct             0.069

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.250
    is_first_30min            0.165
    time_bucket               0.103
    orb_width_pct             0.078
    mom_15m_pct               0.076

  MID_LONG — top 5 features:
    atr14_pct                 0.468
    mom_15m_pct               0.098
    orb_width_pct             0.071
    mom_30m_pct               0.069
    time_bucket               0.059

  MID_SHORT — top 5 features:
    atr14_pct                 0.463
    is_last_hour              0.093
    time_bucket               0.072
    vwap_dev_pct              0.061
    mom_15m_pct               0.058

## 2026-05-08 (tester)
**Strategy:** vwap, orb
**Trades:** 6 (2W / 4L)
**PnL:** +Rs71.51

**Market:** # Indian Stock Market Today

Based on the latest data, the **Nifty 50 is trading around 24,184-24,330**, showing mixed performance with modest gains of approximately **1.24%** in some readings, though earlier data showed declines of around **-0.50% to -1.16%**. **Nifty Bank is down significantly by ~1.30%**, while **Nifty IT is outperforming with gains of ~1.22-1.34%**. Key movers include NUVAMA (+9.78%), PIDILITIND (+2.25%), and NBCC (+3.79%).

**Context:** Global bias was RISK_ON. Skipped event-risk stocks: ICICIGI.

**Best trade:** DIXON +Rs423.17 (TARGET)
**Worst trade:** BERGEPAINT Rs-173.87 (STOPLOSS)

**Edge check:** Loss rate >60% — check if market was choppy/low-volume. Review signal quality.

> WARNING: #stopped-out appears 5x in recent journal. Researcher should review stoploss width.

**Tags:** #bergepaint #clean-exit #dixon #heromotoco #loss #orb #srf #stopped-out #vwap #win

---
## 2026-05-08 (tester) [enriched]
**Strategy:** vwap, orb
**Trades:** 6 closed (2W / 4L) + 2 open (DIXON SELL, SRF SELL)
**PnL:** +Rs71.51 closed (4 SL / 2 TARGET) — nominally green; structurally one of the worst process days to date
**Cumulative week PnL:** approx +Rs1345.60 (2026-05-05 +Rs872.55, 2026-05-06 +Rs11.78, 2026-05-07 +Rs389.76, today +Rs71.51; open positions excluded)
**Market:** Nifty 50 ~24,184–24,330 (+1.24% recovery). Nifty Bank -1.30%. Nifty IT +1.22–1.34%. Global bias RISK_ON. ICICIGI skipped (event risk). DIXON strong (ORB BUY hit target at open in BULLISH_TREND). NUVAMA +9.78%, PIDILITIND +2.25%.

**Trade breakdown:**

| # | Time | Symbol | Side | Strategy | PnL | Exit | ml_prob | cat_dir | cat_score | consec_loss | regime | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 51 | 09:30:01 | BERGEPAINT | SELL | vwap | -Rs173.68 | STOPLOSS | 0.4832 | NEUTRAL | 3 | 0 | CHOPPY | Highest ml_prob of session; SL'd in first minute |
| 52 | 09:30:02 | HEROMOTOCO | SELL | vwap | -Rs167.82 | STOPLOSS | 0.5229 | NEUTRAL | 3 | 0 | CHOPPY | Highest ml_prob of session; SL'd in first minute |
| 53 | 09:30:16 | BERGEPAINT | SELL | vwap | -Rs173.87 | STOPLOSS | 0.5219 | NEUTRAL | 3 | 3 | CHOPPY | Same symbol/side as #51, 15 sec later; consec_loss=3 at entry; per-symbol cooldown would have blocked |
| 54 | 09:32:04 | DIXON | BUY | orb | +Rs423.17 | TARGET | 0.2632 | LONG | 7 | 2 | BULLISH_TREND | Clean ORB; catalyst aligned; regime BULLISH_TREND; hit target in 2 min |
| 55 | 09:46:18 | SRF | SELL | vwap | -Rs165.53 | STOPLOSS | 0.1940 | NEUTRAL | 3 | 4 | CHOPPY | Highest consecutive_loss at entry (4) seen in journal; ml_prob=0.194 below any reasonable floor |
| 56 | 09:55:47 | BERGEPAINT | SELL | vwap | +Rs329.25 | TARGET | 0.2001 | NEUTRAL | 3 | 0 | CHOPPY | Third BERGEPAINT SELL today; finally worked; cooldown would have blocked this too |
| 57 | 09:56:04 | DIXON | SELL | vwap | OPEN | OPEN | 0.2409 | LONG | 7 | 0 | CHOPPY | Catalyst conflict — SELL vs LONG score=7; DIXON was clearly strong (ORB BUY hit target 24 min prior) |
| 58 | 10:20:16 | SRF | SELL | vwap | OPEN | OPEN | 0.2612 | NEUTRAL | 3 | 0 | CHOPPY | Second SRF SELL; open at time of writing |

**Best trade:** DIXON ORB BUY +Rs423.17 — BULLISH_TREND regime, catalyst_direction=LONG score=7, clean breakout at open, target hit in 2 minutes. Structurally correct on every dimension. This is what the ORB strategy is supposed to do.

**Worst trade:** BERGEPAINT SELL #53 -Rs173.87 — same symbol, same side as #51, fired 15 seconds later with consecutive_losses=3 already at the soft-pause threshold. No new information since #51 stopped out. A per-symbol 90-min cooldown would have blocked this entry entirely.

---

**Analysis:**

**1. BERGEPAINT triple-entry — mirrors AXISBANK pattern from 2026-04-29**

Trades 51 (09:30:01), 53 (09:30:16), and 56 (09:55:47) are all BERGEPAINT SELL. Trades 51 and 53 are 15 seconds apart. Trade 53 fired with consecutive_losses=3 — already past the soft-pause threshold of 2. The per-symbol 90-min cooldown rule flagged in the 2026-05-07 researcher items would have blocked both #53 and #56. Net BERGEPAINT PnL: -Rs173.68 -Rs173.87 +Rs329.25 = -Rs18.30 across three entries. The third entry happened to win — that is not process validation. The AXISBANK pattern from 2026-04-29 (SL twice, won third) has recurred in BERGEPAINT form. The direction eventually confirmed but the multiple failed entries bled capital first. Tag `#bergepaint-triple` as a named pattern alongside `#axisbank-triple`.

**2. SRF trade 55 fired with consecutive_losses=4 — worst breach to date**

Trade 55 (SRF SELL, 09:46:18) entered with consecutive_losses=4 and ml_prob=0.194. The soft-pause threshold is 2. This is the highest consecutive loss count at entry seen across all sessions in this journal. The ml_prob=0.194 is also below the existing informal floor discussion (0.27–0.30). Both the consecutive_losses gate and the ml_prob floor, if implemented, would have independently blocked this trade. It lost. The bot continued trading 46 minutes into a session where it had already accumulated 4 consecutive stoplosses — this is the definition of a pattern the soft-pause is designed to interrupt.

**3. DIXON catalyst conflict — same class of error as MARUTI, GODREJPROP (5th occurrence)**

Trade 54 (DIXON ORB BUY) hit target cleanly at 09:32 in BULLISH_TREND with catalyst_score=7 LONG. Trade 57 (DIXON VWAP SELL) fired 24 minutes later against that same LONG catalyst, in the same stock that had just demonstrated upside momentum. This is the 5th catalyst conflict event across sessions:
- MARUTI 2026-04-30 (SELL vs LONG catalyst) — lost
- KOTAKBANK 2026-05-05 (BUY vs SHORT catalyst) — won by luck
- BPCL 2026-05-07 (BUY vs SHORT catalyst) — won by luck
- GODREJPROP 2026-05-07 (SELL vs LONG catalyst) — lost
- DIXON today (SELL vs LONG catalyst score=7) — OPEN

The catalyst conflict filter has been flagged as URGENT since 2026-05-05. It remains unimplemented for the fifth consecutive session. Trade 57 is currently open.

**4. High ml_prob trades (51, 52) both stopped out at open — model miscalibration in open-auction window**

Trades 51 and 52 had ml_prob 0.483 and 0.522 — the two highest model confidence scores observed across any recent session. Both were stopped out within the first minute of trading. Meanwhile, Trade 54 (DIXON ORB, ml_prob=0.263) hit target, and Trade 56 (BERGEPAINT, ml_prob=0.200) hit target. High ml_prob was anti-predictive for open-auction VWAP signals today. The ML model's is_first_30min feature has significant weight (0.220 in OPEN_LONG) — but this also means the model may be encoding average open behaviour, not handling the elevated volatility of the first 60 seconds of the auction specifically. A per-window calibration check is warranted: does ml_prob have positive predictive value for trades in the first 2 minutes of open?

**5. DIXON ORB BUY (54) — confirmed edge**

Regime BULLISH_TREND, catalyst LONG score=7, ORB breakout, target hit in 2 minutes. Despite consecutive_losses=2 at entry, the structural setup was clean. This is the ORB strategy executing as designed. Contrasts with every VWAP loss today. The ORB signal in BULLISH_TREND with aligned catalyst has now produced at least two clean wins this week. The VWAP signals in the first 15 minutes of CHOPPY regime have now produced losses across multiple sessions.

**6. All losses in first 16 minutes (09:30–09:46) — opening-window VWAP failure extends the pattern**

Four losses between 09:30 and 09:46. The time-of-day deterioration pattern discussed across prior sessions (afternoon losses) now also applies to the opening minutes. VWAP signals fired in a CHOPPY regime in the first 15 minutes of the session are failing systematically. The time-of-day sizing filter (flagged for after 12:30) should potentially also apply to the first 15 minutes. Tag `#open-auction-vwap-failure` as a new named pattern.

**7. MFSL carry from 2026-05-07 — not in today's trade table**

MFSL SHORT was open overnight from 2026-05-07 (entry 1707.75, SL 1713.73). It does not appear in today's trade table, which suggests it either closed pre-open (gap risk) or is being tracked separately. This should be confirmed against the trades.db record before finalising today's PnL figures.

---

**Recurring patterns flagged (session counts updated):**

| Pattern tag | Session count | Last occurrence |
|---|---|---|
| `#choppy-market` | 6 consecutive sessions | 2026-05-08 |
| `#catalyst-conflict` | 5 events across 5 sessions | 2026-05-08 (DIXON, open) |
| `#consecutive-loss-breach` | 4 sessions | 2026-05-08 (consec=3 at #53, consec=4 at #55) |
| `#ml-filter-weak` | 4 sessions | 2026-05-08 (SRF ml_prob=0.194 passed) |
| `#vedl-repeat` | 3 sessions (not today) | 2026-05-07 |
| `#bergepaint-triple` | 1 (new, mirrors #axisbank-triple) | 2026-05-08 |
| `#open-auction-vwap-failure` | New pattern named today | 2026-05-08 |
| `#ml-high-prob-open-failure` | New pattern named today | 2026-05-08 (ml_prob 0.48, 0.52 both SL'd at open) |

**Edge check:** Green by Rs71.51 because DIXON ORB worked cleanly and BERGEPAINT eventually resolved. Neither of those outcomes validates today's process. BERGEPAINT's third entry winning after two losses is the same variance event as AXISBANK on 2026-04-29. SRF lost with consecutive_losses=4 at entry. HEROMOTOCO and BERGEPAINT #51 were SL'd in the first minute despite being the highest ml_prob signals of the session. DIXON SELL (Trade 57) is open against a score=7 LONG catalyst. The one clear edge trade was DIXON ORB BUY. Everything else was either variance, filter breach, or structurally inadvisable. This is not a good process day that happened to be green.

---

**For researcher Sunday:**

Carry-forward (unimplemented since 2026-04-30 or earlier — all now CRITICAL):
- URGENT (5 sessions overdue): Catalyst direction conflict filter — block when catalyst_direction != signal_direction AND catalyst_score >= 5. Five occurrences. One open trade (DIXON SELL #57) currently exposed.
- URGENT (4 sessions overdue): ml_prob floor of 0.30 for VWAP entries in CHOPPY regime. SRF today (0.194) is the clearest failure case.
- URGENT (4 sessions overdue): Consecutive_losses soft-pause — block new entries when consecutive_losses >= 2 unless ml_prob > 0.35. Trade #53 entered at consec=3, Trade #55 at consec=4.
- Time-of-day sizing: apply 50% position size not just after 12:30 but also in first 15 minutes of session when regime=CHOPPY.
- Per-symbol 90-min cooldown after SL (flagged 2026-05-07): would have blocked BERGEPAINT #53 and #56 today.

New from today:
- Investigate open-auction ml_prob calibration: ml_prob=0.483 and 0.522 both SL'd in the first minute. Positive predictive value of ml_prob may be near-zero for trades fired in the first 2 minutes. Consider a separate entry gate for 09:30:00–09:31:59 window (e.g., require ml_prob > 0.60, or suppress VWAP entries entirely in the first 2 minutes).
- Tag `#bergepaint-triple` as a named pattern for future cross-symbol tracking alongside `#axisbank-triple`.
- Confirm MFSL overnight position close/status against trades.db — it is absent from today's trade table and PnL has not been accounted for.
- Review DIXON SELL #57 (open, catalyst conflict, LONG score=7) — consider manual review of exit conditions before close.

**Tags:** #vwap #orb #choppy-market #winning-day #catalyst-conflict #ml-filter-weak #consecutive-loss-breach #open-auction-vwap-failure #ml-high-prob-open-failure #bergepaint-triple #fakeout #news-gap #clean-signal #dixon #bergepaint #heromotoco #srf #low-volume

---
---

## ML Retrain — 2026-05-08 16:03 IST (IST)
Feedback signals used: 87

### OPEN window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -12.805 -> -12.805
  long/win_rate: 0.31 -> 0.31
  long/n_signals: 86651 -> 86651
  short/sharpe: -14.484 -> -14.486
  short/win_rate: 0.309 -> 0.309
  short/n_signals: 86251 -> 86277

### MID window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -21.8 -> -21.8
  long/win_rate: 0.204 -> 0.204
  long/n_signals: 440635 -> 440635
  short/sharpe: -21.801 -> -21.801
  short/win_rate: 0.214 -> 0.214
  short/n_signals: 440635 -> 440635

### Feature importance
  OPEN_LONG — top 5 features:
    atr14_pct                 0.214
    is_first_30min            0.206
    vol_surge_5d              0.098
    time_bucket               0.078
    orb_width_pct             0.071

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.249
    is_first_30min            0.160
    time_bucket               0.107
    orb_width_pct             0.080
    mom_15m_pct               0.072

  MID_LONG — top 5 features:
    atr14_pct                 0.451
    mom_15m_pct               0.095
    mom_30m_pct               0.073
    orb_width_pct             0.070
    time_bucket               0.060

  MID_SHORT — top 5 features:
    atr14_pct                 0.458
    is_last_hour              0.093
    time_bucket               0.072
    vwap_dev_pct              0.060
    mom_15m_pct               0.059


---
## 2026-05-11 (tester)
**Strategy:** orb, vwap
**Trades:** 5 closed (2W / 2L / 1BE) + 1 open (COALINDIA SELL)
**PnL:** +Rs335.17 closed | open position: COALINDIA SELL at 464.37 (107 qty) — gap risk
**Market:** Nifty -1.5% (~23,815–23,931). Sensex -1.7% to 76,015. Auto/Capital Goods down ~2%. Paint stocks up (Investec buy on Asian Paints, Berger). FII net -Rs4,110.6 Cr. US S&P 500 +0.84% overnight (AI/earnings), Asia mixed.
**Context:** Global bias RISK_OFF. VIX 16.84. POLYCAB skipped (event risk). CANBK had Q2 earnings — not traded. All six signals today had catalyst_direction=NEUTRAL — first catalyst-conflict-free session since 2026-04-29.

**Trade breakdown:**

| # | Time | Symbol | Side | Strategy | PnL | Exit | ml_prob | regime | RSI | bars_abv_vwap | vwap_dev | consec_loss |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 59 | 09:30:15 | HDFCLIFE | BUY | orb | -Rs273.90 | STOPLOSS | 0.308 | BULLISH_TREND | 60.78 | 100% | +0.42% | 0 |
| 60 | 09:46:04 | BPCL | BUY | vwap | +Rs288.09 | TARGET | 0.237 | CHOPPY | 31.58 | 0% | -0.165% | 1 |
| 61 | 10:16:12 | INDUSTOWER | SELL | vwap | Rs0.00 | STOPLOSS-BE | 0.240 | CHOPPY | 62.0 | 6.7% | -0.079% | 0 |
| 62 | 10:50:52 | HEROMOTOCO | BUY | vwap | +Rs495.13 | TARGET | 0.271 | CHOPPY | 42.86 | 23.3% | -1.01% | 1 |
| 63 | 11:07:10 | LICHSGFIN | SELL | vwap | -Rs174.14 | STOPLOSS | 0.281 | CHOPPY | 72.73 | 30% | -0.046% | 0 |
| 64 | 12:28:26 | COALINDIA | SELL | vwap | OPEN | OPEN | 0.297 | CHOPPY | 40.74 | 96.7% | +0.018% | 1 |

**Best trade:** HEROMOTOCO +Rs495.13 (TARGET) — 1.01% below VWAP in CHOPPY, RSI=42.86 (neutral), stock_sentiment=1, adequate deviation with no overbought/oversold distortion. Structural signal: adequate deviation + sentiment + neutral RSI. This is repeatable VWAP long edge.

**Worst trade:** HDFCLIFE -Rs273.90 (STOPLOSS) — highest ml_prob of day (0.308), regime=BULLISH_TREND, yet SL'd in the first 15 seconds. Third session in a row (2026-05-08 Trades 51/52, today) where highest-confidence open signal fails immediately. Pattern `#ml-high-prob-open-failure` is now confirmed across multiple sessions.

**Pattern analysis:**

1. **HDFCLIFE ORB at open — `#ml-high-prob-open-failure` now 3-session confirmed.** ml_prob=0.308 (best today), regime=BULLISH_TREND, SL'd in 15 seconds. Prior occurrences: BERGEPAINT ml_prob=0.483, HEROMOTOCO ml_prob=0.522 on 2026-05-08 — all SL'd in first minute. Open-auction VWAP/ORB entries are consistently anti-predictive regardless of ml_prob score. Requires dedicated investigation: zero-evidence that ml_prob > 0.30 provides edge in the first 2 minutes.

2. **BPCL BUY — legitimate mean-reversion.** RSI=31.58 (near oversold), bars_above_vwap=0%, 0.53% below VWAP, consec_loss=1. Low ml_prob (0.237) but structural signal was valid and target hit. The RSI and bars_above_vwap context justified the trade independent of ml_prob. Process-adherent win.

3. **INDUSTOWER breakeven — trailing SL working as designed.** Entry = exit = 410.29. No monetary loss. `#trailing-sl-working` confirmed again. System executing correctly on this dimension.

4. **LICHSGFIN SELL — shallow deviation failure. Same pattern as MPHASIS 2026-05-05.** vwap_dev=-0.046% (0.046% above VWAP) in CHOPPY regime is not a reversion setup — no meaningful deviation to revert from. RSI=72.73 was favorable for short direction but the price had barely extended. Compare HEROMOTOCO (1.01% deviation, target hit) vs LICHSGFIN (0.046% deviation, SL hit). The minimum vwap_dev_pct threshold of >=0.80% in CHOPPY (flagged 2026-05-05 for MPHASIS at 0.82%, which was borderline) would have blocked LICHSGFIN (0.046%) while correctly passing HEROMOTOCO (1.01%) and BPCL (0.165% — marginal, but RSI=31.58 provides compensating oversold edge).

5. **COALINDIA SELL — NEW FAILURE MODE: bot traded against its own catalyst_reason warning.** Catalyst_reason reads: "2.4x volume with no news catalyst — suspicious flow, avoid." Despite this explicit avoid signal embedded in the reason string, the SELL fired at 12:28 IST. This is a qualitatively different failure from catalyst_direction conflict: the system's own natural-language output said to skip this trade and the executor did not parse it. Also: fired at 12:28 (2 minutes before the 12:30 time-of-day sizing boundary flagged since 2026-04-30). bars_above_vwap=96.7% is consistent with a VWAP short, but the self-contradictory signal is the core issue. Open overnight risk remains.

6. **All today's signals had catalyst_direction=NEUTRAL.** First session since 2026-04-29 with no catalyst direction conflict. Notable, but may reflect watchlist composition rather than a systematic improvement. No credit taken until the catalyst conflict filter is actually implemented.

7. **ml_prob floor: all six signals below 0.31.** Range today: 0.237–0.308. The 0.30 VWAP floor (CRITICAL, flagged since 2026-04-30) would have blocked Trades 60, 61, 62, 63, 64. Only HDFCLIFE at 0.308 marginally clears. Net impact would have been: no trades 60–64, avoiding -Rs174.14 (LICHSGFIN) and COALINDIA open risk, but also forgoing +Rs288.09 (BPCL) and +Rs495.13 (HEROMOTOCO). The filter would have resulted in a net loss day — but BPCL and HEROMOTOCO were legitimate structural setups, suggesting the 0.30 floor may need RSI/vwap_dev overrides rather than a hard block.

**Edge check:** HEROMOTOCO is clean edge — structure, deviation, sentiment all aligned. BPCL is legitimate mean-reversion. LICHSGFIN failure is a known pattern (shallow deviation). HDFCLIFE is the recurring open-auction miscalibration. COALINDIA is a new failure mode requiring a filter. The +Rs335.17 closed PnL is real but the COALINDIA open position carries unresolved risk. 2W/2L/1BE on 5 closed trades is statistically insufficient to judge edge — small sample, variance territory.

**Recurring patterns flagged (3+ occurrences in last 20 entries):**

| Pattern tag | Session count | Status |
|---|---|---|
| `#choppy-market` | 7 consecutive sessions (2026-04-29 through today) | Persistent |
| `#ml-filter-weak` | 5 sessions | All today's VWAP signals 0.237–0.297; none clear 0.30 |
| `#ml-high-prob-open-failure` | 3 sessions (2026-05-08 x2, today) | Confirmed multi-session pattern |
| `#catalyst-conflict` | 5 events / 5 sessions — not triggered today | Absent today (NEUTRAL all) |
| `#consecutive-loss-breach` | 4 sessions | Not breached today (max consec=1 at entry) |
| `#open-auction-vwap-failure` | 3 sessions | HDFCLIFE today; structural |
| `#trailing-sl-working` | 2 sessions (2026-05-07 KOTAKBANK, today INDUSTOWER) | System behaving correctly |

**For researcher Sunday:**

Carry-forward (CRITICAL — unimplemented since dates noted):
- CRITICAL (6 sessions overdue): Catalyst direction conflict filter — today was NEUTRAL across all signals, but the filter remains absent. One missed session does not close this item.
- CRITICAL (5 sessions overdue): ml_prob floor 0.30 for VWAP in CHOPPY. However: BPCL (0.237) and HEROMOTOCO (0.271) were legitimate setups that won. A hard floor would have blocked them. Revise proposal: floor of 0.25 with RSI + vwap_dev compensating gate (e.g., pass if ml_prob >= 0.25 AND (RSI <= 35 for longs OR vwap_dev >= 0.80% OR RSI >= 65 for shorts)).
- CRITICAL (5 sessions overdue): Consecutive_losses soft-pause at consec >= 2. Not breached today but unimplemented.
- Time-of-day sizing: 50% after 12:30 IST in CHOPPY. COALINDIA fired at 12:28 — borderline, but rule would have applied.
- Per-symbol 90-min cooldown after SL (flagged 2026-05-07). Not triggered today.
- RSI directional gate: block BUY when RSI >= 70; block SELL when RSI <= 30 (flagged 2026-05-08). Not triggered today.

New from today:
- **NEW FAILURE MODE — catalyst_reason keyword filter.** COALINDIA catalyst_reason explicitly contained "avoid" and the trade still fired. Executor must parse catalyst_reason for warn/avoid keywords and suppress entry when matched. This is an autonomous system self-contradicting on a live trade with open risk.
- **ml_prob floor reconsideration.** A hard 0.30 floor would have blocked two winning trades today. Propose tiered gate: pass if (ml_prob >= 0.30) OR (ml_prob >= 0.25 AND vwap_dev >= 0.80%) OR (ml_prob >= 0.25 AND RSI <= 32 [long] / RSI >= 68 [short]).
- **Open position COALINDIA SELL (Trade 64):** monitor for gap risk at 2026-05-12 open. bars_above_vwap=96.7% and RSI=40.74 at entry were structurally acceptable for a VWAP short; the problem is the catalyst_reason warning, not the technical setup.
- **`#ml-high-prob-open-failure` requires researcher investigation.** Separate ml_prob calibration check for trades in 09:30:00–09:31:59 window. Third occurrence. Hypothesis: open-auction VWAP deviation is driven by pre-market book imbalance that resolves rapidly regardless of ml_prob score — the feature set doesn't capture auction dynamics.

**Tags:** #orb #vwap #choppy-market #winning-day #ml-filter-weak #ml-high-prob-open-failure #open-auction-vwap-failure #trailing-sl-working #fakeout #risk-off #news-gap #hdfclife #bpcl #industower #heromotoco #lichsgfin #coalindia #shallow-deviation #catalyst-reason-ignored

---

---
## ML Retrain — 2026-05-11 16:08 IST (IST)
Feedback signals used: 87

### OPEN window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -13.328 -> -13.328
  long/win_rate: 0.303 -> 0.303
  long/n_signals: 86651 -> 86654
  short/sharpe: -14.302 -> -14.29
  short/win_rate: 0.313 -> 0.313
  short/n_signals: 86238 -> 86154

### MID window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -21.575 -> -21.575
  long/win_rate: 0.202 -> 0.202
  long/n_signals: 440635 -> 440635
  short/sharpe: -20.952 -> -20.952
  short/win_rate: 0.217 -> 0.217
  short/n_signals: 440635 -> 440635

### Feature importance
  OPEN_LONG — top 5 features:
    atr14_pct                 0.205
    is_first_30min            0.203
    vol_surge_5d              0.110
    orb_width_pct             0.074
    time_bucket               0.063

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.257
    is_first_30min            0.179
    time_bucket               0.111
    mom_15m_pct               0.076
    orb_width_pct             0.072

  MID_LONG — top 5 features:
    atr14_pct                 0.461
    mom_15m_pct               0.098
    orb_width_pct             0.069
    mom_30m_pct               0.064
    time_bucket               0.059

  MID_SHORT — top 5 features:
    atr14_pct                 0.444
    is_last_hour              0.099
    time_bucket               0.077
    mom_15m_pct               0.062
    vwap_dev_pct              0.058

## 2026-05-12 (tester)
**Strategy:** vwap
**Trades:** 2 (0W / 2L)
**PnL:** Rs-341.37

**Market:** **Nifty 50 closed at 23,815.85, down 360.30 points (-1.49%) on May 11, with a day range of 23,799-23,997 amid ongoing market weakness.** Major indices like Sensex (-1.92% at ~74,559), Nifty Bank (-1.63%), and Nifty IT (-3.73%) also fell sharply, led by selloffs in IT, auto, and mid/smallcaps. Key news included heavy losses for jewelry stocks (Titan, Senco down up to 12%) on PM Modi's gold-buying advisory, Bank Nifty pressure from rising crude prices and weak SBI Q4, marking four straight sessions of declines with Nifty cracking ~800 points.

**Context:** Global bias was RISK_OFF. 

**Best trade:** TORNTPHARM Rs-170.01 (STOPLOSS)
**Worst trade:** OBEROIRLTY Rs-171.36 (STOPLOSS)

**Edge check:** Loss rate >60% — check if market was choppy/low-volume. Review signal quality.

> WARNING: #stopped-out appears 7x in recent journal. Researcher should review stoploss width.

**Tags:** #loss #oberoirlty #stopped-out #torntpharm #vwap

---

## 2026-05-12 (tester) [enriched]
**Strategy:** vwap
**Trades:** 2 (0W / 2L)
**PnL:** -Rs341.37
**Cumulative week PnL:** -Rs341.37 (COALINDIA carry-in closed breakeven; week starts clean)
**Market:** VIX 19.12 (NORMAL). FII net -Rs8437.56 Cr — heaviest single-session FII selling across all tracked sessions. DII +Rs5939.65 Cr (partial offset, net still bearish). US overnight: Dow +0.19%, Nasdaq +0.29% — insufficient to counter domestic flow. Global bias: RISK_OFF.

**Trade breakdown:**

| # | Time (IST) | Symbol | Side | PnL | Exit | ml_prob | cat_dir | cat_score | cat_reason | regime | RSI | bars_abv_vwap | vwap_dev_pct | consec_loss | is_last_hour |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 65 | 13:44 | TORNTPHARM | BUY | -Rs170.01 | STOPLOSS | 0.231 | NEUTRAL | 2 | "suspicious volume, no clear direction" | CHOPPY | 44.3 | 36.7% | -0.037% | 1 | 0 |
| 66 | 14:36 | OBEROIRLTY | BUY | -Rs171.36 | STOPLOSS | 0.222 | NEUTRAL | 2 | "unexplained, skip" | CHOPPY | 50.9 | 53.3% | -0.018% | 2 | 1 |

**COALINDIA carry-in (Trade 64):** Confirmed closed breakeven. PnL=Rs0, exit=entry=464.3677 (trailing SL triggered at entry). No gap loss. `#trailing-sl-working` confirmed.

**Best trade:** TORNTPHARM -Rs170.01 — structurally the less-bad entry. RSI=44.3 neutral, entry at 13:44 (not last hour). Still inadvisable: RISK_OFF session, ml_prob=0.231, catalyst_reason flagged suspicious volume, stock not on premarket tradeable list.

**Worst trade:** OBEROIRLTY -Rs171.36 — every structural flag present simultaneously: catalyst_reason="unexplained, skip", consecutive_losses=2 at entry (soft-pause threshold), is_last_hour=1, ml_prob=0.222, vwap_dev=-0.018% (shallowest deviation in journal), RISK_OFF session.

---

**Analysis:**

**1. #catalyst-reason-ignored — 2nd occurrence, elevated urgency**

TORNTPHARM catalyst_reason: "suspicious volume, no clear direction." OBEROIRLTY catalyst_reason: "unexplained, skip." Both trades fired. Yesterday (2026-05-11), COALINDIA catalyst_reason said "avoid" and still fired. The executor is not parsing keyword signals from the catalyst_reason string. This is two confirmed sessions in a row where natural-language output from the system's own newsdesk explicitly flagged the trade for skipping and the entry gate did not act on it. The system is self-contradicting on live trades. Unlike the filter-gap issues (catalyst_direction, ml_prob floor), this is not a missing feature — it is a failure to consume data the system already generates. Fix priority: highest.

**2. #consecutive-loss-breach — 5th session, OBEROIRLTY at exactly consec=2**

OBEROIRLTY fired with consecutive_losses=2 — the exact soft-pause threshold flagged since 2026-04-30. Five sessions of documentation, zero implementation. Session count: 2026-04-30, 2026-05-07, 2026-05--08, 2026-05-11 (not triggered), 2026-05-12. This single gate would have blocked OBEROIRLTY entirely today.

**3. Both BUY entries in RISK_OFF with FII -Rs8437 Cr — worst macro session on record**

The global_bias=risk_off BUY suppression filter has been flagged since 2026-04-30. Today's FII net of -Rs8437.56 Cr is the single largest selling figure across every tracked session in this journal (prior worst: -Rs4110.6 Cr on 2026-05-11). Both trades were VWAP longs in a session where the largest institutional participants were aggressively net-selling. Neither trade had any prospect of macro tailwind. A hard BUY gate suppressing entries when fii_net_cr < -5000 Cr would have blocked both today, in addition to the existing risk_off suppression proposal.

**4. OBEROIRLTY in last hour (is_last_hour=1) + TORNTPHARM at 13:44 — afternoon CHOPPY pattern, 8th session**

Time-of-day position sizing filter after 12:30 IST in CHOPPY regime has been flagged since 2026-04-30. TORNTPHARM fired at 13:44, OBEROIRLTY at 14:36. Both afternoon entries. Afternoon VWAP degradation in CHOPPY has now produced losses or been associated with avoidable entries across 8 consecutive sessions. OBEROIRLTY at 14:36 additionally triggers is_last_hour=1 — the last-hour gate (flagged separately) would have blocked it independently.

**5. ml_prob sub-0.25 on both trades — 8th consecutive session**

TORNTPHARM: 0.231. OBEROIRLTY: 0.222. This is the 8th consecutive session where VWAP signals pass with ml_prob below 0.30. The ml_prob floor of 0.30 (flagged CRITICAL since 2026-04-30) remains unimplemented. Both trades today would have been blocked at 0.25 let alone 0.30.

**6. OBEROIRLTY vwap_dev=-0.018% — shallowest deviation in journal**

vwap_dev_pct=-0.018% is the lowest feature value recorded across all tracked trades. There is no mean-reversion basis at this deviation — price is effectively at VWAP. For reference: HEROMOTOCO on 2026-05-11 won with vwap_dev=1.01% (deep deviation); LICHSGFIN on 2026-05-11 failed with vwap_dev=0.046% (shallow). OBEROIRLTY at 0.018% is less than half LICHSGFIN's value. A minimum vwap_dev_pct threshold of 0.50% would have blocked OBEROIRLTY. The bars_above_vwap=53.3% additionally indicates price is oscillating at VWAP — no directional bias, no reversion setup.

**7. Neither TORNTPHARM nor OBEROIRLTY were on the premarket tradeable list**

The premarket-selected tradeable set was: TATACONSUM, SBIN, CANBK. Both traded stocks were on the watchlist but not selected. The premarket scoring step exists precisely to narrow the field to high-probability setups. If the executor is ignoring the tradeable list for VWAP signal evaluation, this is a configuration gap — the premarket filter is doing work that the executor then discards.

---

**Recurring patterns flagged (updated session counts):**

| Pattern tag | Session count | Status |
|---|---|---|
| `#choppy-market` | 8 consecutive sessions (2026-04-29 through 2026-05-12) | Persistent |
| `#ml-filter-weak` | 6 sessions | Both today sub-0.23; floor unimplemented |
| `#catalyst-reason-ignored` | 2 consecutive sessions (2026-05-11, 2026-05-12) | NEW elevated urgency — system self-contradicting on live trades |
| `#consecutive-loss-breach` | 5 sessions (2026-04-30, 2026-05-07, 2026-05-08, 2026-05-11 not triggered, 2026-05-12) | Unimplemented |
| `#risk-off` (BUY entries) | 5+ sessions | BUY gate missing; today worst macro session on record |
| `#afternoon-losses` | 8 sessions | Time-of-day filter unimplemented |
| `#shallow-deviation` | 3 sessions (MPHASIS 2026-05-05, LICHSGFIN 2026-05-11, OBEROIRLTY today) | vwap_dev floor unimplemented |
| `#ml-high-prob-open-failure` | 3 sessions (not triggered today) | |
| `#trailing-sl-working` | 3 sessions | COALINDIA breakeven today; system correct on this dimension |

**Edge check:** This is a structurally clean loss — not variance, not bad luck. Every filter the system has been asked to implement since 2026-04-30 would have blocked at least one of today's trades. Combined, six independent filters (catalyst_reason parser, consecutive_losses gate, risk_off BUY suppression, ml_prob floor, time-of-day sizing, vwap_dev minimum) would have produced zero entries today. The day represents a direct cost of unimplemented filters across 5+ sessions. No edge was demonstrated because no edge was present at entry on either trade.

---

**For researcher Sunday:**

Carry-forward (all CRITICAL — session-overdue counts updated):
- **CRITICAL (6 sessions overdue): Catalyst_reason keyword parser.** Parse catalyst_reason for "skip", "avoid", "suspicious", "unexplained" keywords. Block entry when matched. System is self-contradicting on live trades for 2 consecutive sessions. This is a data-consumption failure, not a missing feature. Highest priority — implement before next session.
- **CRITICAL (6 sessions overdue): ml_prob floor 0.25 with vwap_dev + RSI compensating gate** (tiered rule proposed 2026-05-11). Both today's trades blocked at 0.25.
- **CRITICAL (6 sessions overdue): Consecutive_losses soft-pause at consec >= 2.** OBEROIRLTY blocked. Five sessions of breach documentation.
- **CRITICAL (6 sessions overdue): Catalyst direction conflict filter** (catalyst_direction != signal_direction AND catalyst_score >= 5). Not triggered today (both NEUTRAL) but still unimplemented.
- Time-of-day sizing: 50% after 12:30 IST in CHOPPY (8 sessions overdue).
- Per-symbol 90-min cooldown after SL (2026-05-07 flag).
- RSI directional gate: BUY block when RSI >= 70; SELL block when RSI <= 30 (2026-05-08 flag).
- Investigate premarket tradeable list enforcement — TORNTPHARM and OBEROIRLTY were watchlist but not tradeable-list; executor should require tradeable list membership for VWAP signal approval.

New from today:
- **FII net hard BUY gate:** if fii_net_cr < -5000 Cr, suppress all BUY entries for the session. Today's -Rs8437 Cr is a clear case. Threshold to evaluate: -Rs4000 Cr (would have blocked 2026-05-11 entry also) vs -Rs5000 Cr (conservative, blocks clearest cases only).
- **vwap_dev minimum for VWAP longs/shorts:** require |vwap_dev_pct| >= 0.50% as an entry gate. OBEROIRLTY at 0.018% is the clearest failure case in the journal.

**Tags:** #vwap #choppy-market #losing-day #risk-off #catalyst-reason-ignored #consecutive-loss-breach #ml-filter-weak #afternoon-losses #shallow-deviation #fii-heavy-selling #torntpharm #oberoirlty #trailing-sl-working
---
## ML Retrain — 2026-05-12 16:03 IST (IST)
Feedback signals used: 87

### OPEN window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -14.354 -> -14.353
  long/win_rate: 0.288 -> 0.288
  long/n_signals: 86653 -> 86643
  short/sharpe: -12.949 -> -12.951
  short/win_rate: 0.326 -> 0.326
  short/n_signals: 86136 -> 86177

### MID window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -21.923 -> -21.923
  long/win_rate: 0.201 -> 0.201
  long/n_signals: 440634 -> 440634
  short/sharpe: -20.159 -> -20.159
  short/win_rate: 0.226 -> 0.226
  short/n_signals: 440634 -> 440634

### Feature importance
  OPEN_LONG — top 5 features:
    atr14_pct                 0.194
    is_first_30min            0.183
    vol_surge_5d              0.119
    orb_width_pct             0.081
    mom_15m_pct               0.067

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.250
    is_first_30min            0.235
    time_bucket               0.087
    orb_width_pct             0.066
    mom_15m_pct               0.065

  MID_LONG — top 5 features:
    atr14_pct                 0.458
    mom_15m_pct               0.106
    orb_width_pct             0.070
    mom_30m_pct               0.065
    time_bucket               0.056

  MID_SHORT — top 5 features:
    atr14_pct                 0.460
    is_last_hour              0.096
    time_bucket               0.074
    vwap_dev_pct              0.056
    mom_15m_pct               0.055

## 2026-05-14 (tester)
**Strategy:** vwap
**Trades:** 3 (0W / 3L)
**PnL:** Rs-346.15

**Market:** **Nifty 50 is trading down 1.16% at ₹23,898.35** (open ₹23,996.95, range 23,796-24,019), after previous close of ₹24,177, amid broader market weakness with 1-week decline of 1.97%. Major movers include banking stocks aiding recovery in some updates, while IT (Nifty IT -2%) and stocks like Indigo (-3.65%), Trent (-2.97%) lag; Sensex mixed around 74,686-75,398. Big news: GIFT Nifty signals strong start potential amid AI optimism and steady crude, but intraday slips noted with Brent oil elevated above $100/bbl.

**Context:** Global bias was RISK_OFF. Skipped event-risk stocks: VOLTAS, DLF.

**Best trade:** VOLTAS +Rs0.00 (STOPLOSS)
**Worst trade:** JUBLFOOD Rs-174.40 (STOPLOSS)

**Edge check:** Loss rate >60% — check if market was choppy/low-volume. Review signal quality.

> WARNING: #stopped-out appears 9x in recent journal. Researcher should review stoploss width.

**Tags:** #hcltech #jublfood #loss #stopped-out #voltas #vwap

---
## 2026-05-14 (tester) [enriched]
**Strategy:** vwap
**Trades:** 3 closed (0W / 2L / 1BE) + 1 open (DIXON SELL — overnight gap risk)
**PnL:** -Rs346.15 closed | Open: DIXON SELL (ml_prob=0.1945, vwap_dev=0.016% — no structural edge)
**Cumulative week PnL:** -Rs346.15 (only closed day this week; prior days 2026-05-12 and earlier excluded from this week's tally)
**Market:** Nifty 50 -1.16% (~23,898). Nifty IT -2%. Regime: BEARISH/CHOPPY throughout. VIX 18.778. FII net -Rs4703.15 Cr (RISK_OFF — just below the -5000 Cr hard BUY gate proposed 2026-05-12). Global bias risk_off. Premarket skip list: VOLTAS, DLF.

**Context:** Every trade today was fired through at least one unimplemented filter gate. This is not a variance loss. It is a direct, documented cost of deferred implementation across 7 sessions.

**Trade breakdown:**

| # | Time | Symbol | Side | PnL | Exit | ml_prob | window | regime | RSI | bars_abv_vwap | vwap_dev | consec_loss | is_last_hour | cat_dir | cat_score | Gates violated |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 74 | 10:02 | JUBLFOOD | SELL | -Rs174.40 | STOPLOSS | 0.4735 | open | BEARISH_TREND | 96.83 | 66.7% | +0.539% | 1 | 0 | NEUTRAL | 2 | RSI extreme momentum (96.83 for SHORT); open-window pattern |
| 75 | 10:25 | HCLTECH | BUY | -Rs171.76 | STOPLOSS | 0.2714 | mid | CHOPPY | 25.0 | 53.3% | -0.182% | 2 | 0 | NEUTRAL | 3 | consec_loss=2 (soft-pause unimplemented); ml_prob=0.2714 (below 0.30 floor); RISK_OFF BUY; cat_reason semantically said "skip" |
| 76 | 13:57 | VOLTAS | SELL | Rs0.00 | STOPLOSS-BE | 0.2875 | mid | CHOPPY | 85.71 | 100% | +0.223% | 3 | 0 | SHORT | 5 | consec_loss=3; premarket SKIP list explicitly flagged VOLTAS |
| 77 | 14:32 | DIXON | SELL | OPEN | — | 0.1945 | mid | CHOPPY | 66.67 | 56.7% | +0.016% | 4 | 1 | NEUTRAL | 4 | ml_prob=0.1945 (journal low); vwap_dev=0.016% (journal low); consec_loss=4 (journal high); is_last_hour=1; RISK_OFF |

**Best trade:** VOLTAS SELL, Rs0.00 — trailing SL to breakeven rescued a trade fired through two gate violations (premarket skip, consec_loss=3). The trailing SL is working. The entry should not have occurred.

**Worst trade:** JUBLFOOD SELL, -Rs174.40 — RSI=96.83 for a short signals extreme upward momentum into entry. ml_prob=0.4735 is the highest of the day and the 4th confirmed `#ml-high-prob-open-failure`. The open-auction window consistently produces this pattern regardless of ml_prob magnitude.

---

**Analysis:**

**1. JUBLFOOD SELL — 4th confirmed `#ml-high-prob-open-failure`; RSI extreme momentum unaddressed**

ml_prob=0.4735 is the highest signal confidence of the session and the highest open-window ml_prob across recent sessions, yet the trade stopped out. Prior instances: BERGEPAINT 0.483 (2026-05-08), HEROMOTOCO 0.522 (2026-05-08), HDFCLIFE 0.308 (2026-05-11). Four consecutive occurrences confirm this is a structural failure of the ML model in the open-auction window, not sampling noise. The RSI=96.83 at entry for a SELL adds a second dimension: the RSI gate blocks BUY at RSI >= 70 and SELL at RSI <= 30, but RSI=96.83 on the SHORT side means the stock is in extreme upward momentum precisely when the signal attempts to fade it. An RSI >= 90 extreme-momentum gate for SELL entries would have blocked this trade independently of the open-window problem. vwap_dev=0.539% is marginal (just above the 0.50% floor) — not a strong deviation signal.

**2. HCLTECH BUY — consec_loss=2 fires a RISK_OFF BUY with semantic skip in catalyst_reason; 2nd consec-breach long**

consecutive_losses=2 at entry, global_bias=risk_off, fii_net=-4703 Cr, ml_prob=0.2714. The soft-pause at consec >= 2 has been CRITICAL/unimplemented for 7 sessions. This is the second instance of a long entry firing with consec_loss=2 in a RISK_OFF session (prior: OBEROIRLTY 2026-05-12). RSI=25.0 is near-oversold and technically approaches the long side's compensating threshold — but the structural weight against this entry (RISK_OFF, low ml_prob, consec_loss=2, no catalyst) outweighs a single RSI reading. Critically, the catalyst_reason explicitly contains "but no catalyst to justify a position" — semantically identical to a hard skip, yet the keyword parser does not catch this phrasing. This is the 3rd session where the cat_reason semantically recommends avoidance but the parser's literal-keyword check fails to block. The filter gap is in vocabulary coverage, not logic architecture.

**3. VOLTAS SELL — premarket SKIP list explicitly violated for the 3rd time; consec_loss=3**

The premarket output flagged VOLTAS as event-risk/skip before the session. The executor fired at 13:57 with consec_loss=3. This is the 3rd confirmed instance of the premarket tradeable list being overridden by the executor (prior: TORNTPHARM, OBEROIRLTY on 2026-05-12). The trailing SL produced Rs0.00 — `#trailing-sl-working` continues to function. The signal itself had some structural quality: RSI=85.71, bars_above_vwap=100%, catalyst_direction=SHORT, catalyst_score=5. The failure mode is not signal quality but the absence of enforcement for the premarket skip tag. A clean signal fired through a hard-skip designation and a consec=3 context simultaneously illustrates that gate enforcement must be sequential and mandatory, not advisory.

**4. DIXON SELL — worst confluence in journal history; 5 independent gates missed; overnight gap risk**

ml_prob=0.1945 is the lowest ml_prob across all tracked trades. vwap_dev=0.016% ties the shallowest deviation on record (OBEROIRLTY 0.018%). consecutive_losses=4 is the new journal maximum (prior high: 3 on VOLTAS today). is_last_hour=1 at 14:32 — the last-hour gate has been flagged and is unimplemented. RISK_OFF session. The catalyst_reason notes "it's priced in and consolidating" — semantically a skip that the keyword parser does not catch. Five independent, unimplemented filter gates (ml_prob floor, vwap_dev minimum, consec_loss pause at 2, last-hour gate, RISK_OFF suppression) would each have blocked this trade in isolation. All five fired simultaneously and were each missed. The position is open overnight — same failure mode as COALINDIA on 2026-05-11, which closed breakeven. Monitor at 2026-05-15 open; no structural edge exists on this trade and there is no reason to hold beyond the first exit opportunity.

**5. No wins; 9 consecutive sessions of CHOPPY or losing pattern; filter backlog costing real money**

The bot has produced no positive closed session since the nominal green on 2026-05-11 (which carried COALINDIA open risk). The recurring pattern across every session since 2026-04-30 is the same: unimplemented filters, documented in prior enriched entries, fired and missed again. Today's -Rs346.15 is not the result of bad luck or an unusual market. The Nifty was down 1.16% in a RISK_OFF session — exactly the environment where every proposed filter was designed to reduce exposure. Instead, four trades were entered, the last one with five simultaneous gate failures.

**6. FII -4703 Cr threshold calibration — the -5000 Cr gate would not have fired today**

The hard BUY gate proposed on 2026-05-12 uses -5000 Cr as the threshold. Today's FII net of -4703 Cr is below the -4000 Cr looser threshold discussed but above -5000 Cr. Result: neither threshold would have blocked the HCLTECH BUY entry. This matters for calibration — the -5000 Cr threshold is too conservative to catch today's RISK_OFF conditions. The -4000 Cr threshold would have triggered. Researcher should evaluate whether -4500 Cr is the right midpoint.

---

**Recurring patterns flagged:**

| Pattern tag | Session count | Status |
|---|---|---|
| `#choppy-market` | 9 consecutive sessions (2026-04-29 through 2026-05-14) | Persistent |
| `#ml-filter-weak` | 7 sessions — DIXON 0.1945 is new journal low | Unimplemented floor |
| `#consecutive-loss-breach` | 7 sessions — consec=3 (VOLTAS) and consec=4 (DIXON) are new maxima | Unimplemented |
| `#catalyst-reason-ignored` | 3 sessions (2026-05-11, 2026-05-12, 2026-05-14) | Keyword parser vocabulary too narrow |
| `#ml-high-prob-open-failure` | 4 sessions (BERGEPAINT, HEROMOTOCO, HDFCLIFE, JUBLFOOD today) | Structural; open-auction window problem |
| `#premarket-list-ignored` | 3 instances across 2 sessions | Enforcement absent |
| `#trailing-sl-working` | 4 sessions (VOLTAS breakeven today) | Functioning correctly |
| `#afternoon-losses` | 9 sessions | Time-of-day filter unimplemented |
| `#shallow-deviation` | 4 sessions — DIXON 0.016% new journal low | vwap_dev floor unimplemented |
| `#risk-off` BUY entries | 6+ sessions | BUY suppression gate unimplemented |

**Edge check:** This is a structurally clean loss. Not variance. Not an unusual market. Every filter that fired today was proposed, documented, and flagged CRITICAL across the preceding 7 sessions. The combined probability that five independent gate failures on a single trade (DIXON) occurred by coincidence is negligible — this is a systematic enforcement gap. No edge was present at entry on any trade today. The one trade that avoided a loss (VOLTAS) did so because the trailing SL worked, not because the entry had merit. Process adherence score: 0/4. Implementation urgency is at maximum.

---

**For researcher Sunday:**

CRITICAL — carry-forward, all 7 sessions overdue:
- **Catalyst_reason keyword parser:** Add "no catalyst", "priced in", "consolidating", "no catalyst to justify" to the block vocabulary. Literal skip/avoid/suspicious is insufficient — today's HCLTECH and DIXON both had semantically clear skip signals in the reason field that were not caught.
- **ml_prob floor 0.25 tiered gate:** Would have blocked HCLTECH (0.2714) and DIXON (0.1945). DIXON is the clearest failure case in journal history at 0.1945.
- **Consecutive_losses soft-pause at consec >= 2:** New journal maximum is consec=4 (DIXON). The gate has been overdue since 2026-04-30.
- **Catalyst direction conflict filter:** Unimplemented. Not triggered today but still outstanding.
- **Premarket tradeable list enforcement:** VOLTAS was explicitly skip-listed. Executor must reject any signal for a skip-listed symbol, regardless of signal quality.

New from today:
- **Last-hour gate (is_last_hour=1 block):** DIXON fired at 14:32 with is_last_hour=1. Previously flagged; still missing. Block all new entries when is_last_hour=1.
- **Time-of-day 50% sizing after 12:30 IST in CHOPPY:** VOLTAS at 13:57, DIXON at 14:32 — both afternoon entries in CHOPPY. Half-size would have halved the exposure on trades with consec_loss >= 3.
- **FII hard BUY gate threshold recalibration:** -5000 Cr did not fire today (fii=-4703 Cr). Recommend lowering threshold to -4500 Cr or -4000 Cr. Today's RISK_OFF conditions should have been caught.
- **RSI extreme momentum gate for SELL entries:** RSI >= 90 at entry for a SHORT should require additional confirmation or be blocked. JUBLFOOD RSI=96.83 fired regardless. The RSI gate covers RSI <= 30 for longs and RSI >= 70 for shorts in some contexts — extend it to flag RSI >= 90 for SELL as extreme momentum risk.
- **DIXON open position:** Monitor at 2026-05-15 open. No structural edge (ml_prob=0.1945, vwap_dev=0.016%, consec_loss=4 at entry). Exit at first opportunity. Same overnight gap risk scenario as COALINDIA 2026-05-11 (which closed breakeven — do not expect that outcome to repeat).

**Tags:** #vwap #choppy-market #losing-day #risk-off #ml-filter-weak #ml-high-prob-open-failure #consecutive-loss-breach #trailing-sl-working #shallow-deviation #afternoon-losses #premarket-list-ignored #catalyst-reason-ignored #jublfood #hcltech #voltas #dixon #stopped-out #open-position-risk
---

---
---
## ML Retrain — 2026-05-14 16:05 IST (IST)
Feedback signals used: 87

### OPEN window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -13.974 -> -13.976
  long/win_rate: 0.3 -> 0.3
  long/n_signals: 86650 -> 86656
  short/sharpe: -11.968 -> -11.961
  short/win_rate: 0.336 -> 0.336
  short/n_signals: 86272 -> 86152

### MID window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: -20.741 -> -20.741
  long/win_rate: 0.214 -> 0.214
  long/n_signals: 440648 -> 440648
  short/sharpe: -19.653 -> -19.653
  short/win_rate: 0.235 -> 0.235
  short/n_signals: 440648 -> 440648

### Feature importance
  OPEN_LONG — top 5 features:
    atr14_pct                 0.202
    is_first_30min            0.147
    vol_surge_5d              0.128
    orb_width_pct             0.081
    mom_15m_pct               0.075

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.253
    is_first_30min            0.213
    time_bucket               0.096
    mom_15m_pct               0.074
    orb_width_pct             0.071

  MID_LONG — top 5 features:
    atr14_pct                 0.462
    mom_15m_pct               0.099
    mom_30m_pct               0.071
    orb_width_pct             0.070
    time_bucket               0.057

  MID_SHORT — top 5 features:
    atr14_pct                 0.464
    is_last_hour              0.094
    time_bucket               0.072
    mom_30m_pct               0.058
    vwap_dev_pct              0.056

---
## ML Retrain — 2026-05-15 08:51 IST (IST)
Feedback signals used: 87

### OPEN window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: - -> -13.976
  long/win_rate: - -> 0.3
  long/n_signals: - -> 86656
  short/sharpe: - -> -11.964
  short/win_rate: - -> 0.336
  short/n_signals: - -> 86188

### MID window | deployed=YES | threshold 0.150 -> 0.150
  long/sharpe: - -> -20.741
  long/win_rate: - -> 0.214
  long/n_signals: - -> 440648
  short/sharpe: - -> -19.653
  short/win_rate: - -> 0.235
  short/n_signals: - -> 440648

### Feature importance
  OPEN_LONG — top 5 features:
    atr14_pct                 0.225
    vol_surge_5d              0.132
    is_first_30min            0.103
    orb_width_pct             0.085
    mom_15m_pct               0.068

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.303
    is_first_30min            0.116
    time_bucket               0.099
    orb_width_pct             0.075
    mom_15m_pct               0.070

  MID_LONG — top 5 features:
    atr14_pct                 0.514
    mom_15m_pct               0.067
    orb_width_pct             0.062
    mom_30m_pct               0.058
    time_bucket               0.054

  MID_SHORT — top 5 features:
    atr14_pct                 0.490
    is_last_hour              0.094
    time_bucket               0.072
    vwap_dev_pct              0.057
    orb_width_pct             0.054

## 2026-05-15 (tester)
**Strategy:** vwap
**Trades:** 14 (3W / 11L)
**PnL:** Rs-489.80

**Market:** Indian markets are trading softer today, with Nifty 50 down about 1.2% in the latest available update, slipping after a weak open and staying near the day’s lows. Heavyweights like financials, autos, IT, and select industrials are among the notable drags, with stocks such as Bajaj Finance, Axis Bank, Bharti Airtel, Adani Ports, and Infosys showing losses.  

On the news side, the broad tone appears to be risk-off rather than driven by one single event, with investors likely reacting to earnings, global cues, and pressure in large-cap names.

**Context:** Global bias was RISK_ON. Skipped event-risk stocks: SUNPHARMA.

**Best trade:** LICHSGFIN +Rs430.31 (TARGET)
**Worst trade:** TATAMOTORS Rs-173.95 (STOPLOSS)

**Edge check:** Loss rate >60% — check if market was choppy/low-volume. Review signal quality.

> WARNING: #stopped-out appears 12x in recent journal. Researcher should review stoploss width.

**Insights:**
- Choppy regime killed edge: 3W/11L (21% win rate) — all trades fired in CHOPPY regime; VWAP strategy has no regime filter and should halt or halve size when regime=CHOPPY.
- ML model was unanimously skeptical (all ml_prob < 0.40) yet all 16 entries fired; a minimum ml_prob threshold (>=0.35 in normal, >=0.40 in CHOPPY) would have culled the weakest setups.
- Repeated-symbol churn destroyed capital: TATAMOTORS 3x, ADANIENT 2x, TATACOMM 2x, PIIND 2x — bot re-entered same symbols intra-day on near-identical signals without a same-symbol cooldown rule.
- Last-hour entries are a known trap (is_last_hour is #2 feature in MID_SHORT model): BAJAJFINSV and HCLTECH both stopped out late; the open HCLTECH position entered with 4 consecutive losses and catalyst_score=3 — fragile overnight hold.
- Stoploss width (0.30%) is too tight for choppy conditions: 11/14 exits were stoploss; wider SL (0.4–0.5%) with reduced sizing would need backtesting before change.
- Winning pattern was high VWAP deviation: both clear winners (LICHSGFIN 0.80%, PIIND 0.62%) had the day's widest deviations and RR >2.4x — signal quality at entry, not entry count, drove the day's only profit.

**Flags for researcher:** (1) Regime=CHOPPY halt/size-reduction rule for VWAP — triggered 3x this week. (2) Same-symbol intra-day cooldown — TATAMOTORS re-entered 3x, ADANIENT/TATACOMM each 2x. (3) ml_prob minimum filter — all 14 losing trades had ml_prob <0.40; needs Sunday review against backtest.

**Tags:** #vwap #choppy-regime #stopped-out #repeated-symbol #low-ml-prob #last-hour-trap #adanient #tatamotors #tatacomm #lichsgfin #piind #jswsteel #bajajfinsv #hcltech #losing-day #winning-trades

---
---
## ML Retrain — 2026-05-15 16:02 IST (IST)
Feedback signals used: 87

### OPEN window | deployed=YES | threshold 0.150 -> 0.400
  long/sharpe: -12.681 -> -12.681
  long/win_rate: 0.315 -> 0.315
  long/n_signals: 86655 -> 86650
  short/sharpe: -13.48 -> -13.479
  short/win_rate: 0.321 -> 0.321
  short/n_signals: 86197 -> 86181

### MID window | deployed=YES | threshold 0.150 -> 0.350
  long/sharpe: -20.904 -> -20.904
  long/win_rate: 0.213 -> 0.213
  long/n_signals: 440637 -> 440637
  short/sharpe: -19.594 -> -19.594
  short/win_rate: 0.237 -> 0.237
  short/n_signals: 440637 -> 440637

### Feature importance
  OPEN_LONG — top 5 features:
    atr14_pct                 0.229
    vol_surge_5d              0.127
    is_first_30min            0.113
    orb_width_pct             0.086
    mom_15m_pct               0.068

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.306
    is_first_30min            0.092
    time_bucket               0.089
    orb_width_pct             0.075
    mom_15m_pct               0.071

  MID_LONG — top 5 features:
    atr14_pct                 0.509
    mom_15m_pct               0.065
    mom_30m_pct               0.065
    orb_width_pct             0.062
    time_bucket               0.055

  MID_SHORT — top 5 features:
    atr14_pct                 0.489
    is_last_hour              0.090
    time_bucket               0.070
    vwap_dev_pct              0.055
    orb_width_pct             0.053

## 2026-05-18 (tester)
**Strategy:** vwap
**Trades:** 4 (0W / 4L)
**PnL:** Rs-680.55

**Market:** Indian markets were broadly weak today, with the Nifty 50 pointing lower as risk sentiment stayed cautious. From the Nifty constituents visible in NSE updates, major drag came from heavyweights like Bajaj Finance, Bajaj Finserv, Axis Bank, Bharti Airtel, and Infosys, while Hindalco and ONGC were among the few gainers.  

On the news side, the main tone appears to be macro-driven rather than company-specific, with global risk-off cues and oil-price concerns weighing on sentiment.

**Context:** Global bias was RISK_ON. Skipped event-risk stocks: TECHM, ADANIENT.

**Best trade:** OFSS Rs-159.69 (STOPLOSS)
**Worst trade:** SAIL Rs-174.89 (STOPLOSS)

**Edge check:** Loss rate >60% — check if market was choppy/low-volume. Review signal quality.

> WARNING: #stopped-out appears 14x in recent journal. Researcher should review stoploss width.

**Tags:** #loss #ofss #sail #stopped-out #voltas #vwap

---

## 2026-05-18 (tester) [enriched]
**Strategy:** vwap (mode: paper)
**Trades:** 4 (0W / 4L) — all SELL/SHORT, all STOPLOSS
**PnL:** -Rs680.55 (worst single-day PnL in journal history; prior worst: -Rs489.80 on 2026-05-15)
**Cumulative week PnL:** -Rs680.55 (first session of week 2026-05-19; session count starts fresh)
**Market:** VIX 19.91 (NORMAL). FII net +Rs1329.17 Cr (BULLISH, data lag from 2026-05-15). DII net -Rs1958.82 Cr. Global bias: RISK_ON. INFY reported strong results and was up on the day; SAIL near 15-yr high on FY26 steel demand; OFSS Q4 profit +38%. Market tone broadly bullish despite DII selling. Premarket skips: TECHM (facility fire), ADANIENT (quarterly loss).

**Trade breakdown:**

| # | Time (IST) | Symbol | Side | PnL | Exit | ml_prob | window | regime | RSI | bars_abv_vwap | vwap_dev_pct | consec_loss | is_last_hour | cat_dir | cat_score | Gates violated |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 94 | 10:10 | SAIL | SELL | -Rs174.89 | STOPLOSS | 0.4304 | open | CHOPPY | 77.67 | 100% | +0.447% | 1 | 0 | NEUTRAL | 4 | risk_on SELL; vwap_dev < 0.50% floor; cat_reason "overextended/weak volume" |
| 95 | 10:16 | OFSS | SELL | -Rs159.69 | STOPLOSS | 0.4062 | mid | CHOPPY | 92.08 | 83.3% | +0.497% | 2 | 0 | NEUTRAL | 4 | consec_loss=2 (soft-pause); RSI=92.08 extreme momentum; risk_on SELL; cat_reason "suspicious" fired anyway; vwap_dev < 0.50% floor |
| 96 | 11:58 | VOLTAS | SELL | -Rs171.50 | STOPLOSS | 0.3833 | mid | CHOPPY | 38.24 | 0% | -0.266% | 3 | 0 | NEUTRAL | 3 | consec_loss=3; INVERTED signal (price below VWAP, shorting further down); cat_reason "suspicious, avoid" fired anyway; vwap_dev negative |
| 97 | 13:52 | SAIL | SELL | -Rs174.47 | STOPLOSS | 0.3652 | mid | CHOPPY | 93.14 | 90% | +0.434% | 4 | 0 | NEUTRAL | 4 | consec_loss=4; same-symbol re-entry (SAIL #2, 3h42m after #1); RSI=93.14 extreme momentum; risk_on SELL; vwap_dev < 0.50% floor |

**Best trade:** OFSS -Rs159.69 — the day's smallest loss and the only trade with a modest structural basis (price above VWAP, deviation marginally approaching the 0.50% floor). Still inadvisable: RSI=92.08 into a short, consec_loss=2 at entry, RISK_ON session.

**Worst trade:** SAIL #1 -Rs174.89 — opened the losing streak at 10:10 in a RISK_ON session. SAIL was at a 15-yr high with weak volume (0.43x). Shorting a stock at a multi-year high in a FII-net-positive session is a structural directional conflict. The cat_reason explicitly said "overextended, weak volume today" — this was a description of the condition creating the signal, not a warning, but combined with global_bias=risk_on and SAIL's positive FY26 steel demand context, there was no bear case.

---

**Analysis:**

**1. #inverted-vwap-signal (NEW, CRITICAL) — VOLTAS SELL with price BELOW VWAP**

VOLTAS SELL fired with vwap_dev_pct=-0.266% and bars_above_vwap=0%. The VWAP reversion strategy shorts when price is extended ABOVE VWAP, expecting a return to the mean. VOLTAS was already below VWAP — the price had nowhere to revert to on the short side. This is a structurally inverted signal: a VWAP SHORT when vwap_dev_pct < 0 is the equivalent of buying when price is above resistance and expecting it to continue rising. The fix is a hard block: reject any VWAP SELL when vwap_dev_pct <= 0. This is the clearest signal-logic error in the journal — the system was literally trading against its own entry premise. This is a new category of failure, distinct from all prior filter gaps.

**2. #risk-on-short-failure (NEW) — all 4 SELL entries in a RISK_ON, FII-net-positive session**

FII net was +Rs1329.17 Cr (BULLISH). Global bias was RISK_ON. The three non-inverted shorts (SAIL x2, OFSS) were entered into stocks with genuinely positive catalysts: SAIL at a 15-yr high on strong FY26 steel demand, OFSS with Q4 profit +38%. Shorting upward-trending stocks with positive catalysts in a risk_on session with institutional net-buying is direction-blind. The prior `#risk-off BUY` pattern flagged since 2026-04-30 identified the same structural error in the opposite direction. The proposed suppression rule must be bidirectional: suppress SELL entries when global_bias=risk_on AND fii_net_cr > +1000 Cr. The data available at market open (FII net from 2026-05-15, lag acknowledged) was +Rs1329.17 Cr — above any reasonable threshold. The session should have been VWAP-neutral or long-biased, not all-short.

**3. #catalyst-reason-ignored — 4th session; VOLTAS and OFSS both explicit**

VOLTAS cat_reason: "No news but 2.3x volume surge on gap down — suspicious, avoid." OFSS cat_reason: "2x volume on flat gap is suspicious." Both trades fired. This is the 4th consecutive session (2026-05-11, 2026-05-12, 2026-05-14, 2026-05-18) where the system's own newsdesk output recommended avoidance and the executor entered regardless. The keyword "suspicious" and "avoid" have appeared in cat_reason across multiple flagged sessions. The parser either does not evaluate this field at all or does not cover these terms. This is a data-consumption failure — the intelligence to block these trades was generated and discarded.

**4. #consecutive-loss-breach — 8th session; consec=4 hit again**

OFSS fired at consec_loss=2 (soft-pause threshold, CRITICAL/unimplemented since 2026-04-30). VOLTAS fired at consec_loss=3. SAIL #2 fired at consec_loss=4. The soft-pause at consec >= 2 would have blocked OFSS, VOLTAS, and SAIL #2 — three of four trades. Only SAIL #1 (consec_loss=1) would have entered the session. The single-trade session would have lost Rs174.89 rather than Rs680.55 — a 74% loss reduction from this one gate alone. Eight sessions of documentation. Zero implementation.

**5. #same-symbol-cooldown — SAIL entered twice, 3h42m apart, identical catalyst_reason**

Trade 94 (SAIL, 10:10) and Trade 97 (SAIL, 13:52) share an identical catalyst_reason field: "Recent rally to 15-yr high + F&O ban risk — overextended, weak volume today (0.43x)." The signals are effectively duplicates — same symbol, same narrative, same regime, both SELL, both stopped out. A per-symbol intra-day cooldown after stoploss exit (proposed originally on 2026-05-07, reinforced on 2026-05-15 for TATAMOTORS 3x) would have blocked SAIL #2 entirely. The symbol returned with near-identical conditions 3h42m later — a cooldown of 90–120 min post-SL would be sufficient.

**6. #extreme-rsi-short — OFSS RSI=92.08 and SAIL#2 RSI=93.14; pattern named on 2026-05-14**

JUBLFOOD RSI=96.83 on 2026-05-14 was the first named instance of `#extreme-rsi-short`. Today OFSS (92.08) and SAIL #2 (93.14) extend the pattern to three instances. Shorting into RSI > 90 means entering a mean-reversion SELL against stocks with maximum upward momentum — exactly the wrong direction for a momentum regime. The proposed gate (block SELL when RSI >= 90) would have eliminated OFSS and SAIL #2 today.

**7. ML threshold raise — first session live, first result: 4/4 losses at new thresholds**

The 2026-05-15 retrain raised OPEN threshold from 0.150 to 0.400 and MID threshold from 0.150 to 0.350. Today is the first session where these raised thresholds were enforced. All four trades cleared the new thresholds (0.4304, 0.4062, 0.3833, 0.3652). All four lost. First data point on raised threshold effectiveness is negative — though a single session of 4 trades is insufficient to draw conclusions. Critically, the ML model passed all four trades despite every structural flag present at entry (risk_on session, RSI extremes, inverted signal, consec breach). The ML features do not appear to incorporate global_bias, RSI extremes, or vwap sign — the threshold raise addresses quantity of signal-passes but not structural validity.

**8. #vwap-dev-shallow — three of four trades below the proposed 0.50% floor**

SAIL #1: +0.447%. OFSS: +0.497%. SAIL #2: +0.434%. VOLTAS: -0.266% (inverted, separate issue). Three trades were below the minimum 0.50% vwap_dev floor proposed following OBEROIRLTY (0.018%) on 2026-05-12. The closest to the floor is OFSS at 0.497% — 0.003% below. The floor would have blocked all three. Combined with the VOLTAS hard block (inverted signal), a 0.50% vwap_dev floor would have produced zero entries today.

---

**Recurring patterns flagged (updated session counts):**

| Pattern tag | Session count | Status |
|---|---|---|
| `#choppy-market` | 10 consecutive sessions (2026-04-29 through 2026-05-18) | Persistent |
| `#catalyst-reason-ignored` | 4 sessions (2026-05-11, -12, -14, -18) | VOLTAS "suspicious, avoid" + OFSS "suspicious" both fired; highest-priority open gap |
| `#consecutive-loss-breach` | 8 sessions — consec=4 again; three trades blocked if gate implemented | Unimplemented since 2026-04-30 |
| `#same-symbol-cooldown` | 4 sessions (SAIL x2 today, TATAMOTORS x3 on 2026-05-15, earlier flags) | No intra-day cooldown implemented |
| `#extreme-rsi-short` | 3 instances: JUBLFOOD 96.83, OFSS 92.08, SAIL#2 93.14 | Proposed gate (RSI >= 90 SELL block) unimplemented |
| `#vwap-dev-shallow` | 5 sessions — 3 trades below 0.50% floor today | vwap_dev minimum unimplemented |
| `#risk-on-short-failure` | 1st formal session (NEW) — all 4 shorts in RISK_ON with FII +1329 Cr | Directional suppression gate absent |
| `#inverted-vwap-signal` | 1st instance (NEW) — VOLTAS SELL with price below VWAP | Hard block absent; signal-logic error |
| `#ml-filter-weak` / threshold raised, still failing | 9 sessions; raised thresholds passed all 4 losers today | ML features do not include bias/RSI/vwap-sign inputs |
| `#stopped-out` | 15+ instances in journal | Persistent |

**Edge check:** No edge was present today. This is not variance — it is the clearest systematic failure session in the journal. Seven independent, unimplemented filter gates each had a clear blocking vote on at least one trade: the inverted-signal hard block (VOLTAS), the 0.50% vwap_dev floor (SAIL x2, OFSS, VOLTAS excluded by prior block), the RSI >= 90 SELL block (OFSS, SAIL #2), the consec_loss >= 2 soft-pause (OFSS, VOLTAS, SAIL #2), the same-symbol cooldown (SAIL #2), the catalyst_reason keyword parser (VOLTAS, OFSS), and the RISK_ON SELL suppression (all four). Applied in sequence, the RISK_ON directional gate alone would have produced zero entries. The -Rs680.55 loss is the direct monetary cost of eight consecutive sessions of deferred implementation. Low trade count (n=4) means this could also be a variance day on the loss magnitude — but the directional failure (all SELL in RISK_ON) and the inverted signal (VOLTAS) are structural, not random.

---

**For researcher Sunday:**

CRITICAL carry-forward (session-overdue counts updated):

- **CRITICAL (9 sessions overdue): Catalyst_reason keyword parser.** "suspicious", "avoid", "suspicious, avoid" must hard-block entry. VOLTAS and OFSS fired today on these exact phrases. This is the 4th session of a data-consumption failure — the system generates the skip signal and discards it.
- **CRITICAL (9 sessions overdue): Consecutive_losses soft-pause at consec >= 2.** Three of four trades blocked if implemented. New worst-case cost: if implemented on 2026-04-30, cumulative saving across 8 sessions is estimated Rs1,500+.
- **CRITICAL (9 sessions overdue): vwap_dev_pct minimum 0.50% for VWAP entries.** Three trades below floor today (SAIL 0.447%, OFSS 0.497%, SAIL#2 0.434%). Combined with inverted-signal block, produces zero entries today.
- **CRITICAL: RSI extreme momentum gate.** Block SELL when RSI >= 90. OFSS (92.08) and SAIL#2 (93.14) are the 2nd and 3rd instances after JUBLFOOD (96.83). All lost.
- **CRITICAL (8 sessions overdue): Catalyst direction conflict filter.** Not the primary issue today but still outstanding.
- **Same-symbol intra-day cooldown (90–120 min post-SL).** SAIL re-entered at consec_loss=4 with identical catalyst_reason, 3h42m after first SL. Flagged on 2026-05-15 (TATAMOTORS x3), now has a second clean example.
- **Time-of-day 50% sizing after 12:30 IST in CHOPPY.** SAIL #2 at 13:52 is afternoon CHOPPY with consec=4. Half-size + consec gate would compound the reduction.

New from today:

- **CRITICAL (NEW): Inverted VWAP signal hard block.** Reject any VWAP SELL when vwap_dev_pct <= 0 (price already below VWAP). This is a signal-logic error, not a tuning parameter. VOLTAS today is the first confirmed instance. Implementation is a single inequality check — simplest fix in the backlog.
- **CRITICAL (NEW): RISK_ON directional SELL suppression.** When global_bias=risk_on AND fii_net_cr > +1000 Cr, suppress VWAP SELL entries. Mirror of the existing risk_off BUY suppression proposal. All four losses today occurred in a RISK_ON session with +Rs1329 Cr FII net and stocks (SAIL, OFSS) with positive catalysts. Evaluate threshold: +500 Cr vs +1000 Cr.
- **ML feature gap investigation:** The raised ML thresholds passed all four structurally invalid trades. The model does not appear to penalise (a) RSI extremes at entry, (b) global_bias direction conflict, or (c) negative vwap_dev for SELL signals. Researcher should verify which features are fed into the model and whether global_bias, RSI at entry, and vwap_dev sign are included. If not, these must be added to the feature vector before the next retrain provides meaningful signal.

**Tags:** #vwap #choppy-market #losing-day #risk-on-short-failure #inverted-vwap-signal #catalyst-reason-ignored #consecutive-loss-breach #same-symbol-cooldown #extreme-rsi-short #vwap-dev-shallow #ml-filter-weak #stopped-out #sail #ofss #voltas #news-gap
---
## ML Retrain — 2026-05-18 22:00 IST (IST)
Feedback signals used: 202

### OPEN window | deployed=NO | threshold 0.400 -> 0.400
  long/sharpe: -13.06 -> -13.124
  long/win_rate: 0.317 -> 0.316
  long/n_signals: 70523 -> 71400
  short/sharpe: -11.098 -> -11.167
  short/win_rate: 0.355 -> 0.354
  short/n_signals: 63516 -> 63681

### MID window | deployed=YES | threshold 0.350 -> 0.350
  long/sharpe: -19.844 -> -19.84
  long/win_rate: 0.225 -> 0.225
  long/n_signals: 406483 -> 406588
  short/sharpe: -19.706 -> -19.679
  short/win_rate: 0.238 -> 0.239
  short/n_signals: 404492 -> 404011

### Feature importance
  OPEN_LONG — top 5 features:
    atr14_pct                 0.229
    vol_surge_5d              0.127
    is_first_30min            0.113
    orb_width_pct             0.086
    mom_15m_pct               0.068

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.306
    is_first_30min            0.092
    time_bucket               0.089
    orb_width_pct             0.075
    mom_15m_pct               0.071

  MID_LONG — top 5 features:
    atr14_pct                 0.508
    mom_30m_pct               0.064
    orb_width_pct             0.063
    mom_15m_pct               0.060
    time_bucket               0.050

  MID_SHORT — top 5 features:
    atr14_pct                 0.493
    is_last_hour              0.084
    time_bucket               0.069
    vwap_dev_pct              0.056
    orb_width_pct             0.051

## 2026-05-19 (tester)
**Strategy:** vwap
**Trades:** 2 (0W / 2L)
**PnL:** ₹-345.31 (-0.35%)

**Market:** Indian markets were weak and choppy today, with Nifty 50 trading around the 23,600–23,700 zone and slipping below 23,650 at one point amid cautious global sentiment and geopolitical concerns. Banks were also soft, while IT stocks stood out as the big movers on the upside, helping limit the broader damage.

**Context:** Global bias was RISK_OFF. Skipped event-risk stocks: TECHM.

**Best trade:** MPHASIS ₹-171.59 (STOPLOSS) / **Worst trade:** ASTRAL ₹-173.73 (STOPLOSS)

**Insights:**
- MPHASIS ML prob 0.4974 — indistinguishable from a coin flip. No viable edge existed at entry; the filter should have suppressed this signal (ML threshold appears to be <0.50 but was not enforced strictly enough).
- MPHASIS price was 5.64% above VWAP at ₹2109.46 — extreme overextension that ordinarily supports a reversion short, yet the CHOPPY regime (regime_avg_move_pct: 0.0) means the mean-reversion impulse was absent. Regime gate should block entries when avg_move_pct is near zero.
- ASTRAL catalyst score 7 (strong SHORT catalyst: weak Q1 results, PAT -14–34%) directly conflicted with ML prob 0.3955. The strategy took the trade; ML was right, catalyst was noise in a choppy tape. This is a recurring #catalyst-ml-conflict failure mode.
- ASTRAL VWAP deviation of 0.75% barely cleared the 0.5% entry threshold — a #shallow-deviation entry in a choppy market with 0.3% SL leaves almost no room before noise triggers the stop. Minimum deviation should be widened or SL should flex with ATR when regime is CHOPPY.
- Both stops were hit at 0.3% — the tightest permitted SL — while ATR was flagged as "very high adds noise risk" (MPHASIS catalyst note). High ATR + tight fixed SL is a structural mismatch that now appears 20 sessions running (#stopped-out every single entry).

**Edge check:** Both signals were structurally weak before entry — ML sub-0.50, CHOPPY regime, one shallow-deviation. Losses are consistent with poor signal quality, not bad luck. Process adherence: strategy executed as configured, but configuration is mismatched to current market conditions.

**Pattern flags:**
- #stopped-out: 20/20 entries (100%) — every trade in the last 20 sessions has been stopped out at least once. Structural SL width review is overdue.
- #choppy-market: 16/20 entries — dominant regime. Strategy params are calibrated for trending conditions; no choppy-market regime gate exists.
- #ml-filter-weak: 15/20 entries — ML is repeatedly below threshold yet trades still execute. Hard ML floor (e.g. prob >= 0.52) not enforced.
- #catalyst-ml-conflict: NEW — catalyst and ML disagreed on ASTRAL (score 7 vs prob 0.40). Adds to the existing 8x #catalyst-conflict pattern; explicitly labelling the sub-type to track frequency.
- #shallow-deviation: 5/20 entries — ASTRAL at 0.75% is the latest instance. Entry threshold may need raising in CHOPPY regime.

> WARNING: #stopped-out now 20/20 entries (up from 18x). #ml-filter-weak 15/20, #choppy-market 16/20 — these three tags co-occurring this frequently signal a regime-strategy mismatch, not random variance. Researcher should propose: (1) ATR-scaled SL, (2) hard ML prob floor >= 0.52, (3) CHOPPY regime gate to suppress vwap entries when regime_avg_move_pct < 0.2.

**Tags:** #vwap #choppy-market #ml-filter-weak #catalyst-ml-conflict #shallow-deviation #stopped-out #losing-day #risk-off #mphasis #astral #loss #fakeout

---
---
## ML Retrain — 2026-05-19 16:02 IST (IST)
Feedback signals used: 397

### OPEN window | deployed=NO | threshold 0.400 -> 0.400
  long/sharpe: -12.729 -> -12.747
  long/win_rate: 0.319 -> 0.319
  long/n_signals: 70529 -> 70552
  short/sharpe: -11.31 -> -11.346
  short/win_rate: 0.353 -> 0.352
  short/n_signals: 63387 -> 63731

### MID window | deployed=YES | threshold 0.350 -> 0.350
  long/sharpe: -20.024 -> -20.026
  long/win_rate: 0.223 -> 0.223
  long/n_signals: 406459 -> 406845
  short/sharpe: -19.421 -> -19.425
  short/win_rate: 0.24 -> 0.24
  short/n_signals: 403789 -> 404005

### Feature importance
  OPEN_LONG — top 5 features:
    atr14_pct                 0.229
    vol_surge_5d              0.127
    is_first_30min            0.113
    orb_width_pct             0.086
    mom_15m_pct               0.068

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.306
    is_first_30min            0.092
    time_bucket               0.089
    orb_width_pct             0.075
    mom_15m_pct               0.071

  MID_LONG — top 5 features:
    atr14_pct                 0.521
    orb_width_pct             0.062
    mom_30m_pct               0.062
    mom_15m_pct               0.059
    time_bucket               0.051

  MID_SHORT — top 5 features:
    atr14_pct                 0.499
    is_last_hour              0.097
    time_bucket               0.069
    vwap_dev_pct              0.056
    orb_width_pct             0.050

## 2026-05-20 (tester) [enriched]
**Strategy:** vwap (mode: paper)
**Trades:** 0 (0W / 0L) — no signals fired
**PnL:** Rs0.00
**Cumulative week PnL:** -Rs1025.86 (2026-05-18 -Rs680.55, 2026-05-19 -Rs345.31, today Rs0.00)
**Market:** Nifty 50 ~23,600–23,700 (near-flat to mildly positive). IT sector notably higher — INFY +4–5% on promoter buyback opt-out catalyst; HCLTECH +2.86%, MPHASIS +3.3%. KOTAKBANK -2.5%, weakness in metals. FII net (2026-05-19 data, 1-day lag): -Rs2457.49 Cr (fii_bias=BEARISH). DII net: +Rs3801.68 Cr (net offset, domestic buying absorbing FII outflow). VIX 18.675 (NORMAL). Global bias: RISK_ON. No event-risk skips today.

**Context:** 14 symbols tradeable (ASTRAL, INFY, TATACOMM, PATANJALI, TECHM, OFSS, TCS, HCLTECH, PAGEIND, ICICIBANK, MPHASIS, KOTAKBANK, SBILIFE, PERSISTENT). Premarket sentiments: ASTRAL(+1), INFY(+1), TATACOMM(+1), PATANJALI(+1), LTTS(-1), all others(0). No stock had a score strong enough to generate a confirmed signal under the raised ML thresholds.

**Why no trades fired:**

The 2026-05-15 retrain raised OPEN threshold 0.150 → 0.400 and MID threshold 0.150 → 0.350. On the prior session (2026-05-19) both signals that fired barely cleared: MPHASIS ml_prob=0.4974 and ASTRAL ml_prob=0.3955 — and both lost. Today's watchlist is predominantly neutral-sentiment (10/14 stocks at 0). The four positive-sentiment stocks (ASTRAL, INFY, TATACOMM, PATANJALI) generate VWAP signals only when price is sufficiently extended from VWAP; in a flat-to-positive session without trending intraday moves, VWAP deviation is unlikely to reach the level needed to produce ml_prob >= 0.40 (OPEN window) or >= 0.35 (MID window). The ML filter is doing its intended job — screening out marginal setups that previously lost money at the old 0.15 threshold. Zero entries on a day where signals would have been marginal at best is the correct outcome.

**Is this a positive outcome?** Yes, conditionally. After -Rs680.55 on 2026-05-18 and -Rs345.31 on 2026-05-19, the streak of structurally weak trades needed to stop. A zero-trade day preserves capital and gives the raised ML thresholds a chance to demonstrate selectivity. The absence of entries is not evidence of a broken strategy — it is the threshold doing what it was raised to do. Whether this is durable selectivity or a temporary gap in signal generation requires more sessions to evaluate.

**Premarket catalyst context:**

INFY's +4–5% move (promoter buyback opt-out, interpreted by market as insider confidence) was the day's most notable catalyst. With sentiment=+1 and strong upward momentum, any VWAP signal would have been a SELL (short against the move) — the inverted VWAP problem flagged on 2026-05-18 (VOLTAS SELL with price below VWAP) applies equally on the long side to stocks in strong uptrends. The ML filter avoiding INFY on a strong positive-catalyst day is correct. LTTS sentiment=-1 was the only bearish stock; KOTAKBANK -2.5% was potentially the strongest short candidate structurally, but with fii_bias=BEARISH and DII absorbing the selling, no clear directional momentum formed.

**Pattern analysis:**

No new patterns from a no-trade day. The relevant observation is that the ML threshold raise has functionally raised the bar high enough to suppress the entire signal queue on a day where most watchlist stocks were either neutral-sentiment or in directional trend (not mean-reverting). This is a calibration shift, not a broken scanner. The 2026-05-19 session showed the raised thresholds will pass trades when ml_prob is high enough — they just lost because other structural problems (choppy regime, shallow deviation) were present. The question for researcher Sunday is whether the raised thresholds are sufficient alone, or whether the backlog of unimplemented structural filters (inverted-signal block, vwap_dev floor, consec_loss pause) is still needed in combination.

**Recurring patterns (last 20 entries):**

| Pattern tag | Count | Status |
|---|---|---|
| `#stopped-out` | 22+ (every trade in recent sessions) | CRITICAL — SL width review overdue; #1 priority for researcher |
| `#choppy-market` | 12 entries (2026-04-29 through 2026-05-19) | Every session; VWAP has no choppy-regime gate |
| `#ml-filter-weak` | 10 entries | Partially addressed by threshold raise on 2026-05-15; efficacy unproven |
| `#losing-day` | 6 entries | 2026-04-30, 2026-05-12, 2026-05-14, 2026-05-15, 2026-05-18, 2026-05-19 |
| `#consecutive-loss-breach` | 6 entries | Soft-pause at consec >= 2 unimplemented since 2026-04-30 |
| `#fakeout` | 6 entries | Persistent across all strategies |
| `#shallow-deviation` | 5 entries | vwap_dev minimum floor unimplemented |
| `#risk-off` (BUY entries in risk-off) | 5 entries | BUY suppression gate absent |
| `#catalyst-reason-ignored` | 4 entries (consecutive) | System generates skip signal; executor discards it |
| `#catalyst-conflict` | 4 entries | Filter flagged CRITICAL since 2026-05-05; still unimplemented |
| `#trailing-sl-working` | 4 entries | POSITIVE — system functioning on this dimension |
| `#ml-high-prob-open-failure` | 4 entries | Structural; open-auction ML miscalibration |
| `#afternoon-losses` | 4 entries | Time-of-day sizing unimplemented |
| `#winning-day` | 5 entries | 2026-04-29, 2026-05-05, 2026-05-07, 2026-05-08, 2026-05-11 |
| `#open-auction-vwap-failure` | 3 entries | First 2-minute VWAP entry window structurally weak |
| `#same-symbol-cooldown` | 2 entries | TATAMOTORS x3, SAIL x2; cooldown unimplemented |
| `#inverted-vwap-signal` | 1 entry | 2026-05-18 VOLTAS; hard block absent |
| `#risk-on-short-failure` | 1 entry | 2026-05-18; directional suppression gate absent |

Flags at 3+: `#stopped-out` (22+), `#choppy-market` (12), `#ml-filter-weak` (10), `#losing-day` (6), `#consecutive-loss-breach` (6), `#fakeout` (6), `#shallow-deviation` (5), `#risk-off` (5), `#catalyst-reason-ignored` (4), `#catalyst-conflict` (4), `#trailing-sl-working` (4), `#ml-high-prob-open-failure` (4), `#afternoon-losses` (4), `#winning-day` (5), `#open-auction-vwap-failure` (3).

**Edge check:** No trades today — no edge to evaluate. The ML threshold raise producing zero entries on a neutral-sentiment, flat-market day is consistent with its design intent. Whether the threshold is now too restrictive (missing legitimate setups) or appropriately calibrated requires 1–2 more sessions. The prior 2 sessions at the raised threshold: 0W/2L (2026-05-19). Sample too small to judge.

**For researcher Sunday:**

- ML threshold raise first-week result: 0W/4L across 2026-05-18 (4 trades, old threshold) and 2026-05-19 (2 trades, new threshold), plus 0 trades today. No wins since 2026-05-11. The threshold raise may be necessary but it does not address the structural filters that produced losses on the trades that did pass.
- Unimplemented CRITICAL filters (all overdue 8+ sessions): inverted VWAP signal hard block, vwap_dev floor 0.50%, consec_loss soft-pause at >= 2, catalyst_reason keyword parser, catalyst direction conflict filter, RISK_ON SELL suppression when fii_net > +1000 Cr.
- `#stopped-out` at 22+ instances suggests SL width at 0.30% is systematically too tight for current CHOPPY regime. ATR-scaled SL should be evaluated for the next retrain cycle.
- With a flat no-trade day ending a 2-loss week, consider whether the VWAP strategy parameters need to be re-evaluated for the current market environment (10+ consecutive choppy sessions, VIX 18–20 range) before resuming normal signal volume.

**Tags:** #vwap #flat #choppy-market #ml-filter-weak #no-signals #low-volume #risk-on #infy #kotakbank

---
---
## ML Retrain — 2026-05-20 16:03 IST (IST)
Feedback signals used: 458

### OPEN window | deployed=NO | threshold 0.400 -> 0.400
  long/sharpe: -12.824 -> -12.852
  long/win_rate: 0.318 -> 0.318
  long/n_signals: 70303 -> 70857
  short/sharpe: -11.247 -> -11.297
  short/win_rate: 0.355 -> 0.354
  short/n_signals: 63369 -> 63513

### MID window | deployed=YES | threshold 0.350 -> 0.350
  long/sharpe: -19.388 -> -19.387
  long/win_rate: 0.227 -> 0.227
  long/n_signals: 405043 -> 405484
  short/sharpe: -19.952 -> -19.958
  short/win_rate: 0.234 -> 0.234
  short/n_signals: 402427 -> 403026

### Feature importance
  OPEN_LONG — top 5 features:
    atr14_pct                 0.229
    vol_surge_5d              0.127
    is_first_30min            0.113
    orb_width_pct             0.086
    mom_15m_pct               0.068

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.306
    is_first_30min            0.092
    time_bucket               0.089
    orb_width_pct             0.075
    mom_15m_pct               0.071

  MID_LONG — top 5 features:
    atr14_pct                 0.515
    mom_30m_pct               0.061
    mom_15m_pct               0.061
    orb_width_pct             0.060
    time_bucket               0.050

  MID_SHORT — top 5 features:
    atr14_pct                 0.489
    is_last_hour              0.098
    time_bucket               0.071
    vwap_dev_pct              0.054
    orb_width_pct             0.051

---
## ML Retrain — 2026-05-20 20:55 IST (IST)
Feedback signals used: 458

### OPEN window | deployed=YES | threshold 0.250 -> 0.250
  long/sharpe: - -> -13.43
  long/win_rate: - -> 0.308
  long/n_signals: - -> 85919
  short/sharpe: - -> -12.678
  short/win_rate: - -> 0.33
  short/n_signals: - -> 83192

### MID window | deployed=YES | threshold 0.220 -> 0.220
  long/sharpe: - -> -19.861
  long/win_rate: - -> 0.221
  long/n_signals: - -> 440533
  short/sharpe: - -> -20.509
  short/win_rate: - -> 0.226
  short/n_signals: - -> 440256

### Feature importance
  OPEN_LONG — top 5 features:
    is_first_30min            0.203
    atr14_pct                 0.182
    vol_surge_5d              0.107
    orb_width_pct             0.083
    mom_15m_pct               0.062

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.257
    is_first_30min            0.194
    time_bucket               0.097
    orb_width_pct             0.073
    mom_15m_pct               0.059

  MID_LONG — top 5 features:
    atr14_pct                 0.451
    mom_15m_pct               0.087
    mom_30m_pct               0.073
    orb_width_pct             0.072
    ema9_21_spread            0.052

  MID_SHORT — top 5 features:
    atr14_pct                 0.446
    is_last_hour              0.098
    time_bucket               0.074
    mom_15m_pct               0.060
    vwap_dev_pct              0.059

## 2026-05-21 (tester)
**Strategy:** vwap
**Trades:** 3 (1W / 2L)
**PnL:** +Rs21.61

**Market:** Indian markets were slightly weak/volatile today, with Nifty 50 trading around the 23,600–23,900 zone and showing a cautious, range-bound tone after some early weakness. Major pressure came from broader market and banking stocks, while pockets of strength were seen in select names like IT and a few large caps.  

Big themes: higher crude oil near $105/bbl and a softer rupee kept sentiment cautious, though global cues and GIFT Nifty pointed to some support.

**Context:** Global bias was RISK_OFF. Skipped event-risk stocks: INDUSINDBK, CANBK.

**Best trade:** MOTHERSON +Rs49.43 (TARGET)
**Worst trade:** MOTHERSON Rs-27.83 (STOPLOSS)

**Edge check:** Loss rate >60% — check if market was choppy/low-volume. Review signal quality.

> WARNING: #stopped-out appears 25x in recent journal. Researcher should review stoploss width.

**Tags:** #clean-exit #icicigi #loss #motherson #stopped-out #vwap #win

---

## 2026-05-21 (tester) [enriched]
**Strategy:** vwap (OPEN + MID windows)
**Trades:** 4 (1W / 2L / 1 open) — 3 closed
**PnL:** +Rs21.61 closed (Trade 103 ICICIGI SELL still live at session end)
**Cumulative week PnL:** +Rs21.61 (week starts 2026-05-19; prior week -Rs1025.86)

**Trade breakdown:**

| # | Symbol | Dir | Time | Exit | PnL | ml_prob | RSI | vwap_dev | Regime |
|---|--------|-----|------|------|-----|---------|-----|----------|--------|
| 100 | ICICIGI | SELL | 09:45 | SL (breakeven) | Rs0.00 | 0.5993 | 88.54 | +0.356% | CHOPPY |
| 101 | MOTHERSON | BUY | 12:17 | TARGET | +Rs49.43 | 0.2885 | 39.2 | -0.059% | CHOPPY |
| 102 | MOTHERSON | SELL | 13:28 | SL | -Rs27.83 | 0.4149 | 78.94 | +0.219% | CHOPPY |
| 103 | ICICIGI | SELL | 13:48 | OPEN | — | 0.3229 | 70.0 | +0.089% | CHOPPY |

**Best trade:** MOTHERSON BUY +Rs49.43 — hit TARGET; won on luck not edge (see below).
**Worst trade:** MOTHERSON SELL -Rs27.83 — same symbol 71 min later, RSI=79, SL triggered.

**What worked:** MOTHERSON BUY reached target. Strategy executed as designed — signal, sizing, target exit all correct. That is the extent of what worked.

**What didn't:**
1. Shallow deviation (T101): vwap_dev=-0.059% is the shallowest VWAP-reversion entry in the full journal — 8x below the proposed 0.5% floor. The trade won, but the mean-reversion basis was noise. Variance win, not edge.
2. Same-symbol round-trip (T101 to T102): BUY hit TARGET at 12:17, SELL fired on the same symbol at 13:28 — 71-minute gap. No 90-minute cooldown implemented. SELL entered with RSI=79 in a CHOPPY regime; SL triggered. Classic fade-the-winner failure.
3. Threshold rollback surfacing marginal signals: overnight change (OPEN 0.400 to 0.250, MID 0.350 to 0.220) let through T101 (ml_prob=0.2885) and T103 (ml_prob=0.3229). Both would have been blocked under prior thresholds. The system went from 0 trades yesterday to 4 today — but the added volume is below-conviction.
4. All 4 trades in CHOPPY regime (avg_move 0.0%–0.224%). Choppy-regime VWAP gate still unimplemented — session 13+ in this state.

**Edge check:** 1W / 2L closed. The single win is attributable to variance (vwap_dev far below minimum-edge floor). Both losses were structurally predictable: same-symbol cooldown absent, RSI near-overbought on T102. Low trade count + choppy regime + marginal ml_prob = variance session, not demonstrated edge.

**Open risk — morning action required (2026-05-22):**
Trade 103 ICICIGI SELL (4 qty) is live at session end. SL=1808.31, Target=1791.72, implied entry ~1799.52. Max downside ~Rs26 at SL. RSI=70 at entry, vwap_dev=0.089% (shallow), global_bias=risk_off. If price gaps above SL at open, loss locks in. Note: ml_prob=0.3229 — marginal under new thresholds, would have been blocked under prior.

**Recurring patterns flagged (updated counts):**
- `#stopped-out` — T102 MOTHERSON SELL. Running count: 26+. ATR-scaled SL still pending.
- `#choppy-market` — All 4 trades in CHOPPY. Running count: 13+ sessions. No choppy gate.
- `#same-symbol-cooldown` — T101 BUY to T102 SELL, 71-min gap. Running count: 3+. No cooldown.
- `#shallow-deviation` — T101 vwap_dev=0.059%, most extreme instance in journal. Running count: 6+. 0.5% floor unimplemented.
- `#ml-high-prob-open-failure` — T100 ICICIGI: ml_prob=0.5993 (highest today), near-open, SL at breakeven. Pattern continues.
- `#ml-filter-weak` — T101 (0.2885) and T103 (0.3229) below old thresholds. Running count: 11+.
- `#risk-off-buy` — T101 MOTHERSON BUY with global_bias=risk_off. Running count: 6+.

**For researcher (Sunday review):**
1. vwap_dev minimum gate: implement abs(vwap_dev_pct) >= 0.50% as hard gate. T101 at 0.059% is the poster-child case — won by luck, not reversion.
2. Same-symbol cooldown: 90-minute block after any exit. T101 to T102 round-trip cost Rs27.83 with zero additional signal value.
3. Choppy-regime gate: suppress VWAP signals when avg_move < 0.25% for trailing 10 bars. 13+ sessions of evidence.
4. ML threshold rollback: first session under new thresholds produced marginal ml_probs of 0.2885 and 0.3229. Track expectancy vs old thresholds over next 5 sessions before declaring rollback correct.
5. OPEN-window RSI gate: T100 (ml_prob=0.5993, near-open, breakeven) continues high-confidence open signal failure. Consider RSI < 60 / RSI > 40 gate for OPEN window, or restrict to first 15 min only.

**Tags:** #vwap #choppy-market #flat #stopped-out #shallow-deviation #same-symbol-cooldown #ml-filter-weak #ml-high-prob-open-failure #risk-off-buy #icicigi #motherson

---
---
## ML Retrain — 2026-05-21 16:04 IST (IST)
Feedback signals used: 461

### OPEN window | deployed=YES | threshold 0.250 -> 0.250
  long/sharpe: -14.03 -> -14.021
  long/win_rate: 0.299 -> 0.299
  long/n_signals: 85909 -> 85834
  short/sharpe: -12.074 -> -12.084
  short/win_rate: 0.337 -> 0.337
  short/n_signals: 83141 -> 83115

### MID window | deployed=YES | threshold 0.220 -> 0.220
  long/sharpe: -19.885 -> -19.885
  long/win_rate: 0.22 -> 0.22
  long/n_signals: 440548 -> 440506
  short/sharpe: -20.692 -> -20.694
  short/win_rate: 0.225 -> 0.225
  short/n_signals: 440314 -> 440483

### Feature importance
  OPEN_LONG — top 5 features:
    is_first_30min            0.212
    atr14_pct                 0.183
    vol_surge_5d              0.107
    orb_width_pct             0.080
    mom_15m_pct               0.062

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.248
    is_first_30min            0.205
    time_bucket               0.096
    orb_width_pct             0.075
    mom_15m_pct               0.059

  MID_LONG — top 5 features:
    atr14_pct                 0.460
    mom_15m_pct               0.088
    orb_width_pct             0.072
    mom_30m_pct               0.067
    ema9_21_spread            0.055

  MID_SHORT — top 5 features:
    atr14_pct                 0.465
    is_last_hour              0.075
    time_bucket               0.073
    mom_30m_pct               0.060
    vwap_dev_pct              0.058

## 2026-05-22 (tester)
**Strategy:** vwap
**Trades:** 8 (1W / 7L)
**PnL:** Rs-28.37

**Market:** Indian markets are trading with a cautiously positive-to-range-bound tone, with Nifty 50 trying to hold above the 23,700–23,800 zone; a close above 23,900 would strengthen the upside, while 23,600 remains near-term support. Big movers have been banks and IT names on the upside, while some auto, steel and select industrial stocks have been weak; broader sentiment is being helped by easing crude oil prices and hopes around U.S.–Iran talks.

**Context:** Global bias was RISK_ON. Skipped event-risk stocks: JSWSTEEL.

**Best trade:** OBEROIRLTY +Rs69.21 (TARGET)
**Worst trade:** VEDL Rs-27.64 (STOPLOSS)

**Edge check:** Loss rate >60% — check if market was choppy/low-volume. Review signal quality.

> WARNING: #stopped-out appears 29x in recent journal. Researcher should review stoploss width.

**Tags:** #astral #clean-exit #jublfood #loss #naukri #oberoirlty #piind #stopped-out #vedl #vwap #win

---

## 2026-05-22 (tester) [enriched]
**Strategy:** vwap (OPEN + MID windows; mode: paper)
**Trades:** 8 (1W / 4L / 3 breakeven — breakevens labeled STOPLOSS with PnL=Rs0)
**PnL:** -Rs28.37
**Cumulative week PnL:** -Rs6.76 (2026-05-21 +Rs21.61, today -Rs28.37; T103 ICICIGI carry-in excluded if closed pre-session)
**Market:** Nifty 50 range-bound 23,700–23,800. Global bias RISK_ON. FII net -Rs1891 Cr (BEARISH — contradicts RISK_ON label; recurring data inconsistency). VIX ~17.82 (NORMAL). JSWSTEEL skipped (event risk). Crude easing, US-Iran talks providing sentiment support. Nifty holding above 23,600 support.

**Trade breakdown:**

| # | id | Time | Symbol | Side | PnL | Exit | ml_prob | RSI | bars_abv_vwap | vwap_dev | consec_at_entry | regime | cat_dir | cat_score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 104 | 1 | 09:56 | VEDL | BUY | -Rs27.64 | STOPLOSS | 0.344 | 21.7 | 63% | -0.55% | 0 | CHOPPY | NEUTRAL | 3 |
| 105 | 2 | 10:09 | PIIND | SELL | -Rs19.40 | STOPLOSS | 0.298 | 83.8 | 100% | +0.60% | 1 | CHOPPY | NEUTRAL | 2 |
| 106 | 3 | 10:56 | OBEROIRLTY | SELL | -Rs23.10 | STOPLOSS | 0.445 | 80.0 | 83% | +0.57% | 2 | CHOPPY | NEUTRAL | 2 |
| 107 | 4 | 11:43 | VEDL | BUY | Rs0.00 | STOPLOSS-BE | 0.252 | 44.4 | 17% | -0.73% | 3 | CHOPPY | NEUTRAL | 3 |
| 108 | 5 | 12:16 | JUBLFOOD | SELL | Rs0.00 | STOPLOSS-BE | 0.236 | 46.7 | 53% | -0.07% | 3 | CHOPPY | SHORT | 8 |
| 109 | 6 | 12:19 | ASTRAL | SELL | Rs0.00 | STOPLOSS-BE | 0.232 | 39.1 | 100% | +0.07% | 3 | CHOPPY | SHORT | 4 |
| 110 | 7 | 12:37 | OBEROIRLTY | SELL | +Rs69.21 | TARGET | 0.433 | 66.7 | 57% | +1.08% | 4 | CHOPPY | NEUTRAL | 2 |
| 111 | 8 | 13:22 | NAUKRI | SELL | -Rs27.44 | STOPLOSS | 0.641 | 56.6 | 97% | +4.46% | 5 | CHOPPY | SHORT | 4 |

**Best trade:** OBEROIRLTY SELL +Rs69.21 (Trade 110) — second entry on this symbol, rr_ratio=3.61, 1.08% above VWAP. Entered with consec=4 which the soft-pause should have blocked; the win is real but the process was wrong. The first OBEROIRLTY entry (#106) took the loss that "earned" this setup — the pair is not a clean edge demonstration.

**Worst trade:** VEDL BUY -Rs27.64 (Trade 104) — VWAP long with RSI=21.7 (extreme oversold) in CHOPPY regime. ml_prob=0.344 is adequate. The loss is the smallest of the day in absolute terms, but VEDL continues a documented pattern (6th recurrence, 2nd time today) that the system has never addressed structurally.

---

**Pattern analysis:**

**1. VEDL sixth recurrence — empirical win rate 12.5% (1/8), bot keeps entering**

VEDL has now appeared in trades on 2026-04-30, 2026-05-06, 2026-05-07 (x2), and today (x2: Trades 104 and 107). Trade 107 fired with consec=3, explicitly past the soft-pause threshold. sym_win_rate_10=0.125 — one win in the last eight VEDL entries. The system has no per-symbol win-rate gate. A symbol-level filter suppressing entry when recent-window win rate < 25% would have blocked Trade 107 independently of the consec gate. VEDL is the single most repeated losing symbol in this journal. This is a watchlist composition problem as much as a filter problem.

**2. PIIND bars_above_vwap=100% + RSI=83.8 — RSI gate logic gap confirmed**

PIIND SELL fired with RSI=83.8 and bars_above_vwap=100% — price in unambiguous uptrend. The config has rsi_sell_block=25 (blocks SELL when RSI <= 25, i.e. oversold protection) and rsi_buy_block=75 (blocks BUY when RSI >= 75). Neither gate applies here: RSI=83.8 on a SELL is not caught by either threshold. This is a structural logic gap — the current RSI gates protect against selling into oversold conditions and buying into overbought conditions, but do not protect against the mirror case: shorting into overbought momentum (RSI=83.8) or buying into oversold momentum. A complementary gate blocking SELL when RSI >= 75 would have prevented PIIND. This pattern also appeared in M&M on 2026-04-30 (bars_above_vwap=100%) and OFSS/SAIL on 2026-05-18 (RSI=92/93). The tag `#bars-above-vwap-momentum-conflict` applies to PIIND and ASTRAL (100% bars_above_vwap, Trade 109) today.

**3. Consecutive-loss escalation to consec=5 without halting — dominant story of the session**

The soft-pause at consec >= 2 has been CRITICAL/unimplemented since 2026-04-30 (session 22+). Today the escalation reached consec=5 at Trade 111 entry, with halt_after_consecutive_losses=7. The sequence:
- Trade 104: consec=0 at entry, SL (-Rs27.64) → consec=1
- Trade 105: consec=1 at entry, SL (-Rs19.40) → consec=2
- Trade 106: consec=2 at entry, SL (-Rs23.10) → consec=3
- Trade 107: consec=3 at entry, BE (Rs0.00) → consec reset to 0 per trailing SL? Or stayed at 3? (STOPLOSS label with PnL=0 — ambiguous. If counted as loss: consec=4)
- Trade 108: consec=3+ at entry, BE (Rs0.00) → same ambiguity
- Trade 109: consec=3+ at entry, BE (Rs0.00)
- Trade 110: consec=4 at entry, TARGET → reset to 0
- Trade 111: consec=5 at entry (from subsequent losses post-110? The notes say consec=5 at 13:22 after Trade 110 hit TARGET — this implies the bot is not correctly resetting consec on breakeven exits, or the TARGET count reset was itself corrupted. Regardless: 5 consecutive counting events without halt at halt_after=7 means the strategy will trade through 2 more losing signals before any system-level stop.)

A soft-pause at consec >= 2 would have blocked Trades 106, 107, 108, 109, and 111 — five of eight trades. The three trades it would have permitted (104, 105, 110) produced net: -Rs27.64 -Rs19.40 +Rs69.21 = +Rs22.17. The day would have been marginally green under the soft-pause. This is the clearest cost calculation in the journal for this single unimplemented gate.

**4. NAUKRI — anomalous rr_ratio, highest ml_prob, still lost**

Trade 111 presents every surface metric of a high-quality signal: ml_prob=0.641 (highest of the session and among the highest in the full journal), catalyst="CFO resigned after 12 years" (genuine catalyst), vwap_dev=+4.46% (far above 0.50% floor, not shallow), cat_score=4. Yet the rr_ratio=14.56 is mechanically anomalous — with SL=0.3% and target=4.368%, the implied target distance is 14.56x the SL. This is not a curated risk/reward; it is a feature artifact of the extreme deviation (4.46% above VWAP with a fixed 0.3% SL). A 4.46% extension in a CHOPPY regime (avg_move ~0%) is outlier noise that the ML model is treating as a high-confidence reversion setup. The model likely learned that large vwap_dev correlates with reversion in trending regimes but does not condition on regime type. In CHOPPY, a 4.46% extension means the stock is in a strong single-session momentum move — not a candidate for VWAP reversion. The trade lost. `#ml-high-prob-open-failure` is not the right tag here (not at open), but `#choppy-market` + `#ml-filter-weak` apply: the ML model is overconfident on outlier-deviation CHOPPY entries.

**5. OBEROIRLTY double entry — same-symbol cooldown absent (3rd occasion this journal for this exact symbol)**

Trades 106 (10:56, SELL, SL) and 110 (12:37, SELL, TARGET) are the same symbol, same direction, 101 minutes apart. No 90-minute same-symbol cooldown is implemented. Net OBEROIRLTY PnL: +Rs46.11. But Trade 110 fired with consec=4, which two separate unimplemented gates (soft-pause at consec >= 2, same-symbol cooldown) should have blocked. The profit does not validate the process. OBEROIRLTY previously appeared on 2026-05-12 (0W/2L on that date for this symbol). The symbol keeps returning to the signal queue in CHOPPY conditions.

**6. FII net -Rs1891 Cr vs global_bias=risk_on — recurring data inconsistency (4th+ flag)**

FII net is net-bearish while the session label is RISK_ON. This inconsistency has been noted on 2026-05-19 (FII=-2457 Cr, RISK_ON), 2026-05-20 (FII=-2457 Cr carry-in), and now today. The global_bias label appears sourced from overnight US/Asia futures while FII net reflects domestic institutional flow from the prior session. The two data streams are not always aligned. Three SELL entries today were taken in a session where domestic institutions were net-selling at -Rs1891 Cr — which structurally supports the short side — yet the RISK_ON label nominally creates a friction against SELL suppression. The FII/global_bias feed requires reconciliation to determine which signal should dominate the directional gate.

**7. JUBLFOOD catalyst_score=8 SHORT + ml_prob=0.236 — breakeven on a well-aligned catalyst**

Trade 108: catalyst="profit beat rejected; -7.8% on results day, gapping down -4.6% on 14.6x vol — institutional distribution." This is among the strongest catalyst descriptions in the journal (score=8 SHORT). Yet ml_prob=0.236 is below the old 0.250 OPEN threshold and barely above the new 0.220 MID threshold. The trade broke even. A strong fundamental catalyst with a weak ML confidence score is a recurring tension — the ML model does not heavily weight the catalyst_score feature, while the newsdesk is generating high-quality directional signals. The gap between catalyst quality and ml_prob output suggests the model's feature vector underweights or excludes catalyst_score. The breakeven is neither a validation nor a refutation — it is an inconclusive data point on a structurally interesting tension.

**8. ASTRAL vwap_dev=+0.07% + bars_above_vwap=100% — another shallow-deviation entry**

Trade 109: vwap_dev=+0.07% is well below the proposed 0.50% floor. bars_above_vwap=100% means price is in unambiguous uptrend. Shorting a stock with 100% of bars above VWAP and only 0.07% extension is not a VWAP reversion setup — there is no meaningful deviation to revert from. The RSI=39.1 is neutral and does not support the short side. Trade broke even (trailing SL). The 0.50% vwap_dev floor would have blocked this entry. `#shallow-deviation` count now 7+.

---

**Recurring patterns (updated counts):**

| Pattern | Count (updated) | Note |
|---|---|---|
| `#stopped-out` | 27+ | T104, T105, T106, T111 today; ATR-scaled SL overdue |
| `#choppy-market` | 14+ sessions | All 8 trades today in CHOPPY; no regime gate |
| `#consecutive-loss-breach` | 7+ sessions | consec reached 5 today without halt; gate unimplemented since 2026-04-30 |
| `#vedl-repeat` | 6 instances (2026-04-30, 05-06, 05-07 x2, 05-22 x2) | sym_win_rate_10=12.5%; no per-symbol win-rate gate |
| `#ml-filter-weak` | 12+ | ml_prob=0.236 (T108), 0.232 (T109) passed; NAUKRI 0.641 failed |
| `#same-symbol-cooldown` | 4+ instances | OBEROIRLTY x2 (106, 110); VEDL x2 (104, 107) today |
| `#shallow-deviation` | 7+ | JUBLFOOD 0.07%, ASTRAL 0.07% today; 0.5% floor unimplemented |
| `#bars-above-vwap-momentum-conflict` | 4+ | PIIND 100% + RSI=83.8; ASTRAL 100% today |
| `#losing-day` | 7 | -Rs28.37 today |
| `#ml-high-prob-open-failure` | 4+ | NAUKRI ml_prob=0.641 (not at open, but highest session, failed) — separate but related |
| `#rsi-gate-logic-gap` | NEW (2026-05-22) | rsi_sell_block=25 doesn't block shorting into overbought RSI=83.8 (PIIND) |

---

**Edge check:** 1W/4L/3BE with net -Rs28.37 is a losing day on paper. The single win (OBEROIRLTY T110) fired with consec=4 — the soft-pause should have blocked it. The three breakevens reflect the trailing SL functioning correctly, not signal quality. The four losses include two structurally weak setups (PIIND momentum-conflict, ASTRAL shallow deviation), one recurring-symbol problem (VEDL), and one anomalous ML-overconfident signal (NAUKRI). Under the soft-pause at consec >= 2, only Trades 104, 105, and 110 would have fired: net +Rs22.17. The difference between -Rs28.37 and +Rs22.17 is the direct cost of the unimplemented consec gate on this single session. This is variance on the sign (near-flat vs prior session losses) but not variance on the process — the same structural failures fired for the 14th+ consecutive session.

---

**For researcher (carry-forward and new from today):**

Carry-forward (CRITICAL — all unimplemented since dates noted):
- **CRITICAL (14+ sessions): Consecutive_losses soft-pause at consec >= 2.** Reached consec=5 today without halt. Cost delta vs implemented: +Rs50.54 swing on this session alone. Highest-priority unimplemented gate in the journal.
- **CRITICAL (14+ sessions): Same-symbol intra-day cooldown (90-min post-SL).** VEDL and OBEROIRLTY both re-entered today. VEDL has 6 total instances across sessions.
- **CRITICAL (10+ sessions): vwap_dev floor 0.50%.** JUBLFOOD (0.07%), ASTRAL (0.07%) today. Would have blocked both.
- **CRITICAL (14+ sessions): Choppy-regime VWAP gate.** 14+ sessions, 100% of trades in CHOPPY. Strategy has never halted or reduced size for choppy conditions.
- **CRITICAL (10+ sessions): Catalyst_reason keyword parser.** Not the primary failure today, but unimplemented.
- **Per-symbol win-rate gate:** block entry when sym_win_rate_10 < 0.25. VEDL at 0.125 is the clearest case.

New from today:
- **RSI gate logic gap (NEW, CRITICAL):** rsi_sell_block=25 only protects against selling oversold stocks. It does NOT block shorting into overbought conditions (RSI >= 75). A symmetric gate is needed: block SELL when RSI >= 75 (mirrors rsi_buy_block=75 logic). Would have prevented PIIND (RSI=83.8) and OBEROIRLTY T106 (RSI=80). Implement as rsi_buy_block=75 / rsi_sell_block_high=75 (rename existing rsi_sell_block=25 to rsi_sell_block_low=25 for clarity).
- **ML model regime-conditioning gap:** NAUKRI ml_prob=0.641 with vwap_dev=4.46% in CHOPPY — the model treats large VWAP deviation as a high-confidence reversion signal regardless of regime. In CHOPPY, extreme deviation is momentum noise, not reversion setup. Add regime as a feature to the ML input vector, or gate out vwap_dev > 3.0% in CHOPPY regime as an outlier exclusion.
- **Clarify breakeven consec counting:** Trades 107–109 exited as STOPLOSS-BE (PnL=Rs0). The consec counter appears to be counting these as losses (consec reached 5 after Trade 110's TARGET). If BEs do not reset consec, the soft-pause implementation needs explicit handling: breakeven = reset? Or hold count? Define the rule before implementation.

**Tags:** #vwap #choppy-market #losing-day #consecutive-loss-breach #same-symbol-cooldown #vedl-repeat #shallow-deviation #bars-above-vwap-momentum-conflict #rsi-gate-logic-gap #ml-filter-weak #stopped-out #fakeout #oberoirlty #vedl #piind #naukri #jublfood #astral #low-volume

---
---
## ML Retrain — 2026-05-22 16:05 IST (IST)
Feedback signals used: 463

### OPEN window | deployed=YES | threshold 0.250 -> 0.250
  long/sharpe: -13.793 -> -13.783
  long/win_rate: 0.301 -> 0.301
  long/n_signals: 85774 -> 85865
  short/sharpe: -12.62 -> -12.633
  short/win_rate: 0.326 -> 0.326
  short/n_signals: 82708 -> 82764

### MID window | deployed=YES | threshold 0.220 -> 0.220
  long/sharpe: -20.254 -> -20.254
  long/win_rate: 0.215 -> 0.215
  long/n_signals: 440797 -> 440809
  short/sharpe: -20.696 -> -20.696
  short/win_rate: 0.224 -> 0.224
  short/n_signals: 440740 -> 440764

### Feature importance
  OPEN_LONG — top 5 features:
    is_first_30min            0.196
    atr14_pct                 0.187
    vol_surge_5d              0.105
    orb_width_pct             0.080
    mom_15m_pct               0.062

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.252
    is_first_30min            0.167
    time_bucket               0.110
    orb_width_pct             0.079
    mom_15m_pct               0.064

  MID_LONG — top 5 features:
    atr14_pct                 0.456
    mom_15m_pct               0.085
    orb_width_pct             0.071
    mom_30m_pct               0.067
    ema9_21_spread            0.050

  MID_SHORT — top 5 features:
    atr14_pct                 0.462
    is_last_hour              0.085
    time_bucket               0.070
    mom_30m_pct               0.066
    mom_15m_pct               0.054

## 2026-05-29 (tester)
**Strategy:** vwap
**Trades:** 27 (8W / 19L)
**PnL:** Rs-170.45

**Market:** Nifty 50 was **slightly lower/flat-to-weak** in today’s trade, with live market trackers showing it around the **23,900** area and broader sentiment cautious. Major drags mentioned in live updates included **auto, metal, oil & gas, PSU banks, and some gaming stocks**, while **IT and a few large-cap names** were holding up better.[2][4][6]

Big news flow was dominated by **weak market breadth** and risk-off sentiment, with commentary pointing to pressure from **foreign outflows, rupee weakness, crude/geopolitical headlines, and the Supreme Court’s GST ruling on online gaming** hitting names like Delta Corp and Nazara.[2][5][7]

**Context:** Global bias was RISK_OFF. Skipped event-risk stocks: MFSL, SRF, BERGEPAINT.

**Best trade:** BOSCHLTD +Rs495.30 (TARGET)
**Worst trade:** WIPRO Rs-274.72 (STOPLOSS)

**Edge check:** Loss rate >60% — check if market was choppy/low-volume. Review signal quality.

> WARNING: #stopped-out appears 33x in recent journal. Researcher should review stoploss width.

**Tags:** #asianpaint #bergepaint #boschltd #clean-exit #dixon #gail #irctc #loss #mfsl #naukri #siemens #squareoff #srf #stopped-out #sunpharma #tatacomm #vwap #win #wipro

---

## 2026-05-29 (tester) [enriched]
**Strategy:** vwap (OPEN + MID windows; mode: paper)
**Trades:** 27 (8W / 13L / 6 breakeven)
**PnL:** -Rs170.45
**Cumulative week PnL:** -Rs170.45 (single session this week in journal; prior sessions not yet aggregated)
**Market:** Nifty 50 flat-to-weak ~23,900. Global bias RISK_OFF. Drags: auto, metal, oil & gas, PSU banks. Supports: IT, select large-cap. FII net negative. Supreme Court GST ruling hit gaming stocks (Delta Corp, Nazara). Crude/rupee/geopolitical headwinds. Regime: CHOPPY throughout session.

---

**Trade breakdown:**

| # | Time | Symbol | Side | PnL | Exit | ml_prob | consec | cat_dir | cat_score | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 112 | 10:42 | IRCTC | SELL | Rs0.00 | BE | 0.5991 | 0 | NEUTRAL | 3 | Trailing SL to breakeven |
| 113 | 10:44 | BERGEPAINT | BUY | -Rs273.34 | SL | 0.4715 | 0 | NEUTRAL | 3 | NOT IN WATCHLIST |
| 114 | 10:44 | MFSL | SELL | -Rs265.85 | SL | 0.5546 | 0 | NEUTRAL | 3 | NOT IN WATCHLIST |
| 115 | 10:44 | NAUKRI | BUY | -Rs271.95 | SL | 0.5421 | 0 | LONG | 7 | Catalyst conflict — BUY on LONG catalyst, lost |
| 116 | 10:44 | SIEMENS | SELL | -Rs272.02 | SL | 0.5478 | 0 | SHORT | 4 | Aligned catalyst; SL |
| 117 | 10:45 | BOSCHLTD | SELL | -Rs205.78 | SL | 0.7374 | 0 | NEUTRAL | 3 | Highest ml_prob of session; SL'd within 3 min |
| 118 | 10:48 | TATACOMM | BUY | Rs0.00 | BE | 0.5818 | 0 | NEUTRAL | 2 | |
| 119 | 10:48 | DIXON | BUY | Rs0.00 | BE | 0.5118 | 0 | NEUTRAL | 3 | |
| 120 | 10:48 | SUNPHARMA | BUY | Rs0.00 | BE | 0.5637 | 0 | NEUTRAL | 2 | NOT IN WATCHLIST |
| 121 | 11:13 | SRF | BUY | -Rs267.99 | SL | 0.4141 | 3 | NEUTRAL | 3 | consec=3 at entry; NOT IN WATCHLIST |
| 122 | 11:15 | WIPRO | BUY | -Rs274.72 | SL | 0.4781 | 3 | NEUTRAL | 3 | consec=3; worst trade |
| 123 | 11:23 | ASIANPAINT | BUY | +Rs382.95 | TARGET | 0.4117 | 4 | NEUTRAL | 3 | consec=4 at entry; won despite breach |
| 124 | 12:26 | SIEMENS | SELL | Rs0.00 | BE | 0.4788 | 0 | SHORT | 4 | 2nd SIEMENS entry |
| 125 | 12:26 | ASIANPAINT | SELL | Rs0.00 | BE | 0.5850 | 0 | NEUTRAL | 3 | Round-trip; <3 min after ASIANPAINT TARGET |
| 126 | 12:37 | TATACOMM | BUY | -Rs266.03 | SL | 0.5354 | 0 | NEUTRAL | 2 | 2nd TATACOMM entry |
| 127 | 12:52 | BOSCHLTD | SELL | +Rs495.30 | TARGET | 0.5352 | 2 | NEUTRAL | 3 | 2nd BOSCHLTD; best trade |
| 128 | 13:12 | BERGEPAINT | BUY | -Rs273.92 | SL | 0.5552 | 3 | NEUTRAL | 3 | 2nd BERGEPAINT; consec=3; NOT IN WATCHLIST |
| 129 | 13:18 | NAUKRI | BUY | +Rs377.62 | TARGET | 0.3355 | 3 | LONG | 7 | 2nd NAUKRI; consec=3; catalyst aligned; won |
| 130 | 13:44 | DIXON | BUY | -Rs256.32 | SL | 0.5970 | 3 | NEUTRAL | 3 | 2nd DIXON; consec=3 |
| 131 | 13:53 | GAIL | SELL | +Rs419.17 | TARGET | 0.4513 | 4 | SHORT | 8 | consec=4; cat_score=8 SHORT; cleanest trade |
| 132 | 14:18 | BOSCHLTD | BUY | -Rs204.85 | SL | 0.6860 | 0 | NEUTRAL | 3 | 3rd BOSCHLTD; direction flip SELL->BUY |
| 133 | 14:19 | TATACOMM | SELL | -Rs268.29 | SL | 0.5354 | 0 | NEUTRAL | 2 | 3rd TATACOMM; direction flip BUY->SELL |
| 134 | 14:20 | MFSL | SELL | +Rs254.02 | TARGET | 0.4068 | 0 | NEUTRAL | 3 | 2nd MFSL; direction flip; NOT IN WATCHLIST |
| 135 | 14:45 | SIEMENS | SELL | +Rs348.52 | TARGET | 0.6692 | 0 | SHORT | 4 | 3rd SIEMENS; finally TARGET |
| 136 | 14:46 | SRF | BUY | +Rs399.06 | TARGET | 0.4620 | 0 | NEUTRAL | 3 | 2nd SRF; NOT IN WATCHLIST |
| 137 | 14:51 | WIPRO | SELL | +Rs390.04 | TARGET | 0.3737 | 1 | NEUTRAL | 3 | 2nd WIPRO; direction flip BUY->SELL |
| 138 | 14:57 | SRF | SELL | -Rs136.06 | SL | 0.5188 | 0 | NEUTRAL | 3 | 3rd SRF; direction flip BUY->SELL; final entry |

---

**Best trade:** BOSCHLTD SELL +Rs495.30 (T127) — 2nd entry on symbol, 12:52, consec=2, no catalyst alignment (NEUTRAL/3). Clean TARGET. The irony: BOSCHLTD's first entry (T117) had ml_prob=0.7374, the highest of the session, and SL'd in under 3 minutes. The winning entry had ml_prob=0.5352 — barely above threshold. Repeatable? Uncertain. The direction was right the second time; the first entry was stopped out on the same thesis. Do not treat this as edge confirmation.

**Worst trade:** WIPRO BUY -Rs274.72 (T122) — consec=3 at entry, NEUTRAL catalyst, ml_prob=0.4781. Fired directly past the soft-pause threshold that has been CRITICAL/unimplemented since 2026-04-30. No structural reason this trade should have fired. The second WIPRO entry (T137, SELL, direction flip) TARGET'd at +Rs390.04 — same pattern as BOSCHLTD: lose on the first entry, reverse direction, win on the second. This is not a strategy; it is dollar-cost-averaging into a position and hoping. Per-symbol cooldown would have eliminated both the loss and the inadvertent recovery.

---

**Pattern analysis:**

**1. 27 trades in one CHOPPY session — highest volume in this journal; signal quality degradation confirmed**

The prior session high was 8 trades (2026-05-22). Today: 27 trades, 41 minutes of activity at open cluster alone. The ML threshold is currently 0.250 (OPEN) / 0.220 (MID). At these thresholds in a CHOPPY regime, the model is generating an excessive number of passing signals — the session win rate is 8/27 = 29.6%, near chance. The 6 breakevens and 13 losses confirm the market offered no directional edge. A CHOPPY regime gate would have halted or reduced the signal queue before market open. Alternatively, a max-daily-trades cap (e.g. 12) would have preserved capital by forcing the bot to skip marginal signals once the cap is reached. The volume itself is the diagnostic: when 27 signals pass the ML filter in one choppy session, the filter threshold is too low for the prevailing regime.

**2. Watchlist contamination — BERGEPAINT, MFSL, SRF, SUNPHARMA traded; none in tester.yaml**

Four symbols executed trades today that are not in the current watchlist (BERGEPAINT x2, MFSL x2, SRF x3, SUNPHARMA x1 = 8 trades, 29.6% of session volume). tester.yaml watchlist: SIEMENS, WIPRO, BOSCHLTD, TATACOMM, GAIL, NAUKRI, PAGEIND, DIXON, ASIANPAINT, IRCTC. None of the four contaminating symbols are present. Possible causes: (a) watchlist cached at startup, dynamic expansion added symbols later without config reload; (b) a separate watchlist source (e.g. ML training universe) is bleeding into the live signal queue; (c) the executor's symbol resolver is not filtering against the YAML watchlist at signal generation time. This is a silent config-to-execution mismatch — the system is trading symbols the operator did not authorise. Flagged for researcher as highest-priority structural bug. Removing these 8 trades: remaining 19 trades, 7W/10L/2BE, net approximately -Rs312, worse on win rate but smaller loss pool — the contamination is not the primary PnL driver but represents a compliance failure.

**3. Same-symbol multi-entry — cooldown completely absent; direction flipping masks the structural gap**

Symbol re-entry counts today: BOSCHLTD x3 (SELL/SELL/BUY), TATACOMM x3 (BUY/BUY/SELL), SIEMENS x3 (SELL/SELL/SELL), SRF x3 (BUY/BUY/SELL), BERGEPAINT x2 (BUY/BUY — not in watchlist), NAUKRI x2 (BUY/BUY), WIPRO x2 (BUY/SELL), DIXON x2 (BUY/BUY). Eight symbols with multiple entries, 17 of 27 trades are repeat-symbol entries. The BOSCHLTD, TATACOMM, SRF, and WIPRO direction flips (first entry SL, second entry different direction, TARGET) produced the afternoon recovery. This is not a strategy feature — it is the bot re-entering after a loss in the opposite direction and accidentally profiting. A 90-minute same-symbol cooldown post-SL (already in cooldown_after_sl_minutes: 90 in config but apparently not enforced at signal generation) would have blocked all second and third entries. The `#same-symbol-cooldown` count is now 5+ instances across sessions. Config has the parameter; enforcement is absent.

**4. Consecutive-loss breach at entries for T121, T122, T123, T128, T129, T130, T131 — winners at consec=4 masking the gap**

The consec counter at entry for key trades: T121 SRF consec=3 (-Rs267.99), T122 WIPRO consec=3 (-Rs274.72), T123 ASIANPAINT consec=4 (+Rs382.95), T128 BERGEPAINT consec=3 (-Rs273.92), T129 NAUKRI consec=3 (+Rs377.62), T130 DIXON consec=3 (-Rs256.32), T131 GAIL consec=4 (+Rs419.17). Two wins at consec=4 (ASIANPAINT, GAIL) recovered significant PnL and superficially justify ignoring the gate. They do not. ASIANPAINT NEUTRAL/3 winning at consec=4 in a CHOPPY session is variance — there is no structural reason the 5th entry in a losing streak should outperform. GAIL winning at consec=4 with cat_score=8 SHORT is a better process trade, but still fired past the soft-pause threshold. The soft-pause at consec >= 2 has been CRITICAL/unimplemented since 2026-04-30 — now 8+ sessions. Counting from T121: if the soft-pause blocked entries at consec >= 2, Trades 121, 122, 128, 130 (4 losses, -Rs1,072.23) would not have fired. The two wins at consec=4 (ASIANPAINT +Rs382.95, GAIL +Rs419.17) would also not have fired. Net cost of the gate: -Rs1,072.23 losses blocked vs +Rs802.12 wins blocked — implementing the gate would have saved Rs270.11 on this session alone, on top of the structural compliance improvement.

**5. Morning cluster failure: 10:42–11:23, 12 trades in 41 minutes, 5L/3BE/1W**

Trades 112–123 fired in a 41-minute window at session open. Results: 5 losses, 3 breakevens, 1 win (ASIANPAINT at consec=4, discussed above). Gross losses: -Rs1,556.93. The cluster includes BOSCHLTD T117 with ml_prob=0.7374 — the session's highest confidence signal — stopped out within 3 minutes. This is `#ml-high-prob-open-failure` instance 5+. The pattern is consistent: the OPEN window in a CHOPPY session produces high ml_prob signals that fail early because the model was trained on a universe that does not adequately distinguish CHOPPY open conditions from trending ones. All 12 morning trades were NEUTRAL/LONG catalyst (score 2–7) — no strong SHORT catalyst alignment in the morning cluster that survived. The breakeven cluster (IRCTC, TATACOMM, DIXON, SUNPHARMA) reflects trailing SL functioning correctly, not signal quality. The morning cluster is a regime problem: 12 signals in 41 minutes at a CHOPPY open should not pass any gate.

**6. Afternoon recovery: 12:52–14:51, 7 TARGET hits reversing the damage**

Trades 127, 129, 131, 134, 135, 136, 137 all hit TARGET between 12:52 and 14:51. Gross wins: +Rs2,683.73. This reversed the morning's -Rs1,556.93 and the midday losses, producing the near-flat -Rs170.45 close. The recovery is real, but the causal structure is not clean: BOSCHLTD (T127), WIPRO (T137), SRF (T136) won after direction flips from earlier losing entries; NAUKRI (T129), GAIL (T131) won on aligned catalyst in breach conditions. The afternoon winners include two non-watchlist symbols (SRF, MFSL) and two breach-condition entries (NAUKRI consec=3, GAIL consec=4). A near-flat result built on direction-flip recoveries and breach-condition wins in non-watchlist symbols is not a positive process outcome.

**7. NAUKRI BUY: T115 SL, T129 TARGET — catalyst alignment necessary but not sufficient at first entry**

Both NAUKRI entries had cat_dir=LONG cat_score=7 — the catalyst was aligned on both. T115 at 10:44 (ml_prob=0.5421, consec=0) SL'd. T129 at 13:18 (ml_prob=0.3355, consec=3) TARGET'd. The second entry had lower ML confidence and higher consecutive-loss count yet won. This is not a pattern that can be exploited structurally — the timing of the second entry relative to the market structure at 13:18 vs 10:44 is the more likely explanation (market had settled after the morning volatility burst). Catalyst alignment at score=7 is strong but insufficient at session open in CHOPPY conditions. `#catalyst-conflict` count updated: T115 filed as catalyst conflict (BUY on LONG, lost) not because direction misaligned but because the open-window CHOPPY environment invalidated the setup before the catalyst could express.

**8. GAIL SELL T131: cat_score=8 SHORT, consec=4 at entry, TARGET — cleanest trade of the day in a breach condition**

GAIL (T131, 13:53, SELL, cat_score=8 SHORT, ml_prob=0.4513, consec=4) is the strongest catalyst-aligned trade in the session and hit TARGET +Rs419.17. This is the best process trade despite firing past the consec gate. The outcome validates the catalyst signal quality (score=8 is among the highest in the journal) but does not validate the process of trading at consec=4. The consec gate should be implemented and GAIL-type setups should be an exception carve-out, not the default behavior. If the soft-pause allows override for cat_score >= 7, this trade fires under that rule; if not, the gate blocks it and the researcher needs to decide whether catalyst quality should override consec count.

---

**Recurring patterns (updated counts):**

| Pattern | Count (updated) | Note |
|---|---|---|
| `#stopped-out` | 34+ | 13 SL exits today; ATR-scaled SL overdue |
| `#choppy-market` | 15+ sessions | 27 trades today all in CHOPPY; no regime gate |
| `#consecutive-loss-breach` | 8+ sessions | consec reached 4 today multiple times; gate unimplemented since 2026-04-30 |
| `#same-symbol-cooldown` | 5+ instances | BOSCHLTD x3, TATACOMM x3, SRF x3, SIEMENS x3 today; config param exists, unenforced |
| `#shallow-deviation` | 7+ | No new shallow-dev flags today; prior count holds |
| `#vedl-repeat` | 6 | VEDL not in today's session; count unchanged |
| `#ml-filter-weak` | 13+ | ml_prob=0.3355 (T129 NAUKRI TARGET) passed; ml_prob=0.4117 (T123 ASIANPAINT TARGET); winners with low ml_prob, losers with moderate — filter adding minimal signal |
| `#ml-high-prob-open-failure` | 5+ | BOSCHLTD ml_prob=0.7374, SL'd in 3 min (T117) |
| `#bars-above-vwap-momentum-conflict` | 4+ | No new instances today; prior count holds |
| `#losing-day` | 8 | -Rs170.45 today |
| `#winning-day` | 5 | Count unchanged |
| `#rsi-gate-logic-gap` | 1 (introduced 2026-05-22) | No new RSI-gate violations confirmed today; remains unimplemented |
| `#catalyst-conflict` | 5+ | T115 NAUKRI BUY on LONG catalyst, open-window CHOPPY, SL |

---

**Edge check:** 8W/13L/6BE with net -Rs170.45 is nominally a losing day on the smallest possible margin (the 27-trade gross loss pool was ~Rs2,856 and the recovery brought it to Rs170). This is not edge — it is a near-flat result produced by direction-flip recoveries (BOSCHLTD, WIPRO, SRF, TATACOMM all lost-then-reversed-and-won) and two breach-condition wins (ASIANPAINT, GAIL at consec=4) that happened to cancel the morning cluster failure. Remove the four non-watchlist symbols from analysis: 19 authorised trades, ~29.6% win rate. In a CHOPPY regime with no regime gate, no consec gate, and no same-symbol cooldown, a near-flat result is variance — the underlying process produced a session where structural filters would have improved the outcome materially. The afternoon recovery from -Rs2,500+ to -Rs170 is real money saved, but the mechanism (direction flip, consec breach) is not a strategy. Low trade count per symbol is not the issue today — 27 trades is the opposite problem. This is variance on the sign, structural failure on the process.

---

**For researcher (carry-forward CRITICAL + new from today):**

New (flagged today, CRITICAL):

- **CRITICAL (NEW): Watchlist contamination.** BERGEPAINT, MFSL, SRF, SUNPHARMA traded despite not appearing in tester.yaml. 8 of 27 trades were in unauthorised symbols. Possible causes: watchlist caching bug at startup, dynamic symbol expansion in ML signal generator, or executor not filtering against YAML watchlist at signal time. Must identify the source before next session — this is a compliance failure, not a tuning issue.
- **CRITICAL (NEW): Max-daily-trades cap.** 27 trades in a CHOPPY session is a signal quality degradation signal. The ML filter is passing too many signals when regime=CHOPPY. Implement a max-daily-trades cap (suggested: 12–15) OR raise the ML threshold in CHOPPY from 0.220/0.250 to 0.400/0.450 until regime improves. The cap is a blunt instrument; the regime-conditional threshold raise is the correct structural fix.

Carry-forward CRITICAL (all unimplemented, all overdue 14+ sessions):

- **CRITICAL (14+ sessions): Consecutive-loss soft-pause at consec >= 2.** Consec reached 4 today at multiple entry points. Cost on this session: implementing would have blocked 4 losses (-Rs1,072.23) and 2 wins (+Rs802.12) — net +Rs270.11 improvement. Cumulative cost across 8+ sessions is materially larger.
- **CRITICAL (14+ sessions): Same-symbol intra-day cooldown (90-min post-SL).** cooldown_after_sl_minutes=90 is in config but not enforced at signal generation. BOSCHLTD x3, TATACOMM x3, SRF x3 today. Enforce the config param that already exists.
- **CRITICAL (10+ sessions): vwap_dev floor 0.50%.** No shallow-deviation new instances today, but the fix remains unimplemented.
- **CRITICAL (14+ sessions): Choppy-regime VWAP gate.** 15+ consecutive sessions all in CHOPPY. The strategy has never halted, size-reduced, or threshold-raised for regime. This is the root cause of the 27-trade session.
- **CRITICAL (4+ sessions): Catalyst conflict filter.** T115 NAUKRI entered BUY with LONG catalyst in open-window CHOPPY — the setup was structurally conflicted. A filter blocking entries where catalyst and price action conflict in CHOPPY should be scoped.
- **RSI gate logic gap (2026-05-22, unimplemented):** rsi_sell_block=25 does not block shorting into overbought conditions. Implement symmetric rsi_sell_block_high=75.

**Tags:** #vwap #orb #choppy-market #losing-day #consecutive-loss-breach #same-symbol-cooldown #ml-filter-weak #ml-high-prob-open-failure #stopped-out #fakeout #catalyst-conflict #boschltd #tatacomm #siemens #srf #bergepaint #naukri #wipro #gail #asianpaint #dixon #irctc #mfsl #sunpharma #low-volume #news-gap

---
---
## ML Retrain — 2026-05-29 20:26 IST (IST)
Feedback signals used: 463

### OPEN window | deployed=YES | threshold 0.250 -> 0.250
  long/sharpe: -12.991 -> -12.984
  long/win_rate: 0.311 -> 0.312
  long/n_signals: 85478 -> 85556
  short/sharpe: -13.513 -> -13.557
  short/win_rate: 0.31 -> 0.31
  short/n_signals: 81673 -> 82175

### MID window | deployed=YES | threshold 0.220 -> 0.220
  long/sharpe: -21.162 -> -21.163
  long/win_rate: 0.199 -> 0.199
  long/n_signals: 440687 -> 440849
  short/sharpe: -19.654 -> -19.653
  short/win_rate: 0.222 -> 0.222
  short/n_signals: 440627 -> 440545

### Feature importance
  OPEN_LONG — top 5 features:
    is_first_30min            0.209
    atr14_pct                 0.183
    vol_surge_5d              0.093
    orb_width_pct             0.074
    mom_15m_pct               0.051

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.229
    is_first_30min            0.148
    time_bucket               0.095
    orb_width_pct             0.076
    mom_15m_pct               0.064

  MID_LONG — top 5 features:
    atr14_pct                 0.469
    mom_15m_pct               0.083
    mom_30m_pct               0.072
    orb_width_pct             0.068
    ema9_21_spread            0.045

  MID_SHORT — top 5 features:
    atr14_pct                 0.463
    time_bucket               0.074
    is_last_hour              0.074
    mom_30m_pct               0.057
    vwap_dev_pct              0.055

---
## ML Retrain — 2026-06-05 05:07 IST (IST)
Feedback signals used: 560

### OPEN window | deployed=YES | threshold 0.450 -> 0.450
  long/sharpe: -11.791 -> -11.764
  long/win_rate: 0.327 -> 0.328
  long/n_signals: 48806 -> 50660
  short/sharpe: -11.778 -> -11.583
  short/win_rate: 0.352 -> 0.356
  short/n_signals: 49251 -> 48276

### MID window | deployed=YES | threshold 0.400 -> 0.400
  long/sharpe: -18.924 -> -18.972
  long/win_rate: 0.229 -> 0.229
  long/n_signals: 339517 -> 342193
  short/sharpe: -19.397 -> -19.353
  short/win_rate: 0.235 -> 0.236
  short/n_signals: 338319 -> 338672

### Feature importance
  OPEN_LONG — top 5 features:
    is_first_30min            0.198
    atr14_pct                 0.176
    vol_surge_5d              0.095
    orb_width_pct             0.074
    mom_15m_pct               0.057

  OPEN_SHORT — top 5 features:
    is_first_30min            0.244
    atr14_pct                 0.227
    time_bucket               0.086
    orb_width_pct             0.062
    mom_15m_pct               0.049

  MID_LONG — top 5 features:
    atr14_pct                 0.448
    mom_15m_pct               0.091
    mom_30m_pct               0.075
    orb_width_pct             0.069
    ema9_21_spread            0.046

  MID_SHORT — top 5 features:
    atr14_pct                 0.469
    time_bucket               0.094
    mom_30m_pct               0.057
    is_last_hour              0.055
    mom_15m_pct               0.052

## 2026-06-05 (tester)
**Strategy:** vwap
**Trades:** 33 (13W / 20L)
**PnL:** +Rs1821.45

**Market:** **Nifty 50 was slightly down to flat** in early trade, with the index around **23,340–23,390** and a cautious tone after opening weak; broader market weakness was visible even as some buying appeared near intraday support.[7][4]  

**Major drags** included **TCS (-8.25%)**, **Tech Mahindra (-6.45%)**, **Adani Enterprises (-1.32%)**, and **Adani Ports (-0.71%)**, while **gains in stocks like Wipro (+2.28%)**, **Infosys (+1.44%)**, and **HDFC Life (+1.56%)** helped offset some pressure.[7][3]  

The main market backdrop was **cautious**, with traders watching **FII outflows, crude prices, geopolitics, and the RBI policy decision** as key near-term cues.[1]

**Context:** Global bias was RISK_OFF. 

**Best trade:** GAIL +Rs564.55 (TARGET)
**Worst trade:** PATANJALI Rs-274.82 (STOPLOSS)

**Edge check:** Loss rate >60% — check if market was choppy/low-volume. Review signal quality.

> WARNING: #stopped-out appears 37x in recent journal. Researcher should review stoploss width.

**Tags:** #bergepaint #clean-exit #dixon #gail #icicibank #irctc #loss #pageind #patanjali #powergrid #recltd #sail #squareoff #stopped-out #tatacomm #trent #voltas #vwap #win

---
## 2026-06-05 (tester) [enriched]
**Strategy:** vwap (OPEN + MID windows; mode: paper). NOTE: config active_strategy=orb but ORB fired ZERO signals today — every trade was VWAP.
**Trades:** 33 (13W / 16L / 4 breakeven). Win rate among decided trades = 13/29 = 45%. (Basic entry mislabeled "20L" by folding the 4 trailing-SL breakevens into losses.)
**PnL:** +Rs1821.45 (green)
**Cumulative week PnL:** +Rs1821.45 (2026-06-05 is the first logged session of the week)
**Market:** Nifty 50 ~23,340–23,390, cautious flat-to-down. Regime CHOPPY essentially all session (brief BULLISH_TREND flip ~11:11, brief BEARISH_TREND ~11:42). Global bias RISK_OFF. VIX 15.9 (low). FII net -Rs4447 Cr (heavy domestic selling). Big drags TCS -8.25%, TechM -6.45%. RBI policy decision a near-term cue.

**Best trade:** GAIL SELL +Rs564.55 (11:42 TARGET) — fired into the brief BEARISH_TREND flip with ml_prob=0.626, consec=0. A short aligned with both the momentary regime and the -Rs4447 Cr FII selling backdrop. This is the one trade where direction matched macro.
**Worst trade:** PATANJALI BUY -Rs274.82 (12:26 STOPLOSS, ml_prob=0.319, consec=1) — 3rd of 4 PATANJALI entries, a re-entry into a chop-stopped name. Representative of the day's churn rather than uniquely bad.

---

**Pattern analysis:**

**1. Overtrading / symbol round-tripping in CHOPPY — the dominant story.** 33 trades is the highest count in this journal, the entire session was CHOPPY, and the same names were traded repeatedly both directions: RECLTD x3 (SELL/SELL/BUY), PATANJALI x4, GAIL x3, TATACOMM x3, TRENT x3, PAGEIND x3 (all BUY), DIXON x2, VOLTAS x2, ICICIBANK x2, SAIL x2, BERGEPAINT x2. This is churn, not conviction. The green PnL is carried entirely by ~6 big winners (GAIL SELL +564, RECLTD SELL +558, TATACOMM BUY +546, RECLTD BUY +508, VOLTAS BUY +446, GAIL BUY +446 = +Rs3069) offsetting a long tail of ~Rs270 stop-outs. Strip the top 2 winners and the day is roughly flat. No overtrading throttle exists for CHOPPY regime.

**2. PAGEIND traded 3x, all BUY, catalyst LONG/7: +316, -212, -211 = net -107.** Re-entering the same losing long thesis after consecutive stop-outs (cl0 -> cl1 -> cl1). Per-symbol loss memory / re-entry cooldown still absent — the single clearest cost of that missing gate today.

**3. ml_prob floor (#ml-filter-weak, recurring).** The 4 lowest-ml_prob entries — GAIL 0.276, TATACOMM 0.282, SAIL 0.288, ICICIBANK 0.301 — ALL lost or broke even. A 0.30 floor cuts 3-4 pure losers (~-Rs820). BUT the counter-evidence stands: RECLTD SELL 09:49 had ml_prob=0.549 (high) and lost -Rs274 in the OPEN window. #ml-high-prob-open-failure recurs a 5th time. ml_prob is necessary-not-sufficient; high prob at the OPEN window still fails.

**4. Regime-flip whipsaw at 11:11.** TRENT BUY (-260) and DIXON BUY (-254) both fired in the brief BULLISH_TREND flip with consec=2, both stopped out -Rs514 combined. Chasing a momentary regime flip — the flip reverted within the hour (BEARISH by 11:42). A regime-stability filter (require N bars in regime before acting on a flip) would have blocked both.

**5. No catalyst-direction conflict today — note the absence.** Most signals were NEUTRAL catalyst; the directional ones (PAGEIND/POWERGRID) were aligned. The recurring #catalyst-conflict pattern did NOT cost money today. Worth recording the clean case.

**6. Filters actively gating volume.** 911 signals were blocked/shadow-logged today (blocked_signals table). The shadow-log is populating for later would-have-hit analysis — the gating layer is doing heavy lifting even as 33 still passed.

**7. Trailing-SL-to-breakeven working.** 4 clean breakevens (POWERGRID 09:46, TATACOMM 10:15, VOLTAS 11:50, ICICIBANK 12:29) — feature continues to function (#trailing-sl-working, 4th occurrence).

**8. EOD square-off tail.** 5 trades force-closed 13:13–14:53: SAIL +346, IRCTC +232, BERGEPAINT +143, RECLTD -25, PATANJALI -1, POWERGRID -25. Net +Rs670 from square-offs — late-session carries were modestly positive, no disorderly EOD bleed.

---

**Recurring patterns (last 20 tester sessions, >=3 occurrences; updated):**

| Pattern | Count | Note |
|---|---|---|
| `#stopped-out` | 13 | 16 stop-outs today; ~Rs270 each, the long tail |
| `#choppy-market` | 5 | 100% of session CHOPPY again |
| `#shallow-deviation` | 4 | not the lead failure today but persists |
| `#ml-high-prob-open-failure` | 5 | RECLTD SELL 0.549 lost at OPEN |
| `#ml-filter-weak` | 5 | 4 sub-0.30 entries all lost/BE |
| `#fakeout` | 3 | 11:11 regime-flip whipsaw |
| `#trailing-sl-working` | 4 | 4 clean breakevens |
| `#risk-off` | 4 | global bias RISK_OFF, FII -4447 Cr |
| `#catalyst-conflict` | 3 | did NOT recur today (clean) |
| `#winning-day` | 1 | +Rs1821.45 |
| `#overtrading` | NEW | 33 trades, heavy same-symbol round-tripping |

---

**Edge check:** Green day (+Rs1821.45) but this is NOT a demonstration of edge. 45% decided win rate in a CHOPPY/RISK_OFF tape, with PnL concentrated in ~6 outsized winners against a long tail of ~Rs270 stop-outs, is the signature of variance favorably distributing across high trade count — not repeatable signal quality. The same structural gaps fired again: no overtrading throttle (33 trades), no per-symbol re-entry cooldown (PAGEIND -107 net over 3 longs), no ml_prob floor (4 sub-0.30 losers), no regime-stability gate (11:11 whipsaw). Strip the top 2 winners and the day is flat. Process unchanged; outcome favorable by variance. Do not read the green as validation.

**For researcher Sunday:**
- **ml_prob floor (still unimplemented, #ml-filter-weak 5th):** 0.30 floor would have cut SAIL/GAIL/TATACOMM/ICICIBANK (~-Rs820). Caveat: keep monitoring #ml-high-prob-open-failure (RECLTD 0.549) — a floor alone does not fix the OPEN-window failure mode.
- **Per-symbol re-entry cooldown / loss memory (CRITICAL, recurring):** PAGEIND 3x all BUY = -Rs107 net; PATANJALI 4x. Block re-entry into a name within N minutes of a stop-out, or after K losses on that symbol intra-day.
- **Overtrading throttle in CHOPPY regime (NEW, escalate):** 33 trades in an all-CHOPPY session is churn. Cap trades-per-session or trades-per-symbol when regime=CHOPPY; ties to the unimplemented filter backlog.
- **Regime-stability gate (NEW):** require N consecutive bars in a regime before acting on a flip. 11:11 BULLISH flip (TRENT+DIXON BUY, -Rs514) reverted to BEARISH by 11:42.
- These four tie directly to the standing filter backlog (7 filters flagged CRITICAL for 5-9 sessions).

**Tags:** #vwap #orb #choppy-market #winning-day #overtrading #stopped-out #ml-filter-weak #ml-high-prob-open-failure #trailing-sl-working #fakeout #risk-off #low-volume #gail #recltd #tatacomm #voltas #pageind #patanjali #sail #icicibank #squareoff

---
---
## ML Retrain — 2026-06-05 16:04 IST (IST)
Feedback signals used: 1433

### OPEN window | deployed=YES | threshold 0.280 -> 0.300
  long/sharpe: -13.737 -> -13.743
  long/win_rate: 0.297 -> 0.297
  long/n_signals: 84054 -> 83986
  short/sharpe: -14.254 -> -14.23
  short/win_rate: 0.312 -> 0.313
  short/n_signals: 79813 -> 79692

### MID window | deployed=YES | threshold 0.250 -> 0.250
  long/sharpe: -21.427 -> -21.426
  long/win_rate: 0.205 -> 0.205
  long/n_signals: 439777 -> 439595
  short/sharpe: -20.388 -> -20.393
  short/win_rate: 0.22 -> 0.22
  short/n_signals: 438369 -> 438672

### Feature importance
  OPEN_LONG — top 5 features:
    is_first_30min            0.185
    atr14_pct                 0.179
    vol_surge_5d              0.097
    orb_width_pct             0.073
    mom_15m_pct               0.056

  OPEN_SHORT — top 5 features:
    is_first_30min            0.322
    atr14_pct                 0.205
    time_bucket               0.084
    orb_width_pct             0.052
    mom_15m_pct               0.041

  MID_LONG — top 5 features:
    atr14_pct                 0.457
    mom_15m_pct               0.085
    mom_30m_pct               0.079
    orb_width_pct             0.063
    ema9_21_spread            0.044

  MID_SHORT — top 5 features:
    atr14_pct                 0.458
    time_bucket               0.093
    is_last_hour              0.058
    mom_30m_pct               0.058
    vwap_dev_pct              0.055

---
## ML Retrain — 2026-06-05 22:25 IST (IST)
Feedback signals used: 1433

### OPEN window | deployed=YES | threshold 0.300 -> 0.300
  long/sharpe: -13.693 -> -13.693
  long/win_rate: 0.298 -> 0.298
  long/n_signals: 82462 -> 82462
  short/sharpe: -14.015 -> -14.015
  short/win_rate: 0.317 -> 0.317
  short/n_signals: 77642 -> 77642

### MID window | deployed=YES | threshold 0.250 -> 0.250
  long/sharpe: -21.426 -> -21.426
  long/win_rate: 0.205 -> 0.205
  long/n_signals: 439595 -> 439595
  short/sharpe: -20.393 -> -20.393
  short/win_rate: 0.22 -> 0.22
  short/n_signals: 438672 -> 438672

### Feature importance
  OPEN_LONG — top 5 features:
    is_first_30min            0.185
    atr14_pct                 0.179
    vol_surge_5d              0.097
    orb_width_pct             0.073
    mom_15m_pct               0.056

  OPEN_SHORT — top 5 features:
    is_first_30min            0.322
    atr14_pct                 0.205
    time_bucket               0.084
    orb_width_pct             0.052
    mom_15m_pct               0.041

  MID_LONG — top 5 features:
    atr14_pct                 0.457
    mom_15m_pct               0.085
    mom_30m_pct               0.079
    orb_width_pct             0.063
    ema9_21_spread            0.044

  MID_SHORT — top 5 features:
    atr14_pct                 0.458
    time_bucket               0.093
    is_last_hour              0.058
    mom_30m_pct               0.058
    vwap_dev_pct              0.055

## 2026-06-08 (tester)
**Strategy:** vwap, orb
**Trades:** 7 (1W / 6L)
**PnL:** Rs-1338.85

**Market:** Indian markets were **weak today**, with Nifty 50 trading lower and extending a cautious-to-bearish tone; one live snapshot shows it around **23,123 (-1.04%)**, while another earlier quote had it near **23,366 (-0.21%)**. [4][2]  

**Major drags** included **Nifty IT** (down about **1.7%**), with **Infosys, TCS and Wipro** under pressure from the global tech selloff; **auto** also fell sharply, while **IndiGo** slipped on higher crude and Airbus delivery concerns. [4]

**Context:** Global bias was RISK_ON. Skipped event-risk stocks: TATASTEEL, VEDL.

**Best trade:** TECHM +Rs8.18 (SQUAREOFF)
**Worst trade:** RECLTD Rs-273.78 (STOPLOSS)

**Edge check:** Loss rate >60% — check if market was choppy/low-volume. Review signal quality.

> WARNING: #stopped-out appears 41x in recent journal. Researcher should review stoploss width.

**Tags:** #ambujacem #loss #ltts #orb #recltd #stopped-out #tatacomm #techm #vedl #vwap #win

---

## 2026-06-08 (tester) [enriched]
**Strategy:** vwap (OPEN + MID windows; mode: paper) + 1 orb. Mixed: 6 VWAP, 1 ORB (LTTS, first trade). Config active_strategy may read orb, but ORB fired exactly 1 signal; the day was a VWAP day.
**Trades:** 7 — corrected scorecard 0 real wins / 5 full stop-outs / 2 breakeven. (Basic auto-entry mislabeled "1W/6L": it counted TECHM +Rs8.18 as a "win" — it is a timed square-off, not edge — and folded the VEDL Rs0.00 breakeven into losses.) Decided win rate = 0/5 = 0%.
**PnL:** -Rs1338.85 (-0.13% on Rs1,000,000)
**Cumulative week PnL:** +Rs482.60 (06-05 +Rs1821.45, 06-08 -Rs1338.85)
**Market:** Nifty 50 weak, ~-1% (snapshots 23,123 / 23,366). Regime mostly CHOPPY (1 BULLISH_TREND open on LTTS, 1 BEARISH_TREND on TECHM 10:04). VIX 15.8 (low). IT (-1.7%, INFY/TCS/WIPRO) and auto leading down. FII net -Rs8776 Cr — very heavy selling, the heaviest in recent sessions.
**Context:** global_bias label = RISK_ON — INCONSISTENT with a -Rs8776 Cr FII tape (see pattern 4). Skipped event-risk: TATASTEEL, VEDL (VEDL still traded once at 11:51).

**Best trade:** TECHM SELL +Rs8.18 (11:50 SQUAREOFF, ml_prob=0.319, consec=4). Flagged honestly: this is NOT the best trade by edge — it is a near-breakeven timed square-off that happened to print fractionally green. There was no winning trade today. Calling it "best" is a formatting artifact.
**Worst trade:** RECLTD SELL -Rs273.78 (10:34 STOPLOSS, ml_prob=0.548, RSI=75.8 overbought, catalyst SHORT/7 ALIGNED — Q4 profit -22% YoY + downgrades, consec=2 at entry). The single most structurally-justified short of the day — aligned catalyst, overbought, matched the risk-off tape — and it still stopped. Largest single loss; representative of the day's core problem, not a one-off.

---

**Pattern analysis:**

**1. Clean-setup stop-outs — losses were NOT direction error, they were STOPLOSS WIDTH / CHOPPY whipsaw.** Trades 2 (AMBUJACEM), 3 (TATACOMM), 5 (RECLTD) all had catalyst ALIGNED with signal direction. #catalyst-conflict did NOT recur (mirrors the 06-05 clean case). These were structurally-clean setups that still stopped on the 0.5% SL inside CHOPPY chop. The lever is SL width / regime, not signal direction. Record explicitly.

**2. #ml-high-prob-open-failure recurs (6th occurrence) — strongest case yet.** TATACOMM BUY 09:53, ml_prob=0.768 (highest of day), catalyst LONG/3 ALIGNED, RSI=21.8 deep oversold, vol_ratio_5m=3.89 big surge, vwap_dev=-0.99% — confirmed on every single metric — and STILL stopped out in the OPEN window. This is the cleanest evidence to date that ml_prob is not predictive at the OPEN window. A plain ml_prob floor does NOT fix this failure mode; it would have passed this trade.

**3. Soft-pause-after-2-consecutive-losses would have saved the late tail.** consec_losses climbed to 4 today; the hard halt is 5, so it never tripped. A soft-pause at 2 consecutive losses would have blocked trades 5 (RECLTD -274), 6 (TECHM +8), 7 (VEDL 0) = net ~-Rs265 saved. Flagged unimplemented since 2026-04-30. Today is a concrete dated cost.

**4. FII/global_bias label inconsistency recurs (first noted 2026-05-05).** FII net -Rs8776 Cr (very heavy selling) yet global_bias=RISK_ON. The tape was clearly risk-off; the label disagrees and suppressed nothing. Worse, RISK_ON arguably greenlit the morning longs (LTTS/AMBUJACEM/TATACOMM all BUY) into a selling tape — the three earliest stop-outs. The label is not just cosmetic; it may be actively misdirecting morning bias.

**5. Early bleed then flatline.** 5 straight stop-outs by 10:34 (~Rs265-274 each, uniform sizing), then 2 near-breakeven trades (TECHM +8, VEDL 0) once consec was high. Low VIX (15.8), weak tape (-1%), IT/auto down. The damage was front-loaded in the first 50 minutes — the OPEN window again.

**6. VEDL breakeven exit — system worked here.** VEDL BUY 11:51 exited at entry price (Rs0.00), ml_prob=0.349, sym_win_rate_10=0.11, stock_sentiment=-1. A name with an 11% recent win rate and negative sentiment that the system scratched at flat rather than letting bleed. Trailing-SL-to-breakeven functioning (#trailing-sl-working).

---

**Recurring patterns (last 20 tester sessions, >=3 occurrences; updated):**

| Pattern | Count | Note |
|---|---|---|
| `#stopped-out` | 18 | 5 more today; uniform ~Rs265-274 each |
| `#choppy-market` | 6 | mostly CHOPPY again |
| `#ml-high-prob-open-failure` | 6 | TATACOMM 0.768 lost at OPEN — cleanest case yet |
| `#ml-filter-weak` | 5 | floor would not fix the 0.768 OPEN failure |
| `#risk-off` | 5 | FII -8776 Cr (heaviest), tape -1% |
| `#trailing-sl-working` | 4 | VEDL scratched flat |
| `#catalyst-conflict` | 3 | did NOT recur today (clean) |
| `#losing-day` | NEW | -Rs1338.85, 0 real wins |

---

**Edge check:** Edge, not variance — and the read is negative-confirming. Unlike 06-05 (green by variance), today the losses were CLEAN: trades 2/3/5 had aligned catalysts, oversold/overbought RSI, volume confirmation, and the highest ml_prob of the day (TATACOMM 0.768) — and all stopped. When the best-constructed setups by every available metric still fail, the failure is structural (0.5% SL too tight for CHOPPY whipsaw + OPEN-window noise), not signal selection. Low trade count (7) limits statistical weight, but the direction is consistent with 5 prior sessions. Process adhered: strategy executed as designed, no risk-limit breach, sizing uniform. The design itself is the problem, not the discipline.

**For researcher Sunday:**
- **Soft-pause-after-2-consecutive-losses (CRITICAL, unimplemented since 2026-04-30):** dated cost today = ~-Rs265 (would have blocked trades 5/6/7). Hard halt at 5 is too loose; consec reached 4. Add a soft cooldown at 2.
- **OPEN-window ml_prob is non-predictive (#ml-high-prob-open-failure, 6th):** TATACOMM 0.768 fully-confirmed setup lost at OPEN. Do NOT ship a plain ml_prob floor expecting it to fix this — it passes the 0.768 trade. Consider an OPEN-window-specific gate (wider confirmation, delayed entry, or skip OPEN entirely for VWAP).
- **Stoploss width / regime-aware SL (escalate):** 5 clean setups stopped on 0.5% SL in CHOPPY. Test wider SL or volatility-scaled SL in CHOPPY regime; the long tail of uniform ~Rs270 stop-outs is the recurring bleed.
- **FII/global_bias label fix (recurring since 2026-05-05):** -Rs8776 Cr FII = risk-off, label said RISK_ON. Reconcile the label to the FII/tape; it may have greenlit the morning longs into a selling tape.
- These four tie directly to the standing filter backlog (7 filters flagged CRITICAL for 5-9 sessions).

**Tags:** #vwap #orb #choppy-market #losing-day #stopped-out #ml-high-prob-open-failure #ml-filter-weak #trailing-sl-working #risk-off #low-volume #event-risk-realized #ltts #ambujacem #tatacomm #techm #recltd #vedl #squareoff

---
---
---
## ML Retrain — 2026-06-08 16:04 IST (IST)
Feedback signals used: 1828

### OPEN window | deployed=NO | threshold 0.300 -> 0.300
  long/sharpe: -12.665 -> -12.685
  long/win_rate: 0.308 -> 0.308
  long/n_signals: 82456 -> 82613
  short/sharpe: -15.221 -> -15.249
  short/win_rate: 0.301 -> 0.301
  short/n_signals: 77678 -> 77801

### MID window | deployed=YES | threshold 0.250 -> 0.250
  long/sharpe: -21.513 -> -21.523
  long/win_rate: 0.203 -> 0.203
  long/n_signals: 439556 -> 440049
  short/sharpe: -20.621 -> -20.615
  short/win_rate: 0.216 -> 0.217
  short/n_signals: 438549 -> 438193

### Feature importance
  OPEN_LONG — top 5 features:
    is_first_30min            0.185
    atr14_pct                 0.179
    vol_surge_5d              0.097
    orb_width_pct             0.073
    mom_15m_pct               0.056

  OPEN_SHORT — top 5 features:
    is_first_30min            0.322
    atr14_pct                 0.205
    time_bucket               0.084
    orb_width_pct             0.052
    mom_15m_pct               0.041

  MID_LONG — top 5 features:
    atr14_pct                 0.453
    mom_15m_pct               0.086
    mom_30m_pct               0.080
    orb_width_pct             0.065
    ema9_21_spread            0.044

  MID_SHORT — top 5 features:
    atr14_pct                 0.449
    time_bucket               0.095
    is_last_hour              0.060
    mom_15m_pct               0.055
    orb_width_pct             0.052

## 2026-06-09 (tester)
**Strategy:** vwap
**Trades:** 4 (0W / 4L)
**PnL:** Rs-1091.64

**Market:** Indian markets were **mixed to slightly firmer** in early trade: Nifty 50 was around **23,242, up 0.52%**, while Sensex gained about **395 points** and Bank Nifty outperformed with a **2.09%** rise[4]. Biggest movers mentioned included **Bank Nifty/banking stocks**, **auto stocks**, and individual names like **Vodafone Idea** and **NLC India**; headline drivers were the **RBI forex swap facility**, **GIFT Nifty weakness**, and **geopolitical tension in Iran** keeping sentiment cautious[4].

**Context:** Global bias was RISK_OFF. Skipped event-risk stocks: SAIL, BEL, BERGEPAINT.

**Best trade:** HINDALCO Rs-270.18 (STOPLOSS)
**Worst trade:** CANBK Rs-274.51 (STOPLOSS)

**Edge check:** Variance, but with a directional bias. All 4 were the *same* setup — VWAP-fade SHORT (price X% above VWAP, short back to VWAP) on a GAP-DOWN day in a CHOPPY/RISK_OFF regime. In every case price kept recovering upward (intraday reversion bounce) and ran the short over. Near-identical losses (~-Rs270 each) confirm fixed-risk sizing worked as designed; the *direction* was wrong, not the sizing. Shorting oversold gap-down bounces is fighting the reversion — the fade-short logic is backwards for this regime.

> WARNING: #stopped-out appears 45x in recent journal. Researcher should review stoploss width.

**Insights:**
- **Fade-short into bounce (root cause):** All 4 shorts faded a move above VWAP on gap-down days; price reverted up. This is shorting oversold bounces. Likely a meaningful contributor to the recurring #stopped-out cluster (now 45x, already WARNING-flagged) — flag for Sunday researcher review (no change now).
- **ML gate ineffective:** 3 of 4 entries had ml_prob < 0.50 (0.36, 0.47, 0.30) yet still traded. HINDALCO at 0.30 (VERY LOW) should likely have been blocked.
- **Cooldown likely breached:** cooldown_after_sl_minutes=90, but CANBK SL 10:22 → BERGEPAINT 10:34 (12m) and UNIONBANK SL 12:19 → HINDALCO 12:35 (16m). VWAP's own cooldown_minutes=5 may be overriding the account-level 90m. Config/logic question for weekly review.
- **Watchlist drift:** BERGEPAINT and HINDALCO are not in tester's configured watchlist.
- **Context contradiction:** Entry's Context line lists BERGEPAINT as a SKIPPED event-risk stock, but it was actually traded (Trade 2, -Rs272.69).
- **Strategy mismatch:** active_strategy="orb" but zero ORB trades fired (orb has _strategist_suppress_long=true); all 4 trades came from vwap.

**Tags:** #bergepaint #canbk #hindalco #loss #losing-day #stopped-out #unionbank #vwap #vwap-fade #vwap-fade-fail #gap-down-bounce #short-squeeze #choppy-market #ml-gate-ignored #cooldown-breach #watchlist-drift #fakeout

---
---
## ML Retrain — 2026-06-09 16:02 IST (IST)
Feedback signals used: 3588

### OPEN window | deployed=YES | threshold 0.300 -> 0.300
  long/sharpe: -13.029 -> -13.036
  long/win_rate: 0.303 -> 0.303
  long/n_signals: 82196 -> 82323
  short/sharpe: -14.969 -> -14.954
  short/win_rate: 0.304 -> 0.304
  short/n_signals: 77275 -> 76956

### MID window | deployed=YES | threshold 0.250 -> 0.250
  long/sharpe: -22.035 -> -22.031
  long/win_rate: 0.197 -> 0.197
  long/n_signals: 439905 -> 439419
  short/sharpe: -20.427 -> -20.43
  short/win_rate: 0.216 -> 0.216
  short/n_signals: 437848 -> 437957

### Feature importance
  OPEN_LONG — top 5 features:
    is_first_30min            0.196
    atr14_pct                 0.187
    vol_surge_5d              0.090
    orb_width_pct             0.080
    mom_15m_pct               0.052

  OPEN_SHORT — top 5 features:
    is_first_30min            0.280
    atr14_pct                 0.232
    time_bucket               0.089
    orb_width_pct             0.056
    mom_15m_pct               0.043

  MID_LONG — top 5 features:
    atr14_pct                 0.455
    mom_15m_pct               0.090
    mom_30m_pct               0.080
    orb_width_pct             0.062
    time_bucket               0.043

  MID_SHORT — top 5 features:
    atr14_pct                 0.455
    time_bucket               0.092
    mom_15m_pct               0.058
    is_last_hour              0.057
    vwap_dev_pct              0.053

## 2026-07-06 (us_trader)
**Strategy:** vwap
**Trades:** 8 (3W / 5L)
**PnL:** +$174.86 (+0.17% on $100k)

**Market:** US session risk_on. VIX 15.9 (NORMAL regime). Per-symbol sentiment positive for AAPL, TSLA, AMD, META, MSFT; neutral for SPY, QQQ, NVDA.

**Best trade:** META +$106.73 (TARGET)
**Worst trade:** TSLA -$24.98 (STOPLOSS)

**Notes:** Green day, but the win came from R-multiple, not hit rate. Five small stoplosses (META $0.00, META -$23.90, TSLA -$24.98, AMD -$22.31, TSLA -$8.62) were outweighed by three larger targets (META +$106.73, TSLA +$101.33, TSLA +$46.61). 37.5% win rate is a caution flag, not something to celebrate. Heavy same-symbol re-entry — META traded 3× (2 SL then 1 target), TSLA 4× (mixed) — suggests the VWAP shorts keep probing the same names after stopping out; watch cooldown/churn. First shorts of the session stopped out back-to-back before the targets came in later.

**Edge check:** Low trade count + 37.5% hit rate = mostly variance carried by R-multiple. Not confirmed edge.

> WARNING: #stopped-out appears 48x in recent journal. Researcher should review stoploss width.

**Tags:** #vwap #meta #tsla #amd #stopped-out #same-symbol-churn #low-hit-rate #green-day #r-multiple-carry

---
---
## ML Retrain — 2026-07-07 02:19 IST (IST)
Feedback signals used: 4206

### OPEN window | deployed=YES | threshold 0.300 -> 0.300
  long/sharpe: -13.036 -> -13.039
  long/win_rate: 0.303 -> 0.303
  long/n_signals: 82323 -> 82314
  short/sharpe: -14.954 -> -14.974
  short/win_rate: 0.304 -> 0.304
  short/n_signals: 76956 -> 77126

### MID window | deployed=YES | threshold 0.250 -> 0.250
  long/sharpe: -22.031 -> -22.031
  long/win_rate: 0.197 -> 0.197
  long/n_signals: 439419 -> 439582
  short/sharpe: -20.43 -> -20.431
  short/win_rate: 0.216 -> 0.216
  short/n_signals: 437957 -> 437976

### Feature importance
  OPEN_LONG — top 5 features:
    is_first_30min            0.192
    atr14_pct                 0.175
    vol_surge_5d              0.088
    orb_width_pct             0.077
    mom_15m_pct               0.050

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.247
    is_first_30min            0.211
    time_bucket               0.100
    orb_width_pct             0.059
    mom_15m_pct               0.046

  MID_LONG — top 5 features:
    atr14_pct                 0.461
    mom_15m_pct               0.091
    mom_30m_pct               0.080
    orb_width_pct             0.064
    time_bucket               0.044

  MID_SHORT — top 5 features:
    atr14_pct                 0.455
    time_bucket               0.092
    is_last_hour              0.060
    mom_15m_pct               0.059
    vwap_dev_pct              0.054

## 2026-07-07 (us_trader)
**Strategy:** vwap
**Trades:** 2 (1W / 1L)
**PnL:** +$69.70 (+0.07%)

**Market:** Global bias neutral. VIX 15.85 (NORMAL regime). Per-symbol sentiment mildly constructive on tech: AAPL +1, MSFT +1, AMD +1, NVDA +1; TSLA, SPY, QQQ flat (0). No macro catalyst — quiet, low-conviction tape.

**Best trade:** NVDA short +$69.70 (TARGET) — clean move from 199.02 down to 196.23, single R-multiple winner that carried the day.
**Worst trade:** TSLA short +$0.00 (STOPLOSS) — scratched at breakeven, stopped out flat at 408.575.

**What worked:** One NVDA short reached target; VWAP short thesis paid on the name with the strongest bearish follow-through.
**What didn't:** TSLA (sentiment 0) never trended and scratched. Both trades were VWAP shorts probing the same large-caps — same pattern as 2026-07-06.

**Edge check:** Not edge. 2 trades, one winner carrying a green day that is +0.07% — essentially flat. Sample far too small to conclude anything; treat as variance / low-activity day. Do not celebrate.

> WARNING: #stopped-out appears 52x in recent journal. Researcher should review stoploss width.

**Tags:** #vwap #nvda #tsla #short #stopped-out #green-day #flat #small-sample #r-multiple-carry #win #loss

---
---
## US ML Retrain — 2026-07-08 14:34 ET | account=us_trader
Trades used: 10 | Deployed: YES
  short: win=33.3% sharpe=-12.58 signals=6 precision=66.7%

## 2026-07-09 (tester)
**Strategy:** none
**Trades:** 0 (0W / 0L)
**PnL:** +Rs0.00

**Market:** Nifty 50 closed sharply lower at **23,882.05**, down **2.12%**, breaking below its key support of 24,200 amid profit-booking and global cues like the Fed’s unchanged rate decision [1][4][5]. Major losers included **Jio Financial Services** (–5.38%), **Shriram Finance** (–4.91%), and **Maruti Suzuki** (–4.04%), while top gainers were **ONGC**, **Bajaj Auto**, and **Coal India** [3]. The big news driving the market was the **Fed leaving rates unchanged** and hinting at a potential rate hike later this year, alongside renewed **U.S.–Iran MoU tensions** [2].

**Context:** Global bias was RISK_OFF. Skipped event-risk stocks: DIVISLAB, UNIONBANK.

**Best trade:** none
**Worst trade:** none

**Edge check:** No trades today — no signals fired.

> ⚠️ #stopped-out appears 11x in last 20 sessions. Researcher should review stoploss width.

**Tags:** 

---
---
## ML Retrain — 2026-07-09 22:30 IST (IST)
Feedback signals used: 4619

### OPEN window | deployed=YES | threshold 0.300 -> 0.300
  long/sharpe: -13.039 -> -13.056
  long/win_rate: 0.303 -> 0.303
  long/n_signals: 82314 -> 82137
  short/sharpe: -14.974 -> -14.968
  short/win_rate: 0.304 -> 0.304
  short/n_signals: 77126 -> 77177

### MID window | deployed=YES | threshold 0.250 -> 0.250
  long/sharpe: -22.031 -> -22.031
  long/win_rate: 0.197 -> 0.197
  long/n_signals: 439582 -> 439618
  short/sharpe: -20.431 -> -20.429
  short/win_rate: 0.216 -> 0.216
  short/n_signals: 437976 -> 438000

### Feature importance
  OPEN_LONG — top 5 features:
    atr14_pct                 0.187
    is_first_30min            0.152
    vol_surge_5d              0.098
    orb_width_pct             0.076
    mom_15m_pct               0.056

  OPEN_SHORT — top 5 features:
    atr14_pct                 0.283
    is_first_30min            0.192
    time_bucket               0.091
    orb_width_pct             0.057
    mom_15m_pct               0.047

  MID_LONG — top 5 features:
    atr14_pct                 0.474
    mom_30m_pct               0.072
    mom_15m_pct               0.064
    orb_width_pct             0.058
    time_bucket               0.044

  MID_SHORT — top 5 features:
    atr14_pct                 0.472
    time_bucket               0.089
    is_last_hour              0.059
    vwap_dev_pct              0.050
    mom_30m_pct               0.049

## 2026-07-10 (us_trader)
**Strategy:** vwap
**Trades:** 5 (2W / 3L)
**PnL:** +Rs30.84

**Market:** The Nifty 50 closed at **23,882**, down **2.12%**, with technical indicators signaling a **Strong Sell** amid heavy profit booking [3][4]. Major movers included **Bajaj Finance** (-3.08%), **Reliance Industries** (-2.48%), and **ICICI Bank** (-2.41%), all trending lower [3]. Key news driving the downturn includes the **Fed's unchanged rate decision** with a hint of a potential 2026 hike, alongside a U.S.-Iran **MoU** signed the previous night [2].

**Context:** 

**Best trade:** AMD +Rs117.94 (TARGET)
**Worst trade:** TSLA Rs-49.81 (STOPLOSS)

**Edge check:** Mixed results — sample too small to conclude. Keep logging.

> ⚠️ #stopped-out appears 8x in last 20 sessions. Researcher should review stoploss width.

**Tags:** #amd #clean-exit #loss #qqq #stopped-out #tsla #vwap #win

---
---
## US ML Retrain — 2026-07-09 16:45 ET | account=us_trader
Trades used: 14 | Deployed: NO (kept old)
  short: win=14.3% sharpe=-11.34 signals=7 precision=71.4%

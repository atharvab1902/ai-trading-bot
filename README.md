# AI Trading Bot

---

## What is this?

This is an autonomous intraday trading bot that trades stocks on the **Indian market (NSE via Dhan)** and the **US market (NYSE/NASDAQ via Alpaca)** simultaneously.

You set it up once, start it from a browser dashboard, and it runs on its own — scanning stocks before market open, entering trades during the session, managing stop losses and targets, and shutting down cleanly at close.

**How it makes decisions:**
- A machine learning model scores every signal before a trade is placed. It learns from your own trade history over time and gets better the longer it runs.
- VWAP and ORB strategies identify entry timing — when a stock deviates from its intraday average with a recovery signal, the bot evaluates whether to trade it.
- A regime detector reads the overall market mood (trending, choppy, volatile) and adjusts position sizes accordingly.
- Every night after market close, Claude analyses the day's trades and proposes strategy improvements. Every Sunday, a three-agent pipeline (researcher → critic → risk officer) reviews the week and auto-applies safe parameter changes.

**What you see on the dashboard:**
- Live PnL for each market, updated every few seconds
- Open positions with entry price, current price, stop loss, target, and a progress bar
- Recent trade history
- Live log viewer — same logs you'd see in a terminal
- Start/stop controls for each bot

**Paper trading by default.** No real money is used until you explicitly switch to live mode after verifying results.

---

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- API keys (see step 2)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/atharvab1902/ai-trading-bot.git
cd ai-trading-bot
```

### 2. Start

```bash
docker compose up -d
```

### 3. Open the dashboard and add your keys

Go to **http://localhost:5000** → **Settings** and paste your API keys there. No need to touch any files.

| Key | Where to get it |
|---|---|
| `DHAN_CLIENT_ID` + `DHAN_ACCESS_TOKEN` | [dhanhq.co](https://dhanhq.co) → My Profile → API |
| `ALPACA_API_KEY` + `ALPACA_API_SECRET` | See instructions below |
| `TELEGRAM_BOT_TOKEN` | Telegram → @BotFather → /newbot |
| `TELEGRAM_CHAT_ID` | Telegram → @userinfobot |
| `PERPLEXITY_API_KEY` | [perplexity.ai](https://www.perplexity.ai/settings/api) |

> Leave any key blank if you don't have it — the bot runs without it (Dhan/Alpaca required for the respective bot, others optional).

### 4. Start a bot

Back on the dashboard home page, click **▶ Start Bot** for India or US. That's it.

---

### Getting your Alpaca paper trading keys

The US bot trades on Alpaca's paper trading environment — no real money, no risk.

**1. Create a free account**

Go to [https://app.alpaca.markets/signup](https://app.alpaca.markets/signup) and sign up. No credit card needed.

**2. Switch to Paper Trading**

After logging in, look at the top-left corner — there's a toggle that says **Live Trading**. Click it and switch to **Paper Trading**. Everything from here on is simulated.

**3. Get your API keys**

- Click your name / account icon (top right)
- Go to **Overview** → scroll down to **Your API Keys**
- Click **Generate New Key**
- Copy both values immediately — the secret is only shown once:
  - `ALPACA_API_KEY` → the key ID (starts with `PK...`)
  - `ALPACA_API_SECRET` → the secret key (shown once, copy it now)

Paste both into the Settings page on the dashboard.

> **Note:** Make sure you're on the Paper Trading environment when you generate the keys. Live trading keys are separate and will charge real money.

---

## Stopping

```bash
docker compose down
```

---

## Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

Docker daemon tests are skipped automatically if Docker is not running.

---

## Project structure

```
config/accounts/    — per-account settings (watchlist, capital, strategy)
executor/           — trade execution engine
ml/                 — ML model training and inference
scanner/            — premarket stock scanner
dashboard.py        — web dashboard (Flask)
scheduler.py        — market session scheduler
data/trades.db      — SQLite trade log (auto-created)
```

---

## Safety rules

- Daily loss limit: **2%** — bot halts automatically if hit
- Default mode: **paper trading** — no real money until you set `TRADING_MODE=live`
- Never set live mode without 4+ weeks of paper trading with positive expectancy

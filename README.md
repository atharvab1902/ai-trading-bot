# AI Trading Bot

Intraday trading bot for **India (Dhan/NSE)** and **US (Alpaca/NYSE)** markets.
ML model decides trades. VWAP/ORB are entry timing only.
Managed via a web dashboard — no terminal needed after setup.

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

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in your keys:

| Key | Where to get it |
|---|---|
| `DHAN_CLIENT_ID` + `DHAN_ACCESS_TOKEN` | [dhanhq.co](https://dhanhq.co) → My Profile → API |
| `ALPACA_API_KEY` + `ALPACA_API_SECRET` | [alpaca.markets](https://alpaca.markets) → Paper Trading → API Keys |
| `TELEGRAM_BOT_TOKEN` | Telegram → @BotFather → /newbot |
| `TELEGRAM_CHAT_ID` | Telegram → @userinfobot |
| `PERPLEXITY_API_KEY` | [perplexity.ai](https://www.perplexity.ai/settings/api) |

> Leave any key blank if you don't have it — the bot runs without it (Dhan/Alpaca required for the respective bot, others optional).

### 3. Start

```bash
docker compose up -d
```

### 4. Open the dashboard

Go to **http://localhost:5000** in your browser.

From there you can:
- Add / update API keys (Settings page)
- Start / stop the India or US bot
- Connect Claude Code via browser OAuth (Settings → Claude Code)
- View live PnL and recent trades

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

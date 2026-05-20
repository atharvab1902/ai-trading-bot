#!/usr/bin/env bash
# Runs Sunday 10:00 IST. Example cron: 0 10 * * 0 /path/to/trading-bot/scripts/cron_weekly.sh
set -e
cd "$(dirname "$0")/.."
ACCOUNT="${1:-tester}"
claude -p "run weekly for account=$ACCOUNT"

#!/usr/bin/env bash
# Runs 16:00 IST. Example cron: 0 16 * * 1-5 /path/to/trading-bot/scripts/cron_postmarket.sh
set -e
cd "$(dirname "$0")/.."
ACCOUNT="${1:-tester}"
claude -p "run postmarket for account=$ACCOUNT"

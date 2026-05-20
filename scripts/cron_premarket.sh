#!/usr/bin/env bash
# Runs 08:30 IST. Example cron: 30 8 * * 1-5 /path/to/trading-bot/scripts/cron_premarket.sh
set -e
cd "$(dirname "$0")/.."
ACCOUNT="${1:-tester}"
claude -p "run premarket for account=$ACCOUNT"

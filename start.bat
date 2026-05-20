@echo off
title Trading Bot — tester
cd /d D:\trading-bot
echo Starting trading bot...
echo.
echo State is auto-saved every 5 seconds.
echo Strategy state + open trades survive restarts.
echo Close this window to STOP the bot.
echo.
python scheduler.py --account tester
pause

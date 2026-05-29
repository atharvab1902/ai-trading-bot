"""Quick standalone test of Dhan WebSocket feed. Run: python scripts/test_feed.py"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from dhanhq import marketfeed

client_id    = os.environ["DHAN_CLIENT_ID"]
access_token = os.environ["DHAN_ACCESS_TOKEN"]

# INFY security ID = 1594
instruments = [(marketfeed.NSE, "1594", marketfeed.Quote)]

print(f"Connecting as client_id={client_id[:6]}...")
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

feed = marketfeed.DhanFeed(client_id, access_token, instruments, version="v2")
print("DhanFeed created, calling run_forever()...")
feed.run_forever()
print("Connected! Waiting for ticks (Ctrl+C to stop)...")

for i in range(5):
    tick = feed.get_data()
    print(f"Tick {i+1}: {tick}")

print("Done.")

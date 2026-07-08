"""Market data feeds for regime context.

Fetches:
- India VIX (from Yahoo Finance — reliable, no auth)
- FII/DII net flow (from NSE archives — free, 1-day lag)

Writes to data/market_context.json, which executor reads for signal features
and premarket reads to build the strategist context.

Usage:
    python data_feeds.py   # run standalone, writes data/market_context.json
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytz
import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent
IST = pytz.timezone("Asia/Kolkata")
load_dotenv(REPO_ROOT / ".env")
log = logging.getLogger(__name__)


def fetch_india_vix() -> float | None:
    """Fetch India VIX from Yahoo Finance. Returns float or None on failure."""
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EINDIAVIX"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            log.warning(f"VIX fetch failed: HTTP {resp.status_code}")
            return None
        data = resp.json()
        result = data.get("chart", {}).get("result", [{}])[0]
        meta = result.get("meta", {})
        vix = meta.get("regularMarketPrice") or meta.get("previousClose")
        if vix:
            log.info(f"India VIX: {vix:.2f}")
            return float(vix)
        return None
    except Exception as e:
        log.warning(f"VIX fetch error: {e}")
        return None


def fetch_fii_data() -> dict | None:
    """Fetch FII/DII cash market net activity from NSE.

    NSE publishes daily participant-wise data. We try today first, then D-1.
    Returns dict with fii_net_cr (crores), dii_net_cr, date.
    """
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.nseindia.com/",
        "Accept": "application/json",
    }
    session = requests.Session()

    # Warm up session cookie
    try:
        session.get("https://www.nseindia.com", headers=headers, timeout=8)
    except Exception:
        pass

    url = "https://www.nseindia.com/api/fiidiiTradeReact"
    try:
        resp = session.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            rows = resp.json()
            # rows is a list; find latest date with cash market data
            for row in rows:
                category = row.get("category", "").strip()
                if "FII" in category.upper():
                    # netValue is in crores directly in this endpoint
                    net_raw = str(row.get("netValue", row.get("netPurchasesSales", "0")))
                    net = float(net_raw.replace(",", ""))
                    date_str = row.get("date", "")
                    fii_net = round(net, 2)  # already in crores
                    log.info(f"FII net (cash): Rs{fii_net:+.0f} Cr on {date_str}")

                    dii_net = None
                    for r2 in rows:
                        if "DII" in r2.get("category", "").upper():
                            dii_raw = str(r2.get("netValue", r2.get("netPurchasesSales", "0")))
                            dii_net = round(float(dii_raw.replace(",", "")), 2)
                            break

                    return {
                        "fii_net_cr": fii_net,
                        "dii_net_cr": dii_net,
                        "date": date_str,
                    }
    except Exception as e:
        log.warning(f"FII NSE API error: {e}")

    # Fallback: NSE archive CSV for yesterday
    try:
        yesterday = (datetime.now(IST) - timedelta(days=1)).strftime("%d%m%Y")
        csv_url = f"https://archives.nseindia.com/content/nsccl/fao_participant_pos_{yesterday}.csv"
        r = requests.get(csv_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code == 200:
            lines = r.text.strip().split("\n")
            for line in lines:
                if "FII" in line.upper():
                    parts = line.split(",")
                    if len(parts) >= 6:
                        # Net position change as proxy for flow direction
                        net = float(parts[5].strip().replace('"', '') or "0")
                        fii_net = round(net / 1e7, 2)
                        log.info(f"FII net (F&O proxy): {fii_net:+.0f} Cr")
                        return {"fii_net_cr": fii_net, "dii_net_cr": None, "date": yesterday}
    except Exception as e:
        log.warning(f"FII archive fallback error: {e}")

    return None


def fetch_us_vix() -> float | None:
    """Fetch CBOE VIX (US) from Yahoo Finance."""
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            log.warning(f"US VIX fetch failed: HTTP {resp.status_code}")
            return None
        data = resp.json()
        result = data.get("chart", {}).get("result", [{}])[0]
        meta = result.get("meta", {})
        vix = meta.get("regularMarketPrice") or meta.get("previousClose")
        if vix:
            log.info(f"US VIX: {vix:.2f}")
            return float(vix)
        return None
    except Exception as e:
        log.warning(f"US VIX fetch error: {e}")
        return None


def load_market_context(account: str = "tester") -> dict:
    """Load previously saved market context (used by executor in hot path)."""
    path = REPO_ROOT / "data" / f"market_context_{account}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


def fetch_and_save(global_bias: str = "neutral", sentiments: dict = None,
                   account: str = "tester") -> dict:
    """Fetch VIX + FII (India) or VIX only (US), save to market_context_{account}.json."""
    ctx = load_market_context(account)

    ctx["ts"] = datetime.now(IST).isoformat()
    ctx["global_bias"] = global_bias
    ctx["sentiments"] = sentiments or {}

    vix = fetch_india_vix()
    fii = fetch_fii_data()

    if vix is not None:
        ctx["vix"] = vix
        if vix >= 20:
            ctx["vix_regime"] = "HIGH_VOLATILITY"
        elif vix <= 14:
            ctx["vix_regime"] = "LOW_VOLATILITY"
        else:
            ctx["vix_regime"] = "NORMAL"

    if fii:
        ctx["fii_net_cr"] = fii["fii_net_cr"]
        ctx["dii_net_cr"] = fii.get("dii_net_cr")
        ctx["fii_date"] = fii["date"]
        if fii["fii_net_cr"] and fii["fii_net_cr"] > 500:
            ctx["fii_bias"] = "BULLISH"
        elif fii["fii_net_cr"] and fii["fii_net_cr"] < -500:
            ctx["fii_bias"] = "BEARISH"
        else:
            ctx["fii_bias"] = "NEUTRAL"

    out_path = REPO_ROOT / "data" / f"market_context_{account}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(ctx, indent=2))
    log.info(f"market_context_{account}.json saved | VIX={vix} FII={fii}")
    return ctx


def fetch_and_save_us(global_bias: str = "neutral", sentiments: dict = None,
                      account: str = "us_trader") -> dict:
    """Fetch US VIX only (no FII/DII — not applicable for US market)."""
    ctx = load_market_context(account)

    ctx["ts"] = datetime.now(IST).isoformat()
    ctx["global_bias"] = global_bias
    ctx["sentiments"] = sentiments or {}

    vix = fetch_us_vix()
    if vix is not None:
        ctx["vix"] = vix
        # US VIX thresholds: >25 = high, <15 = low (different from India VIX)
        if vix >= 25:
            ctx["vix_regime"] = "HIGH_VOLATILITY"
        elif vix <= 15:
            ctx["vix_regime"] = "LOW_VOLATILITY"
        else:
            ctx["vix_regime"] = "NORMAL"

    out_path = REPO_ROOT / "data" / f"market_context_{account}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(ctx, indent=2))
    log.info(f"market_context_{account}.json saved | US VIX={vix}")
    return ctx


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ctx = fetch_and_save()
    print(json.dumps(ctx, indent=2))

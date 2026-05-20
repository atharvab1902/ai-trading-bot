"""Sector correlation map. Prevents multiple positions in the same sector."""

SECTORS = {
    "BANKING":  ["HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "SBIN", "HDFCBANK"],
    "IT":       ["INFY", "TCS", "WIPRO"],
    "ENERGY":   ["RELIANCE", "ONGC"],
    "INFRA":    ["LT"],
    "AUTO":     ["MARUTI", "TATAMOTORS", "M&M"],
    "PHARMA":   ["SUNPHARMA", "DRREDDY", "CIPLA"],
}

# Reverse map: symbol -> sector
_SYMBOL_TO_SECTOR = {sym: sector for sector, syms in SECTORS.items() for sym in syms}


def get_sector(symbol: str) -> str:
    return _SYMBOL_TO_SECTOR.get(symbol.upper(), "MISC")


def has_sector_conflict(symbol: str, open_positions: dict) -> tuple:
    """
    Returns (conflict: bool, reason: str).
    open_positions: {symbol: side} dict of currently open trades.
    """
    sector = get_sector(symbol)
    if sector == "MISC":
        return False, ""

    for open_sym in open_positions:
        if open_sym == symbol:
            continue
        if get_sector(open_sym) == sector:
            return True, f"{symbol} and {open_sym} are both in {sector} sector"

    return False, ""

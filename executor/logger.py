"""Centralised logging setup for the executor.

Call setup_logging() once at startup. After that, every module uses:
    import logging
    log = logging.getLogger(__name__)

Console  → INFO and above  (trades, signals, errors — human-readable)
Log file → DEBUG and above (every tick, every check — full trace)
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

import pytz
_IST = pytz.timezone("Asia/Kolkata")

REPO_ROOT = Path(__file__).parent.parent
LOG_DIR = REPO_ROOT / "logs"

CONSOLE_FMT = "[%(asctime)s] %(levelname)-5s %(message)s"
FILE_FMT    = "[%(asctime)s] %(levelname)-5s %(name)s | %(message)s"
TIME_FMT    = "%H:%M:%S"


def setup_logging(account: str) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(_IST).strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"executor_{account}_{ts}.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console — INFO only (clean, readable)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(CONSOLE_FMT, datefmt=TIME_FMT))
    root.addHandler(console)

    # File — DEBUG (every tick, every check)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(FILE_FMT, datefmt=TIME_FMT))
    root.addHandler(fh)

    log = logging.getLogger("executor")
    log.info(f"Logging started — file: {log_file}")
    return log

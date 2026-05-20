from .orb import ORB
from .vwap import VWAP
from .ema import EMA

REGISTRY = {
    "orb":  ORB,
    "vwap": VWAP,
    "ema":  EMA,
}


def get_strategy(name: str):
    if name not in REGISTRY:
        raise ValueError(f"Unknown strategy: {name}")
    return REGISTRY[name]

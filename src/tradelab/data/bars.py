"""Bar validation and synthetic data for tests/demos."""

from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED = ("open", "high", "low", "close")


def validate_bars(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"bars missing columns: {missing}")
    out = df.copy()
    # basic OHLC integrity
    bad = (
        (out["high"] < out["low"])
        | (out["high"] < out["open"])
        | (out["high"] < out["close"])
        | (out["low"] > out["open"])
        | (out["low"] > out["close"])
    )
    if bad.any():
        raise ValueError(f"{int(bad.sum())} bars fail OHLC integrity")
    return out


def synthetic_ohlc(
    n: int = 500,
    *,
    start_price: float = 100.0,
    vol: float = 0.01,
    seed: int = 42,
) -> pd.DataFrame:
    """Geometric Brownian motion OHLC for demos/tests."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0002, vol, size=n)
    close = start_price * np.cumprod(1.0 + rets)
    open_ = np.concatenate([[start_price], close[:-1]])
    noise = np.abs(rng.normal(0, vol * start_price * 0.3, size=n))
    high = np.maximum(open_, close) + noise
    low = np.minimum(open_, close) - noise
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": rng.integers(1e5, 1e6, n)},
        index=idx,
    )

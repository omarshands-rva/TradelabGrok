"""Load OHLC bars from CSV or Parquet. Falls back to synthetic for demos."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import pandas as pd

from tradelab.data.bars import synthetic_ohlc, validate_bars

PathLike = Union[str, Path]


def load_bars(
    path: Optional[PathLike] = None,
    *,
    symbol: str = "ASSET",
    n_synthetic: int = 500,
    synthetic_vol: float = 0.012,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Load bars from path (CSV/Parquet) or generate synthetic GBM.

    Expected columns: open, high, low, close [, volume].
    Index should be datetime if present; otherwise a business-day index is assigned.
    """
    if path is None:
        return synthetic_ohlc(n_synthetic, vol=synthetic_vol, seed=seed)

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"bar file not found: {p}")

    if p.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(p)
    elif p.suffix.lower() in {".csv", ".txt"}:
        df = pd.read_csv(p)
    else:
        raise ValueError(f"unsupported bar file type: {p.suffix}")

    df.columns = [str(c).strip().lower() for c in df.columns]
    rename = {}
    for col in df.columns:
        if col in ("date", "datetime", "timestamp", "time"):
            rename[col] = "_ts"
        elif col in ("o", "open"):
            rename[col] = "open"
        elif col in ("h", "high"):
            rename[col] = "high"
        elif col in ("l", "low"):
            rename[col] = "low"
        elif col in ("c", "close", "adj_close", "adj close"):
            rename[col] = "close"
        elif col in ("v", "vol", "volume"):
            rename[col] = "volume"
    df = df.rename(columns=rename)

    if "_ts" in df.columns:
        df["_ts"] = pd.to_datetime(df["_ts"])
        df = df.set_index("_ts").sort_index()
    elif not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.date_range("2020-01-01", periods=len(df), freq="B")

    df = validate_bars(df)
    df.attrs["symbol"] = symbol
    return df

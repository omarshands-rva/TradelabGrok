"""Bar feed interface — historical batch and simulated realtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Optional

import pandas as pd


@dataclass(frozen=True, slots=True)
class Bar:
    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    index: int = 0  # position in source series


class BarFeed(ABC):
    """Yields bars in time order. Live adapters stream; historical replays a frame."""

    @abstractmethod
    def __iter__(self) -> Iterator[Bar]:
        ...

    @property
    @abstractmethod
    def symbol(self) -> str:
        ...


class HistoricalFeed(BarFeed):
    """Replay a validated OHLC DataFrame as bars."""

    def __init__(self, bars: pd.DataFrame, *, symbol: str = "ASSET", start_index: int = 0) -> None:
        self._bars = bars
        self._symbol = symbol
        self._start = start_index

    @property
    def symbol(self) -> str:
        return self._symbol

    def __iter__(self) -> Iterator[Bar]:
        for i in range(self._start, len(self._bars)):
            row = self._bars.iloc[i]
            ts = self._bars.index[i]
            if not isinstance(ts, datetime):
                ts = pd.Timestamp(ts).to_pydatetime()
            yield Bar(
                symbol=self._symbol,
                ts=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]) if "volume" in self._bars.columns else 0.0,
                index=i,
            )


class SimulatedRealtimeFeed(BarFeed):
    """
    Same as HistoricalFeed but optional sleep between bars for demo 'live' pacing.
    Does not block tests when delay_sec=0.
    """

    def __init__(
        self,
        bars: pd.DataFrame,
        *,
        symbol: str = "ASSET",
        start_index: int = 0,
        delay_sec: float = 0.0,
    ) -> None:
        self._inner = HistoricalFeed(bars, symbol=symbol, start_index=start_index)
        self._delay = delay_sec

    @property
    def symbol(self) -> str:
        return self._inner.symbol

    def __iter__(self) -> Iterator[Bar]:
        import time

        for bar in self._inner:
            if self._delay > 0:
                time.sleep(self._delay)
            yield bar

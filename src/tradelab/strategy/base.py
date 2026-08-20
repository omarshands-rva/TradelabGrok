"""Strategy protocol — single interface for research and paper/live."""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from tradelab.core.types import Order, PortfolioState


class StrategyProtocol(Protocol):
    """Generate orders given bar index, full history, and current portfolio."""

    name: str

    def on_bar(
        self,
        i: int,
        bars: pd.DataFrame,
        state: PortfolioState,
        *,
        symbol: str = "ASSET",
    ) -> list[Order]:
        ...

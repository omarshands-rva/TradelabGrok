"""Simple SMA crossover momentum — long-only, target fraction of equity."""

from __future__ import annotations

import pandas as pd

from tradelab.core.types import Order, PortfolioState, Side


class MomentumStrategy:
    name = "momentum"

    def __init__(
        self,
        window: int = 20,
        fraction: float = 0.95,
        min_notional: float = 50.0,
    ) -> None:
        self.window = window
        self.fraction = fraction
        self.min_notional = min_notional

    def on_bar(
        self,
        i: int,
        bars: pd.DataFrame,
        state: PortfolioState,
        *,
        symbol: str = "ASSET",
    ) -> list[Order]:
        if i < self.window:
            return []
        sma = float(bars["close"].iloc[i - self.window : i].mean())
        mid = float(bars["close"].iloc[i])
        pos = state.positions.get(symbol)
        qty = pos.qty if pos else 0.0
        equity = state.equity({symbol: mid})
        target = (self.fraction * equity / mid) if mid > sma else 0.0
        delta = target - qty
        if abs(delta) * mid < self.min_notional:
            return []
        side = Side.BUY if delta > 0 else Side.SELL
        return [Order(symbol=symbol, side=side, qty=abs(delta), tag=self.name)]

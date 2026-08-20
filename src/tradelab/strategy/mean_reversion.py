"""Bollinger-band mean reversion — long when below lower band, flat otherwise."""

from __future__ import annotations

import pandas as pd

from tradelab.core.types import Order, PortfolioState, Side


class MeanReversionStrategy:
    name = "mean_reversion"

    def __init__(
        self,
        window: int = 20,
        num_std: float = 2.0,
        fraction: float = 0.95,
        min_notional: float = 50.0,
    ) -> None:
        self.window = window
        self.num_std = num_std
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
        window = bars["close"].iloc[i - self.window : i]
        mid_px = float(window.mean())
        std = float(window.std(ddof=1)) or 1e-12
        lower = mid_px - self.num_std * std
        price = float(bars["close"].iloc[i])
        pos = state.positions.get(symbol)
        qty = pos.qty if pos else 0.0
        equity = state.equity({symbol: price})

        if price < lower:
            target = self.fraction * equity / price
        elif price > mid_px:
            target = 0.0
        else:
            target = qty

        delta = target - qty
        if abs(delta) * price < self.min_notional:
            return []
        side = Side.BUY if delta > 0 else Side.SELL
        return [Order(symbol=symbol, side=side, qty=abs(delta), tag=self.name)]

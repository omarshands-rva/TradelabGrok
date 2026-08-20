"""Core domain types. Immutable where practical."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

    def opposite(self) -> "Side":
        return Side.SELL if self is Side.BUY else Side.BUY


@dataclass(frozen=True, slots=True)
class Order:
    """Intent to trade. Not yet risk-checked or cost-adjusted."""

    symbol: str
    side: Side
    qty: float
    limit_price: Optional[float] = None  # None = market
    ts: Optional[datetime] = None
    tag: str = ""
    client_id: str = ""

    def __post_init__(self) -> None:
        if self.qty <= 0:
            raise ValueError("qty must be positive")


@dataclass(frozen=True, slots=True)
class Fill:
    """Executed trade after cost model."""

    symbol: str
    side: Side
    qty: float
    price: float  # fill price after slippage
    commission: float
    slippage_bps: float
    ts: datetime
    order_tag: str = ""

    @property
    def notional(self) -> float:
        return self.qty * self.price

    @property
    def total_cost(self) -> float:
        """Commission only (slippage is embedded in price)."""
        return self.commission


@dataclass(slots=True)
class Position:
    symbol: str
    qty: float = 0.0
    avg_price: float = 0.0
    realized_pnl: float = 0.0

    @property
    def is_flat(self) -> bool:
        return abs(self.qty) < 1e-12

    def market_value(self, mark: float) -> float:
        return self.qty * mark

    def unrealized_pnl(self, mark: float) -> float:
        return self.qty * (mark - self.avg_price)


@dataclass(slots=True)
class PortfolioState:
    """Single-book state. Own capital only."""

    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    equity_high_water: float = 0.0
    peak_equity: float = 0.0
    day_start_equity: float = 0.0
    kills: list[str] = field(default_factory=list)

    def equity(self, marks: dict[str, float]) -> float:
        mv = sum(p.market_value(marks.get(s, p.avg_price)) for s, p in self.positions.items())
        return self.cash + mv

    def drawdown(self, marks: dict[str, float]) -> float:
        eq = self.equity(marks)
        if self.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.peak_equity - eq) / self.peak_equity)

    def update_peaks(self, marks: dict[str, float]) -> None:
        eq = self.equity(marks)
        self.peak_equity = max(self.peak_equity, eq)
        self.equity_high_water = max(self.equity_high_water, eq)

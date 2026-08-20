"""Transaction cost model.

All costs are explicit. Optimistic zero-cost fills are rejected by design.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import sqrt
from typing import Optional

from tradelab.core.config import CostConfig
from tradelab.core.types import Fill, Order, Side


@dataclass(frozen=True, slots=True)
class CostEstimate:
    fill_price: float
    commission: float
    slippage_bps: float
    impact_bps: float
    total_bps: float


class CostModel:
    """Applies commission + half-spread + base slippage + optional sqrt impact."""

    def __init__(self, cfg: CostConfig) -> None:
        self.cfg = cfg

    def estimate(
        self,
        order: Order,
        mid: float,
        *,
        adv: Optional[float] = None,
        quoted_spread_bps: Optional[float] = None,
    ) -> CostEstimate:
        if mid <= 0:
            raise ValueError("mid must be positive")

        half_spread = (quoted_spread_bps if quoted_spread_bps is not None else self.cfg.spread_bps) / 2.0
        base_slip = self.cfg.slippage_bps

        impact = 0.0
        if self.cfg.impact_coeff > 0:
            volume = adv if adv is not None else self.cfg.adv_fallback
            if volume > 0:
                impact = self.cfg.impact_coeff * sqrt(order.qty / volume)

        total_bps = half_spread + base_slip + impact
        direction = 1.0 if order.side is Side.BUY else -1.0
        fill_price = mid * (1.0 + direction * total_bps / 10_000.0)

        notional = order.qty * fill_price
        if self.cfg.commission_pct > 0:
            commission = max(self.cfg.commission_min, notional * self.cfg.commission_pct)
        else:
            commission = max(self.cfg.commission_min, order.qty * self.cfg.commission_per_share)

        return CostEstimate(
            fill_price=fill_price,
            commission=commission,
            slippage_bps=base_slip + impact,
            impact_bps=impact,
            total_bps=total_bps,
        )

    def execute(
        self,
        order: Order,
        mid: float,
        *,
        adv: Optional[float] = None,
        quoted_spread_bps: Optional[float] = None,
        ts: Optional[datetime] = None,
    ) -> Fill:
        est = self.estimate(order, mid, adv=adv, quoted_spread_bps=quoted_spread_bps)
        return Fill(
            symbol=order.symbol,
            side=order.side,
            qty=order.qty,
            price=est.fill_price,
            commission=est.commission,
            slippage_bps=est.slippage_bps,
            ts=ts or datetime.now(timezone.utc),
            order_tag=order.tag,
        )

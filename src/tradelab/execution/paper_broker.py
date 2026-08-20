"""Paper broker — synchronous fills via CostModel."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from tradelab.core.types import Fill, Order
from tradelab.cost.model import CostModel
from tradelab.execution.broker import BrokerAdapter, BrokerOrderAck


class PaperBroker(BrokerAdapter):
    name = "paper"

    def __init__(self, cost: CostModel) -> None:
        self.cost = cost
        self._n = 0

    def submit(
        self,
        order: Order,
        *,
        mid: float,
        adv: Optional[float] = None,
    ) -> tuple[BrokerOrderAck, Optional[Fill]]:
        self._n += 1
        oid = f"paper-{self._n}-{uuid4().hex[:8]}"
        fill = self.cost.execute(
            order,
            mid,
            adv=adv,
            ts=order.ts or datetime.now(timezone.utc),
        )
        fill = Fill(
            symbol=fill.symbol,
            side=fill.side,
            qty=fill.qty,
            price=fill.price,
            commission=fill.commission,
            slippage_bps=fill.slippage_bps,
            ts=fill.ts,
            order_tag=order.tag or order.client_id or oid,
        )
        ack = BrokerOrderAck(
            client_id=order.client_id or oid,
            accepted=True,
            broker_order_id=oid,
        )
        return ack, fill

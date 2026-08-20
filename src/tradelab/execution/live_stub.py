"""
Live broker stub — interface ready for IB/Alpaca wiring.

Does NOT place real orders. Rejects submits with a clear message so a
misconfigured live session cannot silently paper-trade.
"""

from __future__ import annotations

from typing import Optional

from tradelab.core.types import Fill, Order
from tradelab.execution.broker import BrokerAdapter, BrokerOrderAck


class LiveStubBroker(BrokerAdapter):
    """
    Placeholder for a real venue adapter.

    Wire Interactive Brokers / Alpaca / etc. by subclassing BrokerAdapter
    and replacing this in the session factory. Until then, live mode refuses
    to submit so own-capital safety is preserved.
    """

    name = "live_stub"

    def __init__(self, *, venue: str = "unset") -> None:
        self.venue = venue
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def submit(
        self,
        order: Order,
        *,
        mid: float,
        adv: Optional[float] = None,
    ) -> tuple[BrokerOrderAck, Optional[Fill]]:
        return (
            BrokerOrderAck(
                client_id=order.client_id or "",
                accepted=False,
                reason=(
                    f"live_stub: no venue wired (venue={self.venue}). "
                    "Implement BrokerAdapter for your broker before live trading."
                ),
            ),
            None,
        )

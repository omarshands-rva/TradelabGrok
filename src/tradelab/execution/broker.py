"""Broker adapter interface.

Paper and live backends implement the same protocol so the run loop never
branches on environment. Live adapters only replace fill generation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from tradelab.core.types import Fill, Order


@dataclass(frozen=True, slots=True)
class BrokerOrderAck:
    """Acknowledgement that the venue accepted (or rejected) an order."""

    client_id: str
    accepted: bool
    broker_order_id: str = ""
    reason: str = ""


class BrokerAdapter(ABC):
    """
    Minimal broker surface.

    - submit: send order after risk has already approved it
    - cancel: optional
    - poll_fills: drain any async fills (live); paper returns immediately
    """

    name: str = "base"

    @abstractmethod
    def submit(
        self,
        order: Order,
        *,
        mid: float,
        adv: Optional[float] = None,
    ) -> tuple[BrokerOrderAck, Optional[Fill]]:
        """
        Submit a risk-approved order.

        Returns (ack, fill). Paper fills synchronously; live may return
        fill=None and deliver later via poll_fills.
        """

    def cancel(self, broker_order_id: str) -> bool:
        return False

    def poll_fills(self) -> Sequence[Fill]:
        return ()

    def connect(self) -> None:
        """Optional: open venue connection."""

    def disconnect(self) -> None:
        """Optional: close venue connection."""

    def is_connected(self) -> bool:
        return True

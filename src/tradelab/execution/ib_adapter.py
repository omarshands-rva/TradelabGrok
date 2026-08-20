"""
Interactive Brokers adapter (ib_insync).

Safety gates (all must pass before a real order is sent):
  1. ib_insync installed
  2. enabled=True (config session.ib_enabled or constructor)
  3. Connected to TWS/Gateway
  4. Contract qualified

Default port 7497 = paper. Live port is typically 7496 — set explicitly.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from tradelab.core.types import Fill, Order, Side
from tradelab.execution.broker import BrokerAdapter, BrokerOrderAck

log = logging.getLogger(__name__)

try:
    from ib_insync import IB, MarketOrder, LimitOrder, Stock  # type: ignore

    _HAS_IB = True
except ImportError:  # pragma: no cover
    IB = None  # type: ignore
    MarketOrder = None  # type: ignore
    LimitOrder = None  # type: ignore
    Stock = None  # type: ignore
    _HAS_IB = False


class IBBroker(BrokerAdapter):
    name = "ib"

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        account: str = "",
        enabled: bool = False,
        currency: str = "USD",
        exchange: str = "SMART",
        fill_timeout_sec: float = 15.0,
        readonly: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self.account = account
        self.enabled = enabled
        self.currency = currency
        self.exchange = exchange
        self.fill_timeout_sec = fill_timeout_sec
        self.readonly = readonly
        self._ib: Any = None
        self._connected = False
        self._pending_fills: list[Fill] = []
        self._trades: dict[str, Any] = {}

    def connect(self) -> None:
        if not _HAS_IB:
            log.warning("ib_insync not installed — IBBroker will reject all orders")
            self._connected = False
            return
        if self._ib is None:
            self._ib = IB()
        if self._ib.isConnected():
            self._connected = True
            return
        try:
            self._ib.connect(
                self.host,
                self.port,
                clientId=self.client_id,
                readonly=self.readonly,
            )
            self._connected = self._ib.isConnected()
            log.info("IB connected %s:%s clientId=%s", self.host, self.port, self.client_id)
        except Exception as exc:  # pragma: no cover
            self._connected = False
            log.error("IB connect failed: %s", exc)

    def disconnect(self) -> None:
        if self._ib is not None and _HAS_IB:
            try:
                if self._ib.isConnected():
                    self._ib.disconnect()
            except Exception:  # pragma: no cover
                pass
        self._connected = False

    def is_connected(self) -> bool:
        if self._ib is not None and _HAS_IB:
            try:
                return bool(self._ib.isConnected())
            except Exception:
                return False
        return self._connected

    def submit(
        self,
        order: Order,
        *,
        mid: float,
        adv: Optional[float] = None,
    ) -> tuple[BrokerOrderAck, Optional[Fill]]:
        gate = self._gate_reason()
        if gate:
            return (
                BrokerOrderAck(
                    client_id=order.client_id or "",
                    accepted=False,
                    reason=gate,
                ),
                None,
            )

        assert self._ib is not None
        try:
            contract = Stock(order.symbol, self.exchange, self.currency)
            qualified = self._ib.qualifyContracts(contract)
            if not qualified:
                return (
                    BrokerOrderAck(
                        client_id=order.client_id or "",
                        accepted=False,
                        reason=f"IB: could not qualify contract {order.symbol}",
                    ),
                    None,
                )
            contract = qualified[0]

            action = "BUY" if order.side is Side.BUY else "SELL"
            qty = float(order.qty)
            if order.limit_price is not None:
                ib_order = LimitOrder(action, qty, order.limit_price)
            else:
                ib_order = MarketOrder(action, qty)
            if self.account:
                ib_order.account = self.account

            trade = self._ib.placeOrder(contract, ib_order)
            broker_id = str(trade.order.orderId)
            self._trades[broker_id] = trade

            filled = self._wait_done(trade)
            if filled and trade.fills:
                fill = self._trade_to_fill(order, trade)
                return (
                    BrokerOrderAck(
                        client_id=order.client_id or "",
                        accepted=True,
                        broker_order_id=broker_id,
                    ),
                    fill,
                )

            return (
                BrokerOrderAck(
                    client_id=order.client_id or "",
                    accepted=True,
                    broker_order_id=broker_id,
                    reason="submitted; awaiting fill",
                ),
                None,
            )
        except Exception as exc:
            log.exception("IB submit error")
            return (
                BrokerOrderAck(
                    client_id=order.client_id or "",
                    accepted=False,
                    reason=f"IB submit error: {exc}",
                ),
                None,
            )

    def poll_fills(self) -> Sequence[Fill]:
        out: list[Fill] = list(self._pending_fills)
        self._pending_fills.clear()

        if not self.is_connected() or not self._trades:
            return out

        assert self._ib is not None
        try:
            self._ib.sleep(0)
        except Exception:
            pass

        done_ids: list[str] = []
        for oid, trade in list(self._trades.items()):
            if trade.isDone() and trade.fills:
                side = Side.BUY if trade.order.action.upper() == "BUY" else Side.SELL
                stub = Order(
                    symbol=trade.contract.symbol,
                    side=side,
                    qty=float(trade.order.totalQuantity),
                    tag=str(getattr(trade.order, "orderRef", "") or ""),
                    client_id=str(getattr(trade.order, "orderRef", "") or oid),
                )
                out.append(self._trade_to_fill(stub, trade))
                done_ids.append(oid)
            elif trade.isDone():
                done_ids.append(oid)
        for oid in done_ids:
            self._trades.pop(oid, None)
        return out

    def cancel(self, broker_order_id: str) -> bool:
        if not self.is_connected() or not _HAS_IB:
            return False
        trade = self._trades.get(broker_order_id)
        if trade is None:
            return False
        try:
            self._ib.cancelOrder(trade.order)
            return True
        except Exception:
            return False

    def _gate_reason(self) -> Optional[str]:
        if not _HAS_IB:
            return "IBBroker: ib_insync not installed (pip install ib_insync)"
        if not self.enabled:
            return (
                "IBBroker: disabled. Set enabled=True / session.ib_enabled: true "
                "after verifying paper parity on port 7497."
            )
        if not self.is_connected():
            return "IBBroker: not connected to TWS/Gateway"
        return None

    def _wait_done(self, trade: Any) -> bool:
        if not _HAS_IB or self._ib is None:
            return False
        try:
            steps = max(1, int(self.fill_timeout_sec * 10))
            for _ in range(steps):
                if trade.isDone():
                    return True
                self._ib.sleep(0.1)
            return bool(trade.isDone())
        except Exception:
            return False

    def _trade_to_fill(self, order: Order, trade: Any) -> Fill:
        shares = 0.0
        notional = 0.0
        commission = 0.0
        for f in trade.fills:
            shares += float(f.execution.shares)
            notional += float(f.execution.shares) * float(f.execution.price)
            if f.commissionReport is not None:
                commission += abs(float(getattr(f.commissionReport, "commission", 0) or 0))
        price = (notional / shares) if shares > 0 else float(
            getattr(trade.orderStatus, "avgFillPrice", 0) or 0
        )
        ts = datetime.now(timezone.utc)
        if trade.fills:
            t0 = trade.fills[-1].execution.time
            if t0 is not None:
                if t0.tzinfo is None:
                    ts = t0.replace(tzinfo=timezone.utc)
                else:
                    ts = t0
        return Fill(
            symbol=order.symbol,
            side=order.side,
            qty=shares if shares > 0 else float(order.qty),
            price=price,
            commission=commission,
            slippage_bps=0.0,
            ts=ts,
            order_tag=order.tag or order.client_id,
        )


def ib_available() -> bool:
    return _HAS_IB

from tradelab.core.types import Order, Side
from tradelab.execution.ib_adapter import IBBroker, ib_available


def test_ib_disabled_rejects():
    broker = IBBroker(enabled=False)
    broker.connect()
    ack, fill = broker.submit(
        Order(symbol="SPY", side=Side.BUY, qty=1),
        mid=100.0,
    )
    assert not ack.accepted
    assert fill is None
    assert "disabled" in ack.reason.lower() or "not installed" in ack.reason.lower()


def test_ib_enabled_but_not_connected_rejects():
    broker = IBBroker(enabled=True, host="127.0.0.1", port=59999, client_id=99)
    broker.connect()
    ack, fill = broker.submit(
        Order(symbol="SPY", side=Side.BUY, qty=1),
        mid=100.0,
    )
    assert not ack.accepted
    assert fill is None


def test_ib_available_is_bool():
    assert isinstance(ib_available(), bool)

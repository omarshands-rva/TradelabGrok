from datetime import datetime, timezone

from tradelab.core.types import Fill, PortfolioState, Side
from tradelab.core.portfolio import apply_fill


def _fill(side, qty, price):
    return Fill(
        symbol="X",
        side=side,
        qty=qty,
        price=price,
        commission=1.0,
        slippage_bps=0.0,
        ts=datetime.now(timezone.utc),
    )


def test_open_long():
    state = PortfolioState(cash=10_000.0)
    apply_fill(state, _fill(Side.BUY, 10, 100.0))
    assert state.positions["X"].qty == 10
    assert abs(state.cash - (10_000 - 1000 - 1)) < 1e-6


def test_close_long_realizes_pnl():
    state = PortfolioState(cash=10_000.0)
    apply_fill(state, _fill(Side.BUY, 10, 100.0))
    apply_fill(state, _fill(Side.SELL, 10, 110.0))
    assert state.positions["X"].is_flat
    assert state.positions["X"].realized_pnl == 100.0

"""Shared portfolio accounting. Used by evaluation harness and paper engine."""

from __future__ import annotations

from typing import Optional

from tradelab.core.types import Fill, PortfolioState, Position, Side


def apply_fill(state: PortfolioState, fill: Fill) -> float:
    """
    Apply a fill to portfolio state. Mutates state in place.

    Returns realized PnL attributable to this fill (including commission as cost).
    Cash and average price are updated correctly for open / increase / reduce / flip.
    """
    pos = state.positions.get(fill.symbol)
    if pos is None:
        pos = state.positions.setdefault(fill.symbol, Position(symbol=fill.symbol))

    signed = fill.qty if fill.side is Side.BUY else -fill.qty
    realized = 0.0

    if pos.is_flat:
        pos.qty = signed
        pos.avg_price = fill.price
    elif (pos.qty > 0 and signed > 0) or (pos.qty < 0 and signed < 0):
        new_qty = pos.qty + signed
        pos.avg_price = (pos.avg_price * abs(pos.qty) + fill.price * fill.qty) / abs(new_qty)
        pos.qty = new_qty
    else:
        close_qty = min(abs(pos.qty), fill.qty)
        if pos.qty > 0:
            realized = close_qty * (fill.price - pos.avg_price)
        else:
            realized = close_qty * (pos.avg_price - fill.price)

        remaining = abs(pos.qty) - close_qty
        if remaining > 1e-12:
            pos.qty = remaining if pos.qty > 0 else -remaining
        elif fill.qty > close_qty + 1e-12:
            residual = fill.qty - close_qty
            pos.qty = residual if fill.side is Side.BUY else -residual
            pos.avg_price = fill.price
        else:
            pos.qty = 0.0
            pos.avg_price = 0.0

        pos.realized_pnl += realized

    if fill.side is Side.BUY:
        state.cash -= fill.notional + fill.commission
    else:
        state.cash += fill.notional - fill.commission

    return realized - fill.commission


def portfolio_snapshot(state: PortfolioState, marks: dict[str, float]) -> dict:
    """Lightweight status dict for logging / UI."""
    eq = state.equity(marks)
    return {
        "cash": state.cash,
        "equity": eq,
        "peak_equity": state.peak_equity,
        "drawdown": state.drawdown(marks),
        "positions": {
            s: {"qty": p.qty, "avg_price": p.avg_price, "mkt": p.market_value(marks.get(s, p.avg_price))}
            for s, p in state.positions.items()
            if not p.is_flat
        },
        "killed": bool(state.kills),
    }

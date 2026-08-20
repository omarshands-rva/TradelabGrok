"""Rebuild PortfolioState from a journal (resume / audit)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from tradelab.core.portfolio import apply_fill
from tradelab.core.types import Fill, PortfolioState, Side
from tradelab.persistence.journal import Journal


@dataclass
class RestoredSession:
    session_id: str
    mode: str
    strategy: str
    symbol: str
    starting_cash: float
    state: PortfolioState
    n_fills: int
    last_bar_i: Optional[int]
    killed: bool
    kill_reason: Optional[str]
    ended: bool


def restore_from_journal(
    path: Union[str, Path],
    *,
    session_id: Optional[str] = None,
) -> RestoredSession:
    """
    Replay fills for a session into a fresh PortfolioState.

    If session_id is None, uses the last session_start in the file.
    """
    journal = Journal(path)
    events = list(journal.iter_events())
    if not events:
        raise ValueError(f"empty journal: {path}")

    starts = [e for e in events if e.get("event") == "session_start"]
    if not starts:
        raise ValueError("no session_start in journal")
    if session_id is None:
        start = starts[-1]
        session_id = start["session_id"]
    else:
        matched = [e for e in starts if e["session_id"] == session_id]
        if not matched:
            raise ValueError(f"session_id not found: {session_id}")
        start = matched[-1]

    sid = start["session_id"]
    cash = float(start.get("starting_cash", 0))
    state = PortfolioState(
        cash=cash,
        day_start_equity=cash,
        peak_equity=cash,
        equity_high_water=cash,
    )

    n_fills = 0
    last_bar_i: Optional[int] = None
    killed = False
    kill_reason: Optional[str] = None
    ended = False

    for e in events:
        if e.get("session_id") != sid:
            continue
        ev = e.get("event")
        if ev == "fill":
            fill = _event_to_fill(e)
            apply_fill(state, fill)
            n_fills += 1
        elif ev == "equity":
            last_bar_i = e.get("bar_i", last_bar_i)
            eq = float(e.get("equity", state.cash))
            state.peak_equity = max(state.peak_equity, eq)
        elif ev == "kill":
            killed = True
            kill_reason = e.get("reason")
            state.kills.append(kill_reason or "kill")
        elif ev == "session_end":
            ended = True

    return RestoredSession(
        session_id=sid,
        mode=str(start.get("mode", "paper")),
        strategy=str(start.get("strategy", "")),
        symbol=str(start.get("symbol", "")),
        starting_cash=cash,
        state=state,
        n_fills=n_fills,
        last_bar_i=last_bar_i,
        killed=killed,
        kill_reason=kill_reason,
        ended=ended,
    )


def _event_to_fill(e: dict[str, Any]) -> Fill:
    ts_raw = e.get("fill_ts") or e.get("ts")
    if isinstance(ts_raw, str):
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
    else:
        ts = datetime.now(timezone.utc)
    side = Side(e["side"]) if not isinstance(e.get("side"), Side) else e["side"]
    return Fill(
        symbol=str(e["symbol"]),
        side=side,
        qty=float(e["qty"]),
        price=float(e["price"]),
        commission=float(e.get("commission", 0)),
        slippage_bps=float(e.get("slippage_bps", 0)),
        ts=ts,
        order_tag=str(e.get("order_tag", "")),
    )

"""Unified trading session — paper or live via BrokerAdapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import pandas as pd

from tradelab.core.config import TradeLabConfig
from tradelab.core.portfolio import apply_fill
from tradelab.core.types import Fill, Order, PortfolioState
from tradelab.cost.model import CostModel
from tradelab.data.feed import Bar, BarFeed, HistoricalFeed
from tradelab.eval.metrics import PerformanceReport, compute_metrics
from tradelab.execution.broker import BrokerAdapter
from tradelab.execution.ib_adapter import IBBroker
from tradelab.execution.live_stub import LiveStubBroker
from tradelab.execution.paper_broker import PaperBroker
from tradelab.persistence.journal import Journal, SessionRecord
from tradelab.risk.engine import RiskEngine, RiskVerdict
from tradelab.strategy.base import StrategyProtocol


@dataclass
class SessionResult:
    session_id: str
    mode: str
    equity: list[float]
    fills: list[Fill]
    trade_pnls: list[float]
    report: PerformanceReport
    final_state: PortfolioState
    rejected: list[dict[str, Any]] = field(default_factory=list)
    kill_reason: Optional[str] = None
    journal_path: Optional[str] = None

    @property
    def n_fills(self) -> int:
        return len(self.fills)


class TradingSession:
    """Bar-driven session. mode=paper → PaperBroker; mode=live → IB or stub."""

    def __init__(
        self,
        cfg: TradeLabConfig,
        *,
        mode: str = "paper",
        broker: Optional[BrokerAdapter] = None,
        journal: Optional[Journal] = None,
        heartbeat_every: int = 50,
        initial_state: Optional[PortfolioState] = None,
        session_id: Optional[str] = None,
    ) -> None:
        self.cfg = cfg
        self.mode = mode
        self.cost = CostModel(cfg.cost)
        self.risk = RiskEngine(cfg.risk)
        if broker is not None:
            self.broker = broker
        elif mode == "live":
            venue = cfg.session.live_venue.lower()
            if venue in ("ib", "interactive_brokers"):
                sc = cfg.session
                self.broker = IBBroker(
                    host=sc.ib_host,
                    port=sc.ib_port,
                    client_id=sc.ib_client_id,
                    account=sc.ib_account,
                    enabled=sc.ib_enabled,
                    fill_timeout_sec=sc.ib_fill_timeout_sec,
                )
            else:
                self.broker = LiveStubBroker(venue=cfg.session.live_venue)
        else:
            self.broker = PaperBroker(self.cost)
        self.journal = journal
        self.heartbeat_every = heartbeat_every
        self._initial_state = initial_state
        self._forced_session_id = session_id

    def run(
        self,
        strategy: StrategyProtocol,
        bars: pd.DataFrame,
        *,
        symbol: str = "ASSET",
        start_index: int = 0,
    ) -> SessionResult:
        feed = HistoricalFeed(bars, symbol=symbol, start_index=start_index)
        return self.run_feed(strategy, feed, bars=bars)

    def run_feed(
        self,
        strategy: StrategyProtocol,
        feed: BarFeed,
        *,
        bars: Optional[pd.DataFrame] = None,
    ) -> SessionResult:
        session_id = self._forced_session_id or uuid4().hex[:12]
        if self._initial_state is not None:
            state = self._initial_state
        else:
            state = PortfolioState(
                cash=self.cfg.starting_cash,
                day_start_equity=self.cfg.starting_cash,
                peak_equity=self.cfg.starting_cash,
                equity_high_water=self.cfg.starting_cash,
            )

        equity: list[float] = [state.equity({})]
        fills: list[Fill] = []
        trade_pnls: list[float] = []
        rejected: list[dict[str, Any]] = []
        marks: dict[str, float] = {}
        kill_reason: Optional[str] = None
        last_day: Any = None
        symbol = feed.symbol
        history_rows: list[dict[str, Any]] = []
        history_index: list[Any] = []

        if self.journal and self._forced_session_id is None:
            self.journal.session_start(
                SessionRecord(
                    session_id=session_id,
                    mode=self.mode,
                    strategy=getattr(strategy, "name", strategy.__class__.__name__),
                    symbol=symbol,
                    started_at=datetime.now(timezone.utc).isoformat(),
                    starting_cash=self.cfg.starting_cash,
                    config_snapshot={
                        "risk": self.cfg.risk.model_dump(),
                        "cost": self.cfg.cost.model_dump(),
                    },
                )
            )

        self.broker.connect()
        bar_count = 0

        try:
            for bar in feed:
                bar_count += 1
                mid = bar.close
                marks[symbol] = mid

                day = bar.ts.date() if bar.ts else None
                if day is not None and day != last_day:
                    state.day_start_equity = state.equity(marks)
                    last_day = day

                state.update_peaks(marks)

                for delayed in self.broker.poll_fills():
                    pnl = apply_fill(state, delayed)
                    fills.append(delayed)
                    trade_pnls.append(pnl)
                    if self.journal:
                        self.journal.fill(session_id, delayed)

                if bars is not None:
                    hist = bars
                    i = bar.index
                else:
                    history_rows.append(
                        {
                            "open": bar.open,
                            "high": bar.high,
                            "low": bar.low,
                            "close": bar.close,
                            "volume": bar.volume,
                        }
                    )
                    history_index.append(bar.ts)
                    hist = pd.DataFrame(history_rows, index=pd.DatetimeIndex(history_index))
                    i = len(hist) - 1

                orders = strategy.on_bar(i, hist, state, symbol=symbol)
                for order in orders:
                    if order.symbol != symbol:
                        order = Order(
                            symbol=symbol,
                            side=order.side,
                            qty=order.qty,
                            limit_price=order.limit_price,
                            ts=order.ts,
                            tag=order.tag,
                            client_id=order.client_id,
                        )
                    decision = self.risk.check(order, state, marks)
                    if not decision.ok:
                        rejected.append(
                            {
                                "i": i,
                                "side": order.side.value,
                                "qty": order.qty,
                                "verdict": decision.verdict.value,
                                "reasons": list(decision.reasons),
                            }
                        )
                        if self.journal:
                            self.journal.reject(
                                session_id,
                                reasons=list(decision.reasons),
                                side=order.side.value,
                                qty=order.qty,
                            )
                        if decision.verdict is RiskVerdict.KILL:
                            reason = decision.reasons[0] if decision.reasons else "kill"
                            kill_reason = reason
                            state.kills.append(reason)
                            if self.journal:
                                self.journal.kill(session_id, reason)
                        continue

                    qty = decision.allowed_qty
                    if qty <= 0:
                        continue
                    adj = Order(
                        symbol=order.symbol,
                        side=order.side,
                        qty=qty,
                        limit_price=order.limit_price,
                        ts=order.ts or bar.ts or datetime.now(timezone.utc),
                        tag=order.tag,
                        client_id=order.client_id or f"{session_id}-{i}",
                    )
                    ack, fill = self.broker.submit(adj, mid=mid, adv=bar.volume or None)
                    if not ack.accepted:
                        rejected.append(
                            {
                                "i": i,
                                "side": adj.side.value,
                                "qty": adj.qty,
                                "verdict": "BROKER_REJECT",
                                "reasons": [ack.reason],
                            }
                        )
                        if self.journal:
                            self.journal.reject(
                                session_id,
                                reasons=[ack.reason],
                                side=adj.side.value,
                                qty=adj.qty,
                            )
                        continue
                    if fill is not None:
                        pnl = apply_fill(state, fill)
                        fills.append(fill)
                        trade_pnls.append(pnl)
                        if self.journal:
                            self.journal.fill(session_id, fill)

                eq = state.equity(marks)
                equity.append(eq)

                if self.journal and self.heartbeat_every and bar_count % self.heartbeat_every == 0:
                    self.journal.heartbeat(
                        session_id,
                        equity=eq,
                        connected=self.broker.is_connected(),
                    )
                    self.journal.equity_tick(session_id, eq, bar_i=i)

                if kill_reason:
                    break
        finally:
            self.broker.disconnect()
            if self.journal and self._forced_session_id is None:
                self.journal.session_end(
                    session_id,
                    equity=state.equity(marks) if marks else state.cash,
                    reason=kill_reason or "completed",
                )

        report = compute_metrics(
            equity,
            trade_pnls=trade_pnls,
            periods_per_year=self.cfg.eval.periods_per_year,
            n_trials=1,
        )
        return SessionResult(
            session_id=session_id,
            mode=self.mode,
            equity=equity,
            fills=fills,
            trade_pnls=trade_pnls,
            report=report,
            final_state=state,
            rejected=rejected,
            kill_reason=kill_reason,
            journal_path=str(self.journal.path) if self.journal else None,
        )

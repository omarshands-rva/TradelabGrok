"""Paper trading engine — same Order → Risk → Cost → Fill path as research."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from tradelab.core.config import TradeLabConfig
from tradelab.core.portfolio import apply_fill, portfolio_snapshot
from tradelab.core.types import Fill, Order, PortfolioState, Side
from tradelab.cost.model import CostModel
from tradelab.eval.metrics import PerformanceReport, compute_metrics
from tradelab.risk.engine import RiskEngine, RiskVerdict
from tradelab.strategy.base import StrategyProtocol


@dataclass
class PaperResult:
    equity: list[float]
    fills: list[Fill]
    trade_pnls: list[float]
    report: PerformanceReport
    final_state: PortfolioState
    rejected: list[dict[str, Any]] = field(default_factory=list)
    snapshots: list[dict[str, Any]] = field(default_factory=list)


class PaperEngine:
    """
    Bar-by-bar paper trading.

    Every order passes RiskEngine.check → CostModel.execute → apply_fill.
    Kill switches halt new risk for the remainder of the run.
    """

    def __init__(self, cfg: TradeLabConfig) -> None:
        self.cfg = cfg
        self.cost = CostModel(cfg.cost)
        self.risk = RiskEngine(cfg.risk)

    def run(
        self,
        strategy: StrategyProtocol,
        bars: pd.DataFrame,
        *,
        symbol: str = "ASSET",
        log_every: int = 0,
        start_index: int = 0,
    ) -> PaperResult:
        state = PortfolioState(
            cash=self.cfg.starting_cash,
            day_start_equity=self.cfg.starting_cash,
            peak_equity=self.cfg.starting_cash,
            equity_high_water=self.cfg.starting_cash,
        )
        equity: list[float] = [state.cash]
        fills: list[Fill] = []
        trade_pnls: list[float] = []
        rejected: list[dict[str, Any]] = []
        snapshots: list[dict[str, Any]] = []
        marks: dict[str, float] = {}

        last_day: Optional[Any] = None

        for i in range(start_index, len(bars)):
            row = bars.iloc[i]
            mid = float(row["close"])
            marks[symbol] = mid

            ts = bars.index[i] if hasattr(bars.index, "date") else None
            day = getattr(ts, "date", lambda: None)() if ts is not None else None
            if day is not None and day != last_day:
                state.day_start_equity = state.equity(marks)
                last_day = day

            state.update_peaks(marks)

            orders = strategy.on_bar(i, bars, state, symbol=symbol)
            for order in orders:
                if order.symbol != symbol:
                    order = Order(
                        symbol=symbol,
                        side=order.side,
                        qty=order.qty,
                        limit_price=order.limit_price,
                        ts=order.ts,
                        tag=order.tag,
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
                    if decision.verdict is RiskVerdict.KILL:
                        state.kills.append(decision.reasons[0] if decision.reasons else "kill")
                    continue

                qty = decision.allowed_qty
                if qty <= 0:
                    continue
                adj = Order(
                    symbol=order.symbol,
                    side=order.side,
                    qty=qty,
                    limit_price=order.limit_price,
                    ts=order.ts or datetime.now(timezone.utc),
                    tag=order.tag,
                )
                vol = float(row["volume"]) if "volume" in bars.columns else None
                fill = self.cost.execute(adj, mid, adv=vol)
                pnl = apply_fill(state, fill)
                fills.append(fill)
                trade_pnls.append(pnl)

            eq = state.equity(marks)
            equity.append(eq)

            if log_every and (i - start_index) % log_every == 0:
                snapshots.append({"i": i, **portfolio_snapshot(state, marks)})

        report = compute_metrics(
            equity,
            trade_pnls=trade_pnls,
            periods_per_year=self.cfg.eval.periods_per_year,
            n_trials=1,
        )
        return PaperResult(
            equity=equity,
            fills=fills,
            trade_pnls=trade_pnls,
            report=report,
            final_state=state,
            rejected=rejected,
            snapshots=snapshots,
        )

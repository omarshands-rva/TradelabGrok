"""Evaluation harness — strategy interface + walk-forward runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from tradelab.core.config import TradeLabConfig
from tradelab.core.portfolio import apply_fill
from tradelab.core.types import Order, PortfolioState, Side
from tradelab.cost.model import CostModel
from tradelab.eval.metrics import PerformanceReport, compute_metrics
from tradelab.eval.monte_carlo import PathStats, monte_carlo_paths, path_statistics
from tradelab.eval.walk_forward import WalkForwardSplit, generate_walk_forward_splits
from tradelab.risk.engine import RiskEngine
from tradelab.strategy.base import StrategyProtocol


@dataclass
class FoldResult:
    fold: int
    report: PerformanceReport
    equity: list[float]
    trade_pnls: list[float]


@dataclass
class HarnessResult:
    folds: list[FoldResult] = field(default_factory=list)
    aggregate: Optional[PerformanceReport] = None
    monte_carlo: Optional[PathStats] = None


class EvaluationHarness:
    """
    Runs a strategy through cost + risk on historical bars (research path).

    Uses the same RiskEngine + CostModel + apply_fill as PaperEngine.
    Bars DataFrame must have columns: open, high, low, close (optional volume).
    """

    def __init__(self, cfg: TradeLabConfig | None = None, **kwargs: object) -> None:
        if cfg is None:
            # Allow test-style kwargs: train_days, test_days, etc.
            from tradelab.core.config import EvalConfig
            eval_kwargs = {k: v for k, v in kwargs.items() if k in EvalConfig.model_fields}
            cfg = TradeLabConfig(eval=EvalConfig(**eval_kwargs))
        self.cfg = cfg
        self.cost = CostModel(cfg.cost)
        self.risk = RiskEngine(cfg.risk)

    def run(
        self,
        strategy: StrategyProtocol,
        bars: pd.DataFrame,
        *,
        symbol: str = "ASSET",
        walk_forward: bool = True,
        monte_carlo: bool = True,
    ) -> HarnessResult:
        n = len(bars)
        result = HarnessResult()

        if walk_forward:
            splits = list(
                generate_walk_forward_splits(
                    n,
                    train_size=self.cfg.eval.train_days,
                    test_size=self.cfg.eval.test_days,
                    purge=self.cfg.eval.purge_days,
                    embargo=self.cfg.eval.embargo_days,
                )
            )
            if not splits:
                splits = [
                    WalkForwardSplit(
                        train_idx=np.arange(0),
                        test_idx=np.arange(n),
                        fold=0,
                    )
                ]
        else:
            splits = [
                WalkForwardSplit(train_idx=np.arange(0), test_idx=np.arange(n), fold=0)
            ]

        all_rets: list[float] = []
        for split in splits:
            self.risk.reset_kill()
            fold = self._run_segment(strategy, bars, split.test_idx, symbol=symbol)
            result.folds.append(fold)
            eq = np.asarray(fold.equity)
            if len(eq) > 1:
                all_rets.extend((np.diff(eq) / eq[:-1]).tolist())

        if all_rets:
            result.aggregate = compute_metrics(
                _equity_from_returns(all_rets, self.cfg.starting_cash),
                periods_per_year=self.cfg.eval.periods_per_year,
                n_trials=max(1, len(result.folds)),
            )

        if monte_carlo and all_rets:
            paths = monte_carlo_paths(
                all_rets,
                n_paths=self.cfg.eval.n_monte_carlo,
                starting_equity=self.cfg.starting_cash,
            )
            result.monte_carlo = path_statistics(paths, ruin_threshold=0.5)

        return result

    def _run_segment(
        self,
        strategy: StrategyProtocol,
        bars: pd.DataFrame,
        idx: np.ndarray,
        *,
        symbol: str,
    ) -> FoldResult:
        state = PortfolioState(
            cash=self.cfg.starting_cash,
            day_start_equity=self.cfg.starting_cash,
            peak_equity=self.cfg.starting_cash,
        )
        equity: list[float] = [state.cash]
        trade_pnls: list[float] = []
        marks: dict[str, float] = {}
        idx_set = set(int(i) for i in idx)

        for i in range(len(bars)):
            row = bars.iloc[i]
            mid = float(row["close"])
            marks[symbol] = mid
            state.update_peaks(marks)

            if i not in idx_set:
                equity.append(state.equity(marks))
                continue

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
                trade_pnls.append(pnl)

            equity.append(state.equity(marks))

        report = compute_metrics(
            equity,
            trade_pnls=trade_pnls,
            periods_per_year=self.cfg.eval.periods_per_year,
        )
        fold_id = int(idx[0]) if len(idx) else 0
        return FoldResult(fold=fold_id, report=report, equity=equity, trade_pnls=trade_pnls)


def _equity_from_returns(returns: Sequence[float], start: float) -> list[float]:
    eq = [start]
    for r in returns:
        eq.append(eq[-1] * (1.0 + r))
    return eq

"""Performance metrics with deflated Sharpe (Bailey & López de Prado style)."""

from __future__ import annotations

from dataclasses import dataclass
from math import erf, log, sqrt
from typing import Optional, Sequence

import numpy as np


@dataclass(frozen=True, slots=True)
class PerformanceReport:
    total_return: float
    cagr: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    win_rate: float
    profit_factor: float
    n_trades: int
    avg_trade: float
    deflated_sharpe: Optional[float]
    periods: int


def _max_drawdown(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    dd = (peak - equity) / np.where(peak > 0, peak, 1.0)
    return float(np.max(dd)) if len(dd) else 0.0


def compute_metrics(
    equity_curve: Sequence[float],
    *,
    trade_pnls: Optional[Sequence[float]] = None,
    risk_free: float = 0.0,
    periods_per_year: int = 252,
    n_trials: int = 1,
) -> PerformanceReport:
    eq = np.asarray(equity_curve, dtype=float)
    if len(eq) < 2:
        return PerformanceReport(
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0.0, None, len(eq)
        )

    rets = np.diff(eq) / np.where(eq[:-1] != 0, eq[:-1], 1.0)
    total_ret = float(eq[-1] / eq[0] - 1.0) if eq[0] != 0 else 0.0
    years = len(rets) / periods_per_year
    cagr = float((eq[-1] / eq[0]) ** (1 / years) - 1) if years > 0 and eq[0] > 0 else 0.0

    excess = rets - risk_free / periods_per_year
    vol = float(np.std(excess, ddof=1)) if len(excess) > 1 else 0.0
    sharpe = float(np.mean(excess) / vol * sqrt(periods_per_year)) if vol > 1e-12 else 0.0

    downside = excess[excess < 0]
    dvol = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0.0
    sortino = float(np.mean(excess) / dvol * sqrt(periods_per_year)) if dvol > 1e-12 else 0.0

    mdd = _max_drawdown(eq)
    calmar = cagr / mdd if mdd > 1e-12 else 0.0

    pnls = np.asarray(trade_pnls, dtype=float) if trade_pnls is not None else np.array([])
    n_trades = len(pnls)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    win_rate = float(len(wins) / n_trades) if n_trades else 0.0
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 1e-12 else (float("inf") if gross_profit > 0 else 0.0)
    avg_trade = float(pnls.mean()) if n_trades else 0.0

    skew = 0.0
    if len(rets) > 2:
        m = float(np.mean(rets))
        s = float(np.std(rets, ddof=1))
        if s > 1e-12:
            skew = float(np.mean(((rets - m) / s) ** 3))
    dsr = _deflated_sharpe(sharpe, len(rets), n_trials=n_trials, skew=skew)

    return PerformanceReport(
        total_return=total_ret,
        cagr=cagr,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=mdd,
        calmar=calmar,
        win_rate=win_rate,
        profit_factor=profit_factor,
        n_trades=n_trades,
        avg_trade=avg_trade,
        deflated_sharpe=dsr,
        periods=len(rets),
    )


def _deflated_sharpe(
    observed_sr: float,
    n_obs: int,
    *,
    n_trials: int = 1,
    skew: float = 0.0,
    kurt: float = 3.0,
) -> Optional[float]:
    """Approximate Prob(SR* > 0) after multiple testing (Bailey & López de Prado)."""
    if n_obs < 2 or n_trials < 1:
        return None
    var = (1 + 0.5 * observed_sr**2 - skew * observed_sr + (kurt - 3) / 4 * observed_sr**2) / n_obs
    if var <= 0:
        return None
    se = sqrt(var)
    if se < 1e-12:
        return None
    se_null = 1.0 / sqrt(n_obs)
    e_max = se_null * (sqrt(2 * log(n_trials)) if n_trials > 1 else 0.0)
    z = (observed_sr - e_max) / se
    prob = 0.5 * (1.0 + erf(z / sqrt(2.0)))
    return float(prob)

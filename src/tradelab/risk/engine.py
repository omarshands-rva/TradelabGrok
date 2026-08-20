"""Risk engine — hard gates before any order is sent.

Every order passes through `check()`. A rejected order never reaches the cost
model or broker simulator.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from tradelab.core.config import RiskConfig
from tradelab.core.types import Order, PortfolioState, Side


class RiskVerdict(str, Enum):
    ALLOW = "ALLOW"
    REDUCE = "REDUCE"
    REJECT = "REJECT"
    KILL = "KILL"


@dataclass(frozen=True, slots=True)
class RiskDecision:
    verdict: RiskVerdict
    allowed_qty: float
    reasons: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.verdict in (RiskVerdict.ALLOW, RiskVerdict.REDUCE) and self.allowed_qty > 0


class RiskEngine:
    def __init__(self, cfg: RiskConfig) -> None:
        self.cfg = cfg
        self._killed = False
        self._kill_reason: Optional[str] = None

    @property
    def is_killed(self) -> bool:
        return self._killed

    def reset_kill(self) -> None:
        """Manual reset only (e.g. new trading day after review)."""
        self._killed = False
        self._kill_reason = None

    def check(
        self,
        order: Order,
        state: PortfolioState,
        marks: dict[str, float],
        *,
        volatility: Optional[float] = None,
    ) -> RiskDecision:
        if self._killed:
            return RiskDecision(
                RiskVerdict.KILL,
                0.0,
                (f"kill switch active: {self._kill_reason}",),
            )

        reasons: list[str] = []
        equity = state.equity(marks)
        if equity <= 0:
            return RiskDecision(RiskVerdict.REJECT, 0.0, ("non-positive equity",))

        if state.day_start_equity > 0:
            daily_pnl_pct = (equity - state.day_start_equity) / state.day_start_equity
            if daily_pnl_pct <= -self.cfg.max_daily_loss_pct:
                reasons.append(
                    f"daily loss {daily_pnl_pct:.2%} breached limit {-self.cfg.max_daily_loss_pct:.2%}"
                )
                if self.cfg.kill_on_daily_breach:
                    self._arm_kill(reasons[-1])
                    return RiskDecision(RiskVerdict.KILL, 0.0, tuple(reasons))
                return RiskDecision(RiskVerdict.REJECT, 0.0, tuple(reasons))

        dd = state.drawdown(marks)
        if dd >= self.cfg.max_drawdown_pct:
            reasons.append(f"drawdown {dd:.2%} >= limit {self.cfg.max_drawdown_pct:.2%}")
            if self.cfg.kill_on_drawdown_breach:
                self._arm_kill(reasons[-1])
                return RiskDecision(RiskVerdict.KILL, 0.0, tuple(reasons))
            return RiskDecision(RiskVerdict.REJECT, 0.0, tuple(reasons))

        mark = marks.get(order.symbol)
        if mark is None or mark <= 0:
            return RiskDecision(RiskVerdict.REJECT, 0.0, (f"no valid mark for {order.symbol}",))

        current = state.positions.get(order.symbol)
        current_qty = current.qty if current else 0.0
        signed = order.qty if order.side is Side.BUY else -order.qty
        new_qty = current_qty + signed
        max_qty = (self.cfg.max_position_pct * equity) / mark
        if abs(new_qty) > max_qty + 1e-9:
            if order.side is Side.BUY:
                allowed = max(0.0, max_qty - current_qty)
            else:
                allowed = max(0.0, current_qty + max_qty)
            if allowed <= 0:
                reasons.append(
                    f"position limit: |{new_qty:.4f}| > max {max_qty:.4f} ({self.cfg.max_position_pct:.0%} equity)"
                )
                return RiskDecision(RiskVerdict.REJECT, 0.0, tuple(reasons))
            reasons.append(f"reduced to position limit ({allowed:.4f})")
            return RiskDecision(RiskVerdict.REDUCE, allowed, tuple(reasons))

        gross = sum(abs(p.market_value(marks.get(s, p.avg_price))) for s, p in state.positions.items())
        additional = order.qty * mark
        increasing = (current_qty >= 0 and order.side is Side.BUY) or (
            current_qty <= 0 and order.side is Side.SELL
        )
        if increasing and (gross + additional) / equity > self.cfg.max_gross_exposure + 1e-9:
            room = max(0.0, self.cfg.max_gross_exposure * equity - gross)
            allowed = room / mark
            if allowed <= 0:
                reasons.append("gross exposure limit")
                return RiskDecision(RiskVerdict.REJECT, 0.0, tuple(reasons))
            reasons.append(f"reduced for gross exposure ({allowed:.4f})")
            return RiskDecision(RiskVerdict.REDUCE, allowed, tuple(reasons))

        qty = order.qty
        if volatility is not None and volatility > 0 and self.cfg.risk_per_trade_pct > 0:
            risk_budget = self.cfg.risk_per_trade_pct * equity
            stop_dist = 2.0 * volatility * mark
            if stop_dist > 0:
                vol_qty = risk_budget / stop_dist
                if vol_qty < qty:
                    reasons.append(f"vol-sized down {qty:.4f} → {vol_qty:.4f}")
                    qty = vol_qty
                    return RiskDecision(RiskVerdict.REDUCE, qty, tuple(reasons))

        return RiskDecision(RiskVerdict.ALLOW, order.qty, tuple(reasons) if reasons else ("ok",))

    def _arm_kill(self, reason: str) -> None:
        self._killed = True
        self._kill_reason = reason

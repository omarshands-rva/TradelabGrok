"""Configuration loading. YAML + pydantic."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class CostConfig(BaseModel):
    commission_per_share: float = 0.005
    commission_min: float = 1.0
    commission_pct: float = 0.0
    spread_bps: float = 2.0
    slippage_bps: float = 1.0
    impact_coeff: float = 0.0
    adv_fallback: float = 1_000_000.0


class RiskConfig(BaseModel):
    max_position_pct: float = 0.10
    max_gross_exposure: float = 1.0
    max_net_exposure: float = 1.0
    max_daily_loss_pct: float = 0.02
    max_drawdown_pct: float = 0.08
    risk_per_trade_pct: float = 0.005
    kill_on_daily_breach: bool = True
    kill_on_drawdown_breach: bool = True


class EvalConfig(BaseModel):
    train_days: int = 252
    test_days: int = 63
    purge_days: int = 5
    embargo_days: int = 5
    n_monte_carlo: int = 1000
    risk_free_rate: float = 0.0
    periods_per_year: int = 252


class SessionConfig(BaseModel):
    mode: str = "paper"  # paper | live
    journal_dir: str = "runs"
    heartbeat_every: int = 50
    live_venue: str = "unset"  # unset | stub | ib
    # IB (only used when live_venue=ib)
    ib_enabled: bool = False  # MUST flip true intentionally
    ib_host: str = "127.0.0.1"
    ib_port: int = 7497  # 7497 paper, 7496 live — never auto-switch to live
    ib_client_id: int = 1
    ib_account: str = ""
    ib_fill_timeout_sec: float = 15.0


class TradeLabConfig(BaseModel):
    starting_cash: float = 100_000.0
    cost: CostConfig = Field(default_factory=CostConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    eval: EvalConfig = Field(default_factory=EvalConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    symbols: list[str] = Field(default_factory=lambda: ["SPY"])

    @field_validator("starting_cash")
    @classmethod
    def positive_cash(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("starting_cash must be positive")
        return v


def load_config(path: Optional[str | Path] = None) -> TradeLabConfig:
    if path is None:
        return TradeLabConfig()
    p = Path(path)
    data: dict[str, Any] = yaml.safe_load(p.read_text()) or {}
    return TradeLabConfig.model_validate(data)

"""Strategy registry — construct by name from config or CLI."""

from __future__ import annotations

from typing import Any, Callable

from tradelab.strategy.mean_reversion import MeanReversionStrategy
from tradelab.strategy.momentum import MomentumStrategy

STRATEGY_REGISTRY: dict[str, Callable[..., Any]] = {
    "momentum": MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
}


def list_strategies() -> list[str]:
    return sorted(STRATEGY_REGISTRY.keys())


def get_strategy(name: str, **kwargs: Any) -> Any:
    key = name.strip().lower().replace("-", "_")
    if key not in STRATEGY_REGISTRY:
        raise KeyError(f"Unknown strategy '{name}'. Available: {list_strategies()}")
    return STRATEGY_REGISTRY[key](**kwargs)

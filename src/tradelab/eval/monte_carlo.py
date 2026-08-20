"""Monte Carlo path sampling for path-dependence and P(ruin)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True, slots=True)
class PathStats:
    median_final: float
    p5_final: float
    p95_final: float
    mean_max_dd: float
    p95_max_dd: float
    prob_ruin: float  # fraction of paths that hit ruin_threshold


def monte_carlo_paths(
    returns: Sequence[float],
    *,
    n_paths: int = 1000,
    starting_equity: float = 1.0,
    method: str = "bootstrap",
    seed: int | None = 42,
) -> np.ndarray:
    """
    Returns array shape (n_paths, n_periods+1) of equity paths.

    method:
      - bootstrap: sample returns with replacement
      - permute: shuffle order of the observed returns (same set, different path)
    """
    r = np.asarray(returns, dtype=float)
    if len(r) == 0:
        return np.full((n_paths, 1), starting_equity)

    rng = np.random.default_rng(seed)
    n = len(r)
    paths = np.empty((n_paths, n + 1))
    paths[:, 0] = starting_equity

    for i in range(n_paths):
        if method == "permute":
            sample = rng.permutation(r)
        else:
            sample = rng.choice(r, size=n, replace=True)
        paths[i, 1:] = starting_equity * np.cumprod(1.0 + sample)

    return paths


def path_statistics(
    paths: np.ndarray,
    *,
    ruin_threshold: float = 0.5,
) -> PathStats:
    """paths: (n_paths, T)."""
    finals = paths[:, -1]
    peaks = np.maximum.accumulate(paths, axis=1)
    dds = (peaks - paths) / np.where(peaks > 0, peaks, 1.0)
    max_dds = dds.max(axis=1)

    return PathStats(
        median_final=float(np.median(finals)),
        p5_final=float(np.percentile(finals, 5)),
        p95_final=float(np.percentile(finals, 95)),
        mean_max_dd=float(np.mean(max_dds)),
        p95_max_dd=float(np.percentile(max_dds, 95)),
        prob_ruin=float(np.mean(finals < ruin_threshold * paths[:, 0])),
    )

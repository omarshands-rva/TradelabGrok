"""Walk-forward splits with purge + embargo (López de Prado style)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Sequence

import numpy as np


@dataclass(frozen=True, slots=True)
class WalkForwardSplit:
    train_idx: np.ndarray
    test_idx: np.ndarray
    fold: int


def generate_walk_forward_splits(
    n: int,
    *,
    train_size: int,
    test_size: int,
    purge: int = 0,
    embargo: int = 0,
    expanding: bool = False,
) -> Iterator[WalkForwardSplit]:
    """
    Yield successive (train, test) index arrays.

    purge: drop this many bars at the end of train nearest to test (label leakage).
    embargo: drop this many bars after test before next train starts (when non-expanding).
    """
    if train_size < 1 or test_size < 1:
        raise ValueError("train_size and test_size must be positive")
    if n < train_size + test_size:
        return

    fold = 0
    start = 0
    while True:
        if expanding:
            train_end = start + train_size + fold * test_size
        else:
            train_end = start + train_size

        test_start = train_end + purge
        test_end = test_start + test_size

        if test_end > n:
            break

        train_idx = np.arange(0 if expanding else start, max(0, train_end - purge))
        test_idx = np.arange(test_start, test_end)

        if len(train_idx) == 0 or len(test_idx) == 0:
            break

        yield WalkForwardSplit(train_idx=train_idx, test_idx=test_idx, fold=fold)
        fold += 1
        start = test_end + embargo

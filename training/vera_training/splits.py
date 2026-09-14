"""Reproducible ASIN-isolated splits (PRD §13.1, weakness #12).

sklearn has no ``RepeatedGroupKFold`` (the PRD's import does not exist), so
:func:`repeated_group_folds` implements it: 5 folds × 3 repeats = 15 folds.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit


def assert_disjoint(*groups: Iterable[str]) -> None:
    """Raise if any product ASIN appears in more than one group."""
    sets = [set(group) for group in groups]
    for index, left in enumerate(sets):
        for right in sets[index + 1 :]:
            if left & right:
                raise ValueError(f"Product leakage: {len(left & right)} overlapping ASIN(s)")


def holdout(frame: pd.DataFrame, fraction: float, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split rows so ~``fraction`` of PRODUCTS land in the second frame."""
    if not 0 < fraction < 1 or frame.parent_asin.nunique() < 2:
        raise ValueError("A product holdout requires two products and fraction in (0, 1)")
    splitter = GroupShuffleSplit(n_splits=1, test_size=fraction, random_state=seed)
    train, test = next(splitter.split(frame, groups=frame.parent_asin))
    left, right = frame.iloc[train].copy(), frame.iloc[test].copy()
    assert_disjoint(left.parent_asin, right.parent_asin)
    return left.reset_index(drop=True), right.reset_index(drop=True)


def train_cal_test(frame: pd.DataFrame, seed: int = 42) -> dict[str, pd.DataFrame]:
    """60 / 20 / 20 product-grouped train / calibration / test split."""
    development, test = holdout(frame, 0.2, seed)
    train, calibration = holdout(development, 0.25, seed + 1)
    assert_disjoint(train.parent_asin, calibration.parent_asin, test.parent_asin)
    return {"train": train, "calibration": calibration, "test": test}


def repeated_group_folds(
    groups: Iterable[str], n_splits: int = 5, n_repeats: int = 3, seed: int = 42
) -> Iterator[tuple[int, int, np.ndarray, np.ndarray]]:
    """Yield ``(repeat, fold, train_idx, test_idx)``; each product is tested once per repeat."""
    group_array = np.asarray(list(groups))
    unique = np.unique(group_array)
    if n_splits < 2 or n_repeats < 1 or len(unique) < n_splits:
        raise ValueError("Not enough distinct products for requested repeated grouped CV")
    rng = np.random.default_rng(seed)
    for repeat in range(n_repeats):
        # Random partitions of GROUPS, not rows; every group is tested once per repeat.
        for fold, held_groups in enumerate(np.array_split(rng.permutation(unique), n_splits)):
            test = np.flatnonzero(np.isin(group_array, held_groups))
            train = np.flatnonzero(~np.isin(group_array, held_groups))
            assert_disjoint(group_array[train], group_array[test])
            yield repeat, fold, train, test

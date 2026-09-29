"""
Cross-validation utilities for financial machine learning.
Implements Purged K-Fold Cross-Validation with Embargo (López de Prado, 2018).
"""
from typing import Generator, Tuple
import numpy as np


class PurgedKFoldEmbargo:
    """
    Purged K-Fold Cross-Validation with Embargo for financial time-series.
    
    1. Divides unique sorted dates into K contiguous test folds.
    2. Drops training observations that overlap with the test fold label evaluation window.
    3. Adds an 'embargo' window following the test fold to eliminate post-event autoregressive leakage.
    """
    def __init__(self, n_splits: int = 5, embargo_days: int = 5):
        if n_splits < 2:
            raise ValueError(f"n_splits must be >= 2, got {n_splits}")
        self.n_splits = n_splits
        self.embargo_days = max(0, int(embargo_days))

    def split(self, unique_dates: np.ndarray) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Yields (train_indices, test_indices) indexing into unique_dates.
        """
        dates = np.sort(np.asarray(unique_dates))
        n = len(dates)
        if n < self.n_splits:
            raise ValueError(f"Number of unique dates ({n}) must be >= n_splits ({self.n_splits})")

        fold_size = n // self.n_splits
        for k in range(self.n_splits):
            test_start = k * fold_size
            test_end = n if k == self.n_splits - 1 else (k + 1) * fold_size
            
            # Apply purge before test and embargo after test
            embargo_lo = max(0, test_start - self.embargo_days)
            embargo_hi = min(n, test_end + self.embargo_days)
            
            test_idx = np.arange(test_start, test_end)
            train_idx = np.concatenate([
                np.arange(0, embargo_lo),
                np.arange(embargo_hi, n)
            ])
            yield train_idx, test_idx

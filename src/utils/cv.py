"""
Cross-validation utilities for financial machine learning.
Implements Purged K-Fold Cross-Validation with Embargo (López de Prado, 2018).
"""
from typing import Generator, Optional, Tuple
import numpy as np


class PurgedKFoldEmbargo:
    """
    Purged K-Fold Cross-Validation with Embargo for financial time-series.
    
    1. Divides unique sorted dates into K contiguous test folds.
    2. Purges training observations prior to the test fold whose label horizon (t1)
       overlaps with the test fold start date (t0), plus any pre-test purge window.
    3. Adds an 'embargo' window following the test fold to eliminate post-event autoregressive leakage.
    """
    def __init__(self, n_splits: int = 5, embargo_days: int = 5, label_horizon_days: Optional[int] = None):
        if n_splits < 2:
            raise ValueError(f"n_splits must be >= 2, got {n_splits}")
        self.n_splits = n_splits
        self.embargo_days = max(0, int(embargo_days))
        self.label_horizon_days = (
            max(0, int(label_horizon_days))
            if label_horizon_days is not None
            else self.embargo_days
        )

    def split(
        self,
        unique_dates: np.ndarray,
        label_end_dates: Optional[np.ndarray] = None,
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Yields (train_indices, test_indices) indexing into unique_dates.
        If `label_end_dates` (t1 for each date in `unique_dates`) is provided,
        any training date prior to `test_start` whose `label_end_date >= dates[test_start]`
        is also purged in addition to the bar-count purge window.
        """
        dates = np.asarray(unique_dates)
        if len(dates) > 1 and np.any(dates[:-1] > dates[1:]):
            raise ValueError("unique_dates must be sorted in ascending chronological order")
        if len(dates) > 1 and np.any(dates[:-1] == dates[1:]):
            raise ValueError("unique_dates must not contain duplicate dates")

        end_dates = None
        if label_end_dates is not None:
            if len(label_end_dates) != len(unique_dates):
                raise ValueError(
                    f"label_end_dates length ({len(label_end_dates)}) must match unique_dates length ({len(unique_dates)})"
                )
            end_dates = np.asarray(label_end_dates)
            if np.any(end_dates < dates):
                raise ValueError("label_end_dates cannot be earlier than unique_dates (negative horizon)")

        n = len(dates)
        if n < self.n_splits:
            raise ValueError(f"Number of unique dates ({n}) must be >= n_splits ({self.n_splits})")

        fold_size = n // self.n_splits
        purge_bars = max(self.embargo_days, self.label_horizon_days)

        for k in range(self.n_splits):
            test_start = k * fold_size
            test_end = n if k == self.n_splits - 1 else (k + 1) * fold_size
            
            # Apply purge before test and embargo after test
            embargo_lo = max(0, test_start - purge_bars)
            embargo_hi = min(n, test_end + self.embargo_days)
            
            pre_train = np.arange(0, embargo_lo)
            if end_dates is not None and len(pre_train) > 0:
                test_start_dt = dates[test_start]
                pre_train = pre_train[end_dates[pre_train] < test_start_dt]

            test_idx = np.arange(test_start, test_end)
            train_idx = np.concatenate([
                pre_train,
                np.arange(embargo_hi, n)
            ])
            yield train_idx, test_idx


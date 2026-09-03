import logging
from datetime import date
from typing import List, Dict, Any, Tuple, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class LandslideDatasetSplitter:
    """
    Leakage-safe splitting strategies for spatio-temporal hazard datasets.
    Supports Temporal Holdouts and Spatial Group Holdouts.
    """

    @classmethod
    def temporal_split(
        cls,
        df: pd.DataFrame,
        date_column: str = "date",
        train_end_date: Optional[date] = None,
        val_end_date: Optional[date] = None,
        test_ratio: float = 0.20,
        val_ratio: float = 0.15,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Splits dataset chronologically to prevent temporal data leakage.
        Returns (train_df, val_df, test_df).
        """
        df_sorted = df.sort_values(by=date_column).reset_index(drop=True)

        if train_end_date and val_end_date:
            train_mask = df_sorted[date_column] <= train_end_date
            val_mask = (df_sorted[date_column] > train_end_date) & (df_sorted[date_column] <= val_end_date)
            test_mask = df_sorted[date_column] > val_end_date

            train_df = df_sorted[train_mask]
            val_df = df_sorted[val_mask]
            test_df = df_sorted[test_mask]
        else:
            n = len(df_sorted)
            n_test = int(n * test_ratio)
            n_val = int(n * val_ratio)
            n_train = n - n_val - n_test

            train_df = df_sorted.iloc[:n_train]
            val_df = df_sorted.iloc[n_train:n_train + n_val]
            test_df = df_sorted.iloc[n_train + n_val:]

        cls.verify_temporal_leakage_absence(train_df, val_df, test_df, date_column)
        return train_df, val_df, test_df

    @classmethod
    def spatial_group_split(
        cls,
        df: pd.DataFrame,
        group_column: str = "location_id",
        test_groups: Optional[List[str]] = None,
        val_groups: Optional[List[str]] = None,
        test_group_ratio: float = 0.20,
        val_group_ratio: float = 0.15,
        random_seed: int = 42,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Splits dataset by spatial units (stations or districts) to test spatial generalization.
        Returns (train_df, val_df, test_df).
        """
        unique_groups = sorted(list(df[group_column].unique()))
        
        if test_groups and val_groups:
            test_set = set(test_groups)
            val_set = set(val_groups)
            train_set = set(unique_groups) - test_set - val_set
        else:
            import random
            rng = random.Random(random_seed)
            shuffled = list(unique_groups)
            rng.shuffle(shuffled)

            n = len(shuffled)
            n_test = max(1, int(n * test_group_ratio))
            n_val = max(1, int(n * val_group_ratio))

            test_set = set(shuffled[:n_test])
            val_set = set(shuffled[n_test:n_test + n_val])
            train_set = set(shuffled[n_test + n_val:])

        train_df = df[df[group_column].isin(train_set)].reset_index(drop=True)
        val_df = df[df[group_column].isin(val_set)].reset_index(drop=True)
        test_df = df[df[group_column].isin(test_set)].reset_index(drop=True)

        # Verify zero spatial overlap
        assert not (train_set & test_set), "Spatial leakage detected between train and test groups!"
        assert not (train_set & val_set), "Spatial leakage detected between train and val groups!"

        logger.info(
            f"Spatial split created: {len(train_set)} train groups ({len(train_df)} rows), "
            f"{len(val_set)} val groups ({len(val_df)} rows), "
            f"{len(test_set)} test groups ({len(test_df)} rows)."
        )
        return train_df, val_df, test_df

    @staticmethod
    def verify_temporal_leakage_absence(
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        test_df: pd.DataFrame,
        date_column: str = "date",
    ):
        """
        Validates that no future date leaks into training sets.
        """
        if train_df.empty or test_df.empty:
            return

        max_train_date = train_df[date_column].max()
        if not val_df.empty:
            min_val_date = val_df[date_column].min()
            if max_train_date >= min_val_date:
                raise ValueError(
                    f"Temporal leakage detected: max train date ({max_train_date}) >= min val date ({min_val_date})"
                )

            max_val_date = val_df[date_column].max()
            min_test_date = test_df[date_column].min()
            if max_val_date >= min_test_date:
                raise ValueError(
                    f"Temporal leakage detected: max val date ({max_val_date}) >= min test date ({min_test_date})"
                )
        else:
            min_test_date = test_df[date_column].min()
            if max_train_date >= min_test_date:
                raise ValueError(
                    f"Temporal leakage detected: max train date ({max_train_date}) >= min test date ({min_test_date})"
                )

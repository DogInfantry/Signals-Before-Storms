"""Causal feature engineering: momentum, realized vol, VIX, macro. Plan phase 2.

Every feature here is computable using only information dated at or before each row's
timestamp. Standardization is deliberately NOT done here; it happens inside each
walk-forward fold using train-only statistics.
"""

from __future__ import annotations

import pandas as pd


def add_momentum(df: pd.DataFrame, price_col: str, windows: list[int]) -> pd.DataFrame:
    raise NotImplementedError("phase 2")


def add_realized_vol(df: pd.DataFrame, ret_col: str, windows: list[int]) -> pd.DataFrame:
    raise NotImplementedError("phase 2")


def build_features(master: pd.DataFrame, cfg) -> pd.DataFrame:
    """Assemble the full causal feature matrix for the regime model."""
    raise NotImplementedError("phase 2")

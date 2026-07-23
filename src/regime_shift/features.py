"""Causal feature engineering: momentum, realized vol, VIX, macro. Plan phase 2.

Every feature here is computable using only information dated at or before each row's
timestamp. Standardization is deliberately NOT done here; it happens inside each
walk-forward fold using train-only statistics.
"""

from __future__ import annotations

import pandas as pd

_ANNUALIZE = 252**0.5  # daily -> annual vol scaling
_RETURN_COLS = ("equity_ret", "bond_ret", "gold_ret")


def add_momentum(df: pd.DataFrame, ret_col: str, windows: list[int]) -> pd.DataFrame:
    """Cumulative log return over each lookback window: mom_w[t] = sum(ret[t-w+1 .. t]).

    Equivalent to log(P_t / P_{t-w}) since the input is log-returns. Right-aligned
    rolling means each value depends only on rows at or before t (causal). Mutates and
    returns df.
    """
    for w in windows:
        df[f"mom_{w}"] = df[ret_col].rolling(w).sum()
    return df


def add_realized_vol(df: pd.DataFrame, ret_col: str, windows: list[int]) -> pd.DataFrame:
    """Annualized realized volatility (rolling std of returns * sqrt(252)) per window.

    Right-aligned rolling, so causal. Mutates and returns df.
    """
    for w in windows:
        df[f"vol_{w}"] = df[ret_col].rolling(w).std() * _ANNUALIZE
    return df


def build_features(master: pd.DataFrame, cfg) -> pd.DataFrame:
    """Assemble the full causal feature matrix for the regime model.

    Features: equity momentum + equity realized vol (windows from config), VIX level and
    its 1-day change, and any macro columns passed through as-is (build_master already
    forward-filled and lagged them). No standardization here; that happens train-only
    inside each walk-forward fold. Leading NaNs from the longest window are dropped.
    """
    if "equity_ret" not in master.columns:
        raise ValueError("master must contain 'equity_ret' for momentum/vol features")

    feats = master[["equity_ret"]].copy()
    add_momentum(feats, "equity_ret", cfg.features["momentum_windows"])
    add_realized_vol(feats, "equity_ret", cfg.features["vol_windows"])
    # ponytail: momentum/vol on equity only (the regime-defining asset). Per-asset is a
    # loop over _RETURN_COLS if the HMM ever needs bond/gold dynamics too.

    if "vix" in master.columns:
        feats["vix"] = master["vix"]
        feats["vix_chg"] = master["vix"].diff()

    macro_cols = [c for c in master.columns if c not in _RETURN_COLS and c != "vix"]
    for c in macro_cols:
        feats[c] = master[c]

    return feats.drop(columns="equity_ret").dropna()

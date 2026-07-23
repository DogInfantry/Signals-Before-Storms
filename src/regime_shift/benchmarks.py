"""Static benchmarks: 60/40 and equal-weight, plus a rule-based regime ablation. Phase 7.

Every benchmark runs through backtest.run_book, so it pays the same entry, drift and turnover
costs the regime strategy pays. A benchmark costed on different terms is not a benchmark.

The ablation is the honest control for the whole project: same optimizer, same costs, same
walk-forward span, but the regimes come from a trailing-vol rule instead of the HMM. If the HMM
cannot beat that, the HMM is decoration.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from regime_shift.backtest import asset_cols, run_book

SIXTY_FORTY = {"equity_ret": 0.6, "bond_ret": 0.4}


def _fixed_vector(cols: list[str], target: dict[str, float] | None) -> np.ndarray:
    """Target weights over the columns that actually exist, renormalized to be fully invested.

    India has no bond sleeve yet, so 60/40 there collapses to 100% equity rather than silently
    holding 60% and 40% cash.
    """
    if target is None:
        return np.full(len(cols), 1.0 / len(cols))
    w = np.array([float(target.get(c, 0.0)) for c in cols])
    if w.sum() <= 0:
        raise ValueError(f"target {target} shares no column with {cols}")
    return w / w.sum()


def static_book(
    returns: pd.DataFrame,
    dates,
    cfg,
    target: dict[str, float] | None = None,
    rebalance: str = "monthly",
) -> pd.DataFrame:
    """Constant-target benchmark over `dates`.

    target None means equal weight. rebalance "monthly" trades back to target at the first close
    of each month (paying for the drift it undoes); "never" buys once and lets it ride.
    """
    cols = asset_cols(returns)
    w = _fixed_vector(cols, target)
    month = None

    def decide(t):
        nonlocal month
        trade = month is None or (rebalance == "monthly" and t.month != month)
        month = t.month
        return None, (w if trade else None)

    return run_book(returns[cols].astype(float), dates, decide, cfg)


def equal_weight(returns: pd.DataFrame, dates, cfg, **kwargs) -> pd.DataFrame:
    """1/N across whatever assets exist."""
    return static_book(returns, dates, cfg, target=None, **kwargs)


def sixty_forty(returns: pd.DataFrame, dates, cfg, **kwargs) -> pd.DataFrame:
    """The classic 60% equity / 40% bond book."""
    return static_book(returns, dates, cfg, target=SIXTY_FORTY, **kwargs)


def vol_rule_regimes(
    returns: pd.DataFrame,
    cfg,
    window: int = 21,
    lookback: int = 252,
    quantile: float = 0.8,
) -> pd.Series:
    """Rule-based regime labels: risk-off when trailing realized vol clears its own trailing
    quantile, calm otherwise. No HMM, no fitting, nothing to leak.

    Rolling windows are right-aligned, so the label at t uses only data up to t. Feed the result
    to backtest.run_backtest (sliced to the HMM's OOS index) for a like-for-like ablation.
    """
    eq = returns["equity_ret"].astype(float)
    vol = eq.rolling(window).std()
    thresh = vol.rolling(lookback).quantile(quantile)
    labels = pd.Series(0, index=eq.index, name="regime")
    labels[vol > thresh] = cfg.hmm.n_states - 1
    return labels[thresh.notna()].astype(int)

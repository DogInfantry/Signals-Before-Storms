"""Phase 7 tests for performance metrics.

Core ratios are checked against closed form or hand-computed paths, not against another
implementation of themselves. The PSR/DSR checks assert the properties that make those numbers
worth reporting: more evidence raises PSR, more searching lowers DSR. Synthetic, seeded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from regime_shift.backtest import run_book
from regime_shift.config import load_config
from regime_shift.metrics import (
    ann_return,
    ann_vol,
    bootstrap_ci,
    calmar,
    deflated_sharpe,
    expected_max_sharpe,
    max_drawdown,
    optimal_block_length,
    probabilistic_sharpe,
    sharpe,
    sortino,
    summary,
)


def _returns(seed: int = 0, n: int = 1260) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0004, 0.010, n)


def test_ann_return_and_vol_match_closed_form():
    r = np.full(252, 0.001)
    assert abs(ann_return(r) - (1.001**252 - 1.0)) < 1e-12
    assert ann_vol(r) < 1e-15  # a constant series has no dispersion beyond float noise

    r = _returns()
    assert abs(ann_vol(r) - r.std(ddof=1) * np.sqrt(252)) < 1e-12


def test_sharpe_matches_manual_and_scales_with_rf():
    r = _returns()
    assert abs(sharpe(r) - r.mean() / r.std(ddof=1) * np.sqrt(252)) < 1e-12
    assert sharpe(r, rf=0.05) < sharpe(r)  # charging a risk-free rate can only lower it


def test_max_drawdown_and_calmar_on_a_hand_built_path():
    r = np.array([0.10, -0.20, 0.05])  # equity 1.10 -> 0.88 -> 0.924, peak was 1.10
    assert abs(max_drawdown(r) - (0.88 / 1.10 - 1.0)) < 1e-12
    assert abs(calmar(r) - ann_return(r) / abs(max_drawdown(r))) < 1e-12


def test_sortino_beats_sharpe_when_the_downside_is_thin():
    # rare large gains, frequent tiny losses: total vol is dominated by the upside
    r = np.full(252, -0.001)
    r[::10] = 0.02
    assert sortino(r) > sharpe(r)


def test_psr_rises_with_more_of_the_same_evidence():
    r = _returns(n=252)
    long_run = np.tile(r, 5)  # identical mean, std, skew and kurtosis, five times the sample
    assert 0.0 <= probabilistic_sharpe(r) <= 1.0
    assert probabilistic_sharpe(long_run) > probabilistic_sharpe(r)


def test_deflated_sharpe_charges_for_the_search():
    r = _returns()
    assert expected_max_sharpe(50, 0.5) > expected_max_sharpe(5, 0.5) > 0.0
    assert expected_max_sharpe(1, 0.5) == 0.0  # one trial is not a search
    assert deflated_sharpe(r, 50, 0.5) < probabilistic_sharpe(r)


def test_optimal_block_length_tracks_persistence():
    rng = np.random.default_rng(3)
    n = 2000
    iid = rng.normal(size=n)
    shocks = rng.normal(size=n)
    ar = np.zeros(n)
    for i in range(1, n):
        ar[i] = 0.9 * ar[i - 1] + shocks[i]  # heavily persistent, needs long blocks

    assert optimal_block_length(iid) < 10.0  # nothing to preserve, so barely block at all
    assert optimal_block_length(ar) > 3 * optimal_block_length(iid)


def test_bootstrap_ci_brackets_the_point_estimate():
    r = _returns()
    lo, hi = bootstrap_ci(r, n_boot=300, seed=1)  # block length chosen from the data
    assert lo < sharpe(r) < hi

    # a hand-pinned block must still work, and a longer one cannot tighten the interval much
    pinned_lo, pinned_hi = bootstrap_ci(r, n_boot=300, seed=1, mean_block=21)
    assert pinned_lo < sharpe(r) < pinned_hi


def test_summary_reports_the_book_columns():
    cfg = load_config()
    idx = pd.bdate_range("2015-01-02", periods=252)
    rets = pd.DataFrame({"a_ret": np.full(252, 0.0004), "b_ret": np.full(252, 0.0002)}, index=idx)
    entry = np.array([0.5, 0.5])
    book = run_book(rets, idx, lambda t: (None, entry if t == idx[0] else None), cfg)

    s = summary(book)
    assert set(s.index) >= {"ann_return", "sharpe", "max_drawdown", "turnover_ann", "cost_drag_ann"}
    assert abs(s["turnover_ann"] - 1.0) < 1e-9  # one entry trade across exactly one year

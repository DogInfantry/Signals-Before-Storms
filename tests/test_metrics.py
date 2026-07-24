"""Phase 7 tests for performance metrics.

Core ratios are checked against closed form or hand-computed paths, not against another
implementation of themselves. The PSR/DSR checks assert the properties that make those numbers
worth reporting: more evidence raises PSR, more searching lowers DSR. Synthetic, seeded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from regime_shift.backtest import run_book
from regime_shift.config import load_config
from regime_shift.metrics import (
    ann_return,
    ann_vol,
    bootstrap_ci,
    calmar,
    deflated_sharpe,
    episode_profile,
    expected_max_sharpe,
    label_profile,
    max_drawdown,
    optimal_block_length,
    paired_bootstrap,
    probabilistic_sharpe,
    sharpe,
    sortino,
    subperiod_summary,
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


def test_paired_bootstrap_uses_the_pairing():
    """The pairing is the whole point, and it is what would break silently.

    Comparing correlated books on independently resampled dates throws away the correlation and
    inflates the interval, which is the error this function exists to avoid. Both assertions below
    fail if the two series are ever resampled with different indices.
    """
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2016-01-01", periods=800)
    a = pd.Series(rng.normal(0.0004, 0.01, 800), index=idx)

    # a book against itself: the difference is identically zero on every replicate
    lo, hi = paired_bootstrap(a, a, n_boot=400)
    assert lo <= 0.0 <= hi
    assert hi - lo < 1e-9

    # same book plus a steady edge: the difference is real and the interval must exclude zero,
    # even though the two marginal Sharpe intervals overlap almost entirely
    b = a + 0.0004
    lo, hi = paired_bootstrap(b, a, n_boot=400)
    assert lo > 0.0

    marg_b = bootstrap_ci(b, n_boot=400)
    marg_a = bootstrap_ci(a, n_boot=400)
    assert marg_b[0] < marg_a[1], "marginals should overlap; that is exactly why pairing matters"

    with pytest.raises(ValueError, match="shared index"):
        paired_bootstrap(a, a.iloc[:-5])


def test_paired_interval_brackets_its_own_point_estimate():
    """A percentile interval that excludes its own point estimate is reporting a different
    quantity, and that failure is invisible unless it is asserted.

    It happened for real here: the driver bootstrapped raw returns while the point estimates used
    rf-excess returns. Sharpe is not translation invariant, so the interval drifted off the
    estimate entirely and produced confident, wrong verdicts.
    """
    rng = np.random.default_rng(3)
    idx = pd.bdate_range("2016-01-01", periods=700)
    rf_daily = 0.0379 / 252
    a = pd.Series(rng.normal(0.0006, 0.004, 700), index=idx)
    b = pd.Series(rng.normal(0.0009, 0.011, 700), index=idx)

    for x, y in ((a, b), (a - rf_daily, b - rf_daily)):
        point = sharpe(x) - sharpe(y)
        lo, hi = paired_bootstrap(x, y, n_boot=600)
        assert lo <= point <= hi, f"CI ({lo:.3f}, {hi:.3f}) excludes point {point:.3f}"


def test_subperiod_summary_partitions_the_window():
    cfg = load_config()
    # long enough to actually reach the post-COVID block; a fixture that stops in 2020 would
    # silently test two blocks and pass
    n = 780
    idx = pd.bdate_range("2019-01-01", periods=n)
    rets = pd.DataFrame({"equity_ret": np.full(n, 0.0004)}, index=idx)
    book = run_book(rets, idx, lambda t: (None, np.array([1.0])), cfg)

    splits = [
        ("pre", "2019-01-01", "2020-02-14"),
        ("covid", "2020-02-15", "2020-12-31"),
        ("post", "2021-01-01", "2021-12-31"),
    ]
    table = subperiod_summary({"only": book}, splits)

    assert list(table.index.get_level_values("period")) == ["pre", "covid", "post"]
    # the blocks tile the window exactly: no day double counted, none dropped
    assert table["days"].sum() == len(book)
    assert (table["days"] > 0).all()


def test_episode_profile_drops_the_largest_episode():
    """The check that retracted this project's apparent directional-regime finding.

    Label 1 here is deliberately built to look like that result: one long losing episode and one
    short winning one. Pooled over days it reads negative; drop the longest episode and it flips
    positive, which is the signature of a state whose whole reputation is a single event.
    """
    n = 40
    idx = pd.bdate_range("2020-01-01", periods=n)
    # equity_ret is a LOG return series, and episode_profile scores master.shift(-1)
    rets = np.full(n, 0.001)
    rets[1:21] = -0.004  # the long losing episode's forward returns
    rets[25:30] = 0.010  # the short winning one's
    master = pd.DataFrame({"equity_ret": rets}, index=idx)

    labels = pd.Series(0, index=idx)
    labels.iloc[0:20] = 1  # 20-day episode
    labels.iloc[24:29] = 1  # 5-day episode
    prof = episode_profile(labels, master)

    assert prof.loc[1, "episodes"] == 2
    assert prof.loc[1, "days"] == 25
    assert prof.loc[1, "neg_episodes"] == 1
    assert prof.loc[1, "ann_ret"] < 0  # pooled over days the state looks directional
    assert prof.loc[1, "ann_ret_ex_largest"] > 0  # one event was carrying it

    # label_profile now carries the same episode count, so the day count is never read alone
    assert label_profile(labels, master).loc[1, "episodes"] == 2


def test_summary_reports_the_book_columns():
    cfg = load_config()
    idx = pd.bdate_range("2015-01-02", periods=252)
    rets = pd.DataFrame({"a_ret": np.full(252, 0.0004), "b_ret": np.full(252, 0.0002)}, index=idx)
    entry = np.array([0.5, 0.5])
    book = run_book(rets, idx, lambda t: (None, entry if t == idx[0] else None), cfg)

    s = summary(book)
    assert set(s.index) >= {"ann_return", "sharpe", "max_drawdown", "turnover_ann", "cost_drag_ann"}
    assert abs(s["turnover_ann"] - 1.0) < 1e-9  # one entry trade across exactly one year

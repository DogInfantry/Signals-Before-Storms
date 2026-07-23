"""Tests for the data-quality guard.

Only the pure helper is tested; loading needs the network. The case being pinned is real:
GOLDBEES.NS on Yahoo prints a 100x round trip over 2019-12-19 to 2019-12-23, and left in place it
inflates gold's return standard deviation from ~0.01 to 0.139.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from regime_shift.data import drop_return_outliers


def _returns() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2015-01-02", periods=200)
    return pd.DataFrame(
        {
            "equity_ret": rng.normal(0.0004, 0.010, 200),
            "gold_ret": rng.normal(0.0002, 0.008, 200),
        },
        index=idx,
    )


def test_vendor_spike_is_dropped_and_announced():
    df = _returns()
    df.iloc[100, df.columns.get_loc("gold_ret")] = -4.6065  # price /100
    df.iloc[102, df.columns.get_loc("gold_ret")] = 4.6052  # and back again

    with pytest.warns(UserWarning, match="gold_ret"):
        cleaned = drop_return_outliers(df, max_abs=0.5)

    assert cleaned["gold_ret"].isna().sum() == 2
    assert cleaned["equity_ret"].notna().all()  # the good column is untouched
    assert cleaned.dropna()["gold_ret"].std() < 0.02  # sane again once the rows are dropped


def test_clean_data_passes_through_untouched():
    df = _returns()
    pd.testing.assert_frame_equal(drop_return_outliers(df, max_abs=0.5), df)


def test_a_real_crash_survives_the_guard():
    df = _returns()
    df.iloc[50, df.columns.get_loc("equity_ret")] = -0.13  # Mar-2020 scale move, not an error
    assert drop_return_outliers(df, max_abs=0.5).notna().all().all()

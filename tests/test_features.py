"""Phase 2 tests for causal feature engineering.

The flagship guard is a leak-proof property test: a feature value at time t must be
identical whether or not future rows exist. Right-aligned rolling windows guarantee
this; the test would fail immediately if any feature were centered or forward-looking.
All data here is synthetic and seeded, so the test is offline and deterministic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from regime_shift.config import load_config
from regime_shift.features import build_features


def _synthetic_master(n: int = 400, seed: int = 0) -> pd.DataFrame:
    """A build_master-shaped frame: log-returns, VIX level, one macro column."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-02", periods=n)
    return pd.DataFrame(
        {
            "equity_ret": rng.normal(0, 0.01, n),
            "bond_ret": rng.normal(0, 0.005, n),
            "gold_ret": rng.normal(0, 0.008, n),
            "vix": 15 + np.abs(rng.normal(0, 3, n)),
            "NFCI": rng.normal(0, 1, n),
        },
        index=idx,
    )


def test_features_are_leak_proof():
    """Features on a prefix must match features on the full series, date for date."""
    cfg = load_config()
    master = _synthetic_master()

    full = build_features(master, cfg)
    prefix = build_features(master.iloc[:300], cfg)

    common = full.index.intersection(prefix.index)
    assert len(common) > 0, "no overlapping dates to compare"
    pd.testing.assert_frame_equal(full.loc[common], prefix.loc[common])


def test_feature_columns_and_no_nan():
    cfg = load_config()
    feats = build_features(_synthetic_master(), cfg)

    expected = (
        [f"mom_{w}" for w in cfg.features["momentum_windows"]]
        + [f"vol_{w}" for w in cfg.features["vol_windows"]]
        + ["vix", "vix_chg", "NFCI"]
    )
    assert list(feats.columns) == expected
    assert not feats.isna().any().any(), "dropna should leave a fully dense matrix"
    # longest window is the binding constraint; rolling(w) leaves w-1 leading NaNs
    assert len(feats) == 400 - (max(cfg.features["momentum_windows"]) - 1)

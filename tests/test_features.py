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
    """A build_master-shaped frame: log-returns, VIX level, one macro column.

    Carries BOTH bond_ret and cash_ret so every role in data._ASSET_ROLES is represented. A
    role the feature builder forgets to exclude is silently promoted to a state variable, and
    only a fixture holding all four roles can catch that.
    """
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-02", periods=n)
    return pd.DataFrame(
        {
            "equity_ret": rng.normal(0, 0.01, n),
            "bond_ret": rng.normal(0, 0.005, n),
            "cash_ret": rng.normal(0.0002, 0.0001, n),
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
    # No raw asset return survives as a state variable. cash_ret is the one that actually got
    # through once: it is not in the macro list, not an equity feature, and India is the only
    # universe carrying it, so it gave that universe a feature the US never saw.
    assert not any(c.endswith("_ret") for c in feats.columns), (
        f"raw asset returns leaked into the feature matrix: {list(feats.columns)}"
    )
    assert not feats.isna().any().any(), "dropna should leave a fully dense matrix"
    # longest window is the binding constraint; rolling(w) leaves w-1 leading NaNs
    assert len(feats) == 400 - (max(cfg.features["momentum_windows"]) - 1)


def test_macro_widens_the_matrix_so_the_model_master_must_exclude_it():
    """The published feature matrix is 9 columns, and one macro column would make it 10.

    Every number in the README was fitted on 9 features per universe. Macro passthrough is a
    real capability, but it is also the mechanism that once gave India a 10th feature via
    cash_ret. FRED being unreachable is what kept that from happening again while the entry
    points still requested macro; now that FRED answers, only the entry points building a
    macro-free model master keep the results reproducible. This pins both halves.
    """
    cfg = load_config()
    master = _synthetic_master()

    model_feats = build_features(master.drop(columns="NFCI"), cfg)
    assert len(model_feats.columns) == 9, list(model_feats.columns)

    with_macro = build_features(master, cfg)
    assert list(with_macro.columns) == [*model_feats.columns, "NFCI"]

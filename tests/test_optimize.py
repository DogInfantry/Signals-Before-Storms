"""Phase 5 tests for per-regime convex optimization.

Checks the constraints hold (long-only, budget, cap), that each regime objective behaves as
intended (min-variance tilts to the calm asset, defensive caps equity), and that the
regime_weights dispatch returns a valid portfolio for every canonical label. Synthetic,
seeded, offline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from regime_shift.config import load_config
from regime_shift.optimize import (
    defensive_weights,
    ledoit_wolf_cov,
    max_sharpe_weights,
    min_variance_weights,
    regime_weights,
    shrink_mu,
)

_COLS = ["equity_ret", "bond_ret", "gold_ret"]


def _returns(seed: int = 0, n: int = 750) -> pd.DataFrame:
    """equity: high vol / high mean, bond: low vol, gold: mid. Distinct enough to be legible."""
    rng = np.random.default_rng(seed)
    data = np.column_stack(
        [
            rng.normal(0.0010, 0.012, n),  # equity
            rng.normal(0.0002, 0.003, n),  # bond (calmest)
            rng.normal(0.0005, 0.008, n),  # gold
        ]
    )
    idx = pd.bdate_range("2015-01-02", periods=n)
    return pd.DataFrame(data, columns=_COLS, index=idx)


def _valid(w, cap):
    assert np.all(w >= -1e-6)  # long-only
    assert abs(w.sum() - 1.0) < 1e-6  # fully invested
    assert w.max() <= cap + 1e-6  # weight cap


def test_min_variance_prefers_calmest_asset():
    R = _returns()
    w = min_variance_weights(ledoit_wolf_cov(R), weight_cap=0.6)
    _valid(w, 0.6)
    assert np.argmax(w) == _COLS.index("bond_ret")  # lowest-vol asset gets the most weight


def test_max_sharpe_respects_cap_and_is_invested():
    R = _returns()
    w = max_sharpe_weights(shrink_mu(R), ledoit_wolf_cov(R), weight_cap=0.6)
    _valid(w, 0.6)


def test_max_sharpe_falls_back_when_no_positive_mean():
    R = _returns()
    cov = ledoit_wolf_cov(R)
    neg_mu = np.full(3, -0.001)  # ratio ill-posed -> should return min-variance
    w = max_sharpe_weights(neg_mu, cov, weight_cap=0.6)
    np.testing.assert_allclose(w, min_variance_weights(cov, 0.6), atol=1e-6)


def test_defensive_caps_equity():
    R = _returns()
    w = defensive_weights(ledoit_wolf_cov(R), _COLS, weight_cap=0.6, equity_cap=0.1)
    _valid(w, 0.6)
    assert w[_COLS.index("equity_ret")] <= 0.1 + 1e-6


def test_regime_weights_dispatch_valid_for_all_labels():
    cfg = load_config()  # n_states 3, weight_cap 0.6
    R = _returns()
    for regime in range(cfg.hmm.n_states):
        w = regime_weights(regime, R, cfg)
        assert list(w.index) == _COLS
        _valid(w.to_numpy(), cfg.weight_cap)
    # crisis (highest label) must hold less equity than bull (lowest)
    bull = regime_weights(0, R, cfg)["equity_ret"]
    crisis = regime_weights(cfg.hmm.n_states - 1, R, cfg)["equity_ret"]
    assert crisis < bull

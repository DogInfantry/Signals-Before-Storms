"""Phase 3 tests for the regime engine.

Covers the three things a naive HMM wrapper gets wrong:
  - causal decode is leak-proof (a label at t is byte-identical with or without future rows),
  - canonical labels are stable and ordered by risk (defusing label switching),
  - dwell-time diagnostics are correct.

Synthetic two-regime data (calm vs turbulent), seeded, so the test is offline and deterministic.
"""

from __future__ import annotations

import numpy as np

from regime_shift.regime import RegimeModel, dwell_times


def _two_regime_data(seed: int = 0):
    """Alternating calm/turbulent blocks; returns (X, rank_by, true_labels).

    Calm  = tiny vol, slight positive drift.  Turbulent = 10x vol, negative drift.
    Feature matrix is [return, |return|] so the vol signal is explicit and separable.
    """
    rng = np.random.default_rng(seed)
    blocks, true = [], []
    for regime in [0, 1, 0, 1, 0]:  # 5 blocks of 200
        if regime == 0:
            r = rng.normal(0.0008, 0.003, 200)
        else:
            r = rng.normal(-0.0020, 0.030, 200)
        blocks.append(r)
        true.append(np.full(200, regime))
    ret = np.concatenate(blocks)
    true_labels = np.concatenate(true)
    X = np.column_stack([ret, np.abs(ret)])
    rank_by = np.abs(ret)  # risk proxy: turbulent rows rank higher
    return X, rank_by, true_labels


def test_causal_decode_is_leak_proof():
    X, rank_by, _ = _two_regime_data()
    model = RegimeModel(engine="hmm", n_states=2, random_state=42).fit(X, rank_by=rank_by)

    full = model.decode_causal(X)
    prefix = model.decode_causal(X[:600])

    # a causal label at t must not change when future rows are appended
    np.testing.assert_array_equal(full[:600], prefix)


def test_labels_are_stable_and_risk_ordered():
    X, rank_by, true = _two_regime_data()
    model = RegimeModel(engine="hmm", n_states=2, random_state=42).fit(X, rank_by=rank_by)
    labels = model.decode(X)

    calm = labels[true == 0]
    turbulent = labels[true == 1]
    # canonical 0 = calmest; the calm block should be mostly 0, turbulent mostly 1
    assert np.median(calm) == 0
    assert np.median(turbulent) == 1


def test_transition_matrix_is_stochastic():
    X, rank_by, _ = _two_regime_data()
    model = RegimeModel(engine="hmm", n_states=2, random_state=42).fit(X, rank_by=rank_by)
    P = model.transition_matrix()
    assert P.shape == (2, 2)
    np.testing.assert_allclose(P.sum(axis=1), 1.0, atol=1e-9)


def test_dwell_times_run_lengths():
    labels = np.array([0, 0, 0, 1, 1, 0])
    dwell = dwell_times(labels)
    assert dwell == {0: 2.0, 1: 2.0}  # state 0 runs [3, 1] -> mean 2.0; state 1 run [2] -> 2.0

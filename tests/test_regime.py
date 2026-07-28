"""Phase 3 tests for the regime engine.

Covers the three things a naive HMM wrapper gets wrong:
  - causal decode is leak-proof (a label at t is byte-identical with or without future rows),
  - canonical labels are stable and ordered by risk (defusing label switching),
  - dwell-time diagnostics are correct.

Synthetic two-regime data (calm vs turbulent), seeded, so the test is offline and deterministic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from regime_shift.regime import RegimeModel, dwell_times, label_episodes


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


def test_filtered_proba_is_canonical_and_agrees_with_decode_causal():
    """The posterior and the label must speak the SAME label space.

    A posterior left in raw state order still sums to 1 and still passes every shape and range
    check, so nothing downstream would complain: a monitor would report 90% confidence in the
    wrong regime. Negating rank_by reverses _canonical_order deterministically, so the second
    pass forces a non-identity permutation rather than hoping the seed happens to supply one.
    """
    X, rank_by, _ = _two_regime_data()
    for rank in (rank_by, -rank_by):
        model = RegimeModel(engine="hmm", n_states=2, random_state=42).fit(X, rank_by=rank)
        proba = model.filtered_proba(X)

        assert proba.shape == (X.shape[0], 2)
        assert (proba >= 0).all()
        np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-12)
        np.testing.assert_array_equal(proba.argmax(axis=1), model.decode_causal(X))


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


def test_label_episodes_counts_runs_not_rows():
    """Episodes, not days, are the sample size behind any regime claim.

    Single-day runs at the first and last position are here on purpose: that is where off-by-one
    errors in run detection hide, and a miscounted episode silently inflates the apparent
    evidence for a state.
    """
    labels = pd.Series(
        [2, 0, 0, 0, 1, 1, 2, 2, 2, 2, 0],
        index=pd.bdate_range("2020-01-01", periods=11),
    )
    eps = label_episodes(labels)

    assert list(eps["label"]) == [2, 0, 1, 2, 0]
    assert list(eps["days"]) == [1, 3, 2, 4, 1]
    assert eps["days"].sum() == len(labels)
    assert eps.iloc[0]["start"] == eps.iloc[0]["end"] == labels.index[0]  # leading single day
    assert eps.iloc[-1]["start"] == eps.iloc[-1]["end"] == labels.index[-1]  # trailing single day

    # label 2 spans 5 days but only 2 episodes, which is the whole point
    lab2 = eps[eps["label"] == 2]
    assert len(lab2) == 2
    assert lab2["days"].sum() == 5

    assert label_episodes(pd.Series([], dtype=float)).empty


def test_dwell_times_run_lengths():
    labels = np.array([0, 0, 0, 1, 1, 0])
    dwell = dwell_times(labels)
    assert dwell == {0: 2.0, 1: 2.0}  # state 0 runs [3, 1] -> mean 2.0; state 1 run [2] -> 2.0


def test_jump_engine_ranks_and_decodes_causally():
    """The second engine is optional, so skip when it is absent, but pin the contract when it is
    installed: same canonical ordering, and a causal decode via predict_online."""
    pytest.importorskip("jumpmodels")
    X, rank_by, true = _two_regime_data()
    X = (X - X.mean(axis=0)) / X.std(axis=0)  # the walk-forward standardizes train-only too
    # jump_penalty is scale-dependent. On this 2-feature fixture the default of 50 collapses to a
    # single state (survivable since _canonical_order pads the order, but it tests nothing) while
    # below ~1 the labels switch too freely to track the true regime. 5 separates it cleanly.
    model = RegimeModel(engine="jump", n_states=2, random_state=42, jump_penalty=5.0).fit(
        X, rank_by=rank_by
    )

    labels = model.decode_causal(X)
    assert labels.shape == (X.shape[0],)
    assert set(np.unique(labels)) <= {0, 1}
    assert np.median(labels[true == 0]) == 0  # canonical 0 is still the calmest state
    assert np.median(labels[true == 1]) == 1
    # jump models exist to suppress switching, so they should be at least as sticky as the HMM
    hmm = RegimeModel(engine="hmm", n_states=2, random_state=42).fit(X, rank_by=rank_by)
    assert np.mean(np.diff(labels) != 0) <= np.mean(np.diff(hmm.decode_causal(X)) != 0) + 1e-9

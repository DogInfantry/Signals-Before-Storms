"""Phase 4 tests for the expanding walk-forward.

Asserts the two leak guards the plan calls out: train/test are disjoint and expanding, and
the orchestration end-to-end produces sane out-of-sample regime labels (calm dates rank
below turbulent). Synthetic, seeded, offline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from regime_shift.config import load_config
from regime_shift.walkforward import expanding_walk_forward_splits, run_walk_forward


def test_splits_disjoint_and_expanding():
    splits = list(expanding_walk_forward_splits(500, 252, 63, 63))
    prev_train_len = 0
    for train, test in splits:
        assert train[0] == 0
        assert train[-1] < test[0]  # disjoint: all train strictly before all test
        assert len(train) >= prev_train_len  # expanding window
        assert len(test) <= 63
        prev_train_len = len(train)
    assert splits[-1][1][-1] == 499  # coverage runs to the last row


def _two_regime_features(seed: int = 0, n: int = 800):
    rng = np.random.default_rng(seed)
    blocks, true = [], []
    for regime in [0, 1, 0, 1, 0]:  # 5 blocks of 160
        sigma = 0.003 if regime == 0 else 0.030
        drift = 0.0008 if regime == 0 else -0.0020
        blocks.append(rng.normal(drift, sigma, n // 5))
        true.append(np.full(n // 5, regime))
    ret = np.concatenate(blocks)
    idx = pd.bdate_range("2015-01-02", periods=len(ret))
    feats = pd.DataFrame({"ret": ret, "vol_21": np.abs(ret)}, index=idx)
    return feats, pd.Series(np.concatenate(true), index=idx)


def test_walk_forward_labels_are_oos_and_sane():
    cfg = load_config()  # min_train 252, test 63, step 63
    feats, true = _two_regime_features()

    regimes = run_walk_forward(feats, cfg)

    # out-of-sample only: first label lands exactly at the min_train boundary, none before
    assert regimes.index.min() == feats.index[cfg.walkforward.min_train]
    assert set(np.unique(regimes.to_numpy())).issubset(set(range(cfg.hmm.n_states)))

    # end-to-end wiring sanity: calm OOS dates rank below turbulent ones
    oos_true = true.loc[regimes.index]
    assert regimes[oos_true == 0].median() < regimes[oos_true == 1].median()

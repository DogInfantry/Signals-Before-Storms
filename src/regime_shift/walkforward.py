"""Expanding-window walk-forward: splits, train-only scaling, fold orchestration. Phase 4."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from regime_shift.regime import RegimeModel


def expanding_walk_forward_splits(n: int, min_train: int, test_size: int, step: int):
    """Yield (train_idx, test_idx) positional arrays for an expanding walk-forward.

    Train always starts at row 0 and grows by `step` each fold; test is the next
    `test_size` rows immediately after train. Train and test are disjoint by construction.
    The final (possibly short) test block is included.
    """
    start = min_train
    while start < n:
        train_idx = np.arange(0, start)
        test_idx = np.arange(start, min(start + test_size, n))
        yield train_idx, test_idx
        start += step


def _pick_rank_col(columns, rank_col: str) -> str:
    if rank_col in columns:
        return rank_col
    vols = [c for c in columns if c.startswith("vol_")]
    if not vols:
        raise ValueError("features have no vol_* column to rank regimes by; pass rank_col")
    return vols[0]


def run_walk_forward(
    features: pd.DataFrame,
    cfg,
    engine: str = "hmm",
    rank_col: str = "vol_21",
    rank_sign: float = 1.0,
    return_model: bool = False,
):
    """Causal, leak-proof regime labels over the out-of-sample span.

    Per fold: fit a StandardScaler on the train rows only, transform train+test with those
    train statistics; fit a RegimeModel on scaled train (ranked by the train rank column so
    labels stay canonical across refits); causally decode the test block carrying the train
    history forward through the online filter; keep only the test-day labels. No test-side
    value ever informs a fitted statistic (scaler, HMM, or label map).

    rank_col / rank_sign define what "ascending risk" means, which turns out to be the whole
    ball game. The default ranks states by trailing volatility, which assumes high vol is bad;
    on US 2016-2023 that assumption is false (the high-vol states carried the HIGHER forward
    equity return, because violent rebounds are as volatile as crashes). rank_col="mom_21" with
    rank_sign=-1.0 ranks by trailing return instead, so label 0 is the best-performing state
    rather than the calmest one. Both are train-only, so both are leak-free; they simply encode
    different definitions of risk.

    Returns a Series named 'regime' (int canonical labels, 0 = calmest) indexed by the
    out-of-sample dates.

    return_model additionally hands back the FINAL fold's fitted model and the causal posterior
    over that fold's test rows. The final fold is the live model by construction: it trains on
    everything up to the last test block and filters causally forward, which is exactly how you
    would run this on today's data. Anything reporting a current regime and its confidence must
    come from that fit, not from a full-sample refit, or the confidence would describe a
    different model than the label (and a full-sample refit would have seen the future for every
    historical band it draws). Off by default, so every existing caller is byte-identical.
    """
    features = features.dropna()
    X = features.to_numpy(dtype=float)
    col = _pick_rank_col(features.columns, rank_col)
    rank = rank_sign * features[col].to_numpy(dtype=float)
    wf = cfg.walkforward
    n = len(features)

    if n <= wf.min_train:
        raise ValueError(
            f"{n} feature rows is not enough for a single fold at min_train={wf.min_train}; "
            "the walk-forward would produce no labels at all"
        )

    oos = pd.Series(index=features.index, dtype="float64", name="regime")
    splits = expanding_walk_forward_splits(n, wf.min_train, wf.test_size, wf.step)
    for train_idx, test_idx in splits:
        scaler = StandardScaler().fit(X[train_idx])
        x_train = scaler.transform(X[train_idx])
        x_test = scaler.transform(X[test_idx])

        model = RegimeModel(
            engine=engine,
            n_states=cfg.hmm.n_states,
            covariance_type=cfg.hmm.covariance_type,
            n_iter=cfg.hmm.n_iter,
            tol=cfg.hmm.tol,
            random_state=cfg.seed,
        ).fit(x_train, rank_by=rank[train_idx])

        # carry train history into the online filter, then keep only the test-day labels
        seq = np.vstack([x_train, x_test])
        causal = model.decode_causal(seq)[len(train_idx) :]
        oos.iloc[test_idx] = causal

    labels = oos.dropna().astype(int)
    if not return_model:
        return labels

    # `model`, `seq`, `train_idx` and `test_idx` are the FINAL fold's, still bound after the loop.
    proba = pd.DataFrame(
        model.filtered_proba(seq)[len(train_idx) :],
        index=features.index[test_idx],
        columns=range(cfg.hmm.n_states),
    )
    return labels, model, proba

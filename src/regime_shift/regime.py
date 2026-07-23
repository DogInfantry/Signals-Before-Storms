"""Regime model: HMM (and a Jump Model second engine), causal decode, stable labels. Phase 3.

Key responsibilities the naive approach omits:
  - stable label mapping so state indices map to Bull/Bear/Crisis consistently across refits
  - causal decoding so a test-day label never uses future observations within the block
  - diagnostics: transition matrix, dwell times, BIC vs number of states
"""

from __future__ import annotations

import warnings

import numpy as np
from hmmlearn.hmm import GaussianHMM
from scipy.special import logsumexp

# Canonical regime order is ALWAYS ascending risk (calmest first). For n_states == 3 these
# names apply; the engine itself only ever works with the integer canonical labels 0..n-1.
REGIME_NAMES_3 = ("Bull", "Bear", "Crisis")


def _canonical_order(raw_labels: np.ndarray, rank_by: np.ndarray, tiebreak: np.ndarray | None):
    """Return raw-state ids sorted ascending by within-state mean risk (calmest first).

    rank_by is a per-row risk proxy (realized vol); tiebreak (per-row, e.g. return) breaks
    ties. This is what defuses HMM label-switching: after every refit the raw state indices
    are permuted, but sorting them by mean vol pins them back to Bull/Bear/Crisis.
    """
    states = np.unique(raw_labels)
    vol_mean = np.array([rank_by[raw_labels == s].mean() for s in states])
    if tiebreak is not None:
        tb_mean = np.array([tiebreak[raw_labels == s].mean() for s in states])
        order = states[np.lexsort((tb_mean, vol_mean))]  # primary vol asc, then tiebreak asc
    else:
        order = states[np.argsort(vol_mean, kind="stable")]
    return order  # order[k] == raw state that becomes canonical label k


class RegimeModel:
    """One fit/decode interface over two engines: a Gaussian HMM (graded baseline) and a
    Statistical Jump Model (flagship second engine, lazily imported).

    Two things the naive `model.predict(whole_test_block)` approach gets wrong and this fixes:
      - label switching: `decode`/`decode_causal` return canonical labels (0 = calmest),
        stable across refits, once `fit` is given a risk proxy to rank states by.
      - lookahead: `decode_causal` uses online forward-filtering, so the label at day t
        depends only on observations at or before t. `decode` (whole-sequence Viterbi) is
        for descriptive overlays on a full sample, never for the walk-forward test decode.
    """

    def __init__(
        self,
        engine: str = "hmm",
        n_states: int = 3,
        covariance_type: str = "diag",
        n_iter: int = 200,
        tol: float = 1e-2,
        random_state: int = 42,
        min_covar: float = 1e-3,
        jump_penalty: float = 50.0,
    ):
        self.engine = engine
        self.n_states = n_states
        self.covariance_type = covariance_type
        self.n_iter = n_iter
        self.tol = tol
        self.random_state = random_state
        self.min_covar = min_covar
        self.jump_penalty = jump_penalty
        self._model = None
        self._raw_order: np.ndarray | None = None  # canonical -> raw state id

    # -- fitting -------------------------------------------------------------
    def fit(
        self,
        X: np.ndarray,
        rank_by: np.ndarray | None = None,
        tiebreak: np.ndarray | None = None,
    ):
        """Fit on standardized feature matrix X (n_samples, n_features).

        rank_by: per-row risk proxy (realized vol) used to pin the canonical label order.
        If None, canonical order is identity and label switching is NOT solved (warns).
        """
        X = np.asarray(X, dtype=float)
        if self.engine == "hmm":
            self._model = GaussianHMM(
                n_components=self.n_states,
                covariance_type=self.covariance_type,
                n_iter=self.n_iter,
                tol=self.tol,
                random_state=self.random_state,
                min_covar=self.min_covar,
            ).fit(X)
            raw = self._model.predict(X)
        elif self.engine == "jump":
            jm = _make_jump_model(self.n_states, self.jump_penalty, self.random_state)
            self._model = jm.fit(X)
            raw = np.asarray(self._model.labels_)
        else:
            raise ValueError(f"unknown engine {self.engine!r}; use 'hmm' or 'jump'")

        if rank_by is None:
            warnings.warn(
                "fit() called without rank_by; canonical labels fall back to raw state order, "
                "so label-switching across refits is NOT handled",
                stacklevel=2,
            )
            self._raw_order = np.arange(self.n_states)
        else:
            self._raw_order = _canonical_order(raw, np.asarray(rank_by, dtype=float), tiebreak)
        return self

    def _to_canonical(self, raw_labels: np.ndarray) -> np.ndarray:
        # canonical label of a raw state = its position in self._raw_order
        raw_to_canon = np.empty(self.n_states, dtype=int)
        raw_to_canon[self._raw_order] = np.arange(self.n_states)
        return raw_to_canon[raw_labels]

    # -- decoding ------------------------------------------------------------
    def decode(self, X: np.ndarray) -> np.ndarray:
        """Whole-sequence MAP decode (Viterbi for HMM). Smoothed, NOT causal: only for
        descriptive full-sample overlays, never for the leak-proof test decode."""
        X = np.asarray(X, dtype=float)
        if self.engine == "hmm":
            raw = self._model.predict(X)
        else:
            raw = np.asarray(self._model.predict(X))
        return self._to_canonical(raw)

    def decode_causal(self, X: np.ndarray) -> np.ndarray:
        """Online decode: label at row t uses only rows 0..t. Leak-proof by construction.

        HMM: normalized forward (alpha) filtering; argmax of the filtered posterior at t.
        Jump: predict_online, which the Jump Model exposes for exactly this purpose.
        """
        X = np.asarray(X, dtype=float)
        if self.engine == "hmm":
            raw = self._forward_filter_states(X)
        else:
            raw = np.asarray(self._model.predict_online(X))
        return self._to_canonical(raw)

    def _forward_filter_states(self, X: np.ndarray) -> np.ndarray:
        m = self._model
        framelogprob = m._compute_log_likelihood(X)  # (T, K) log emission probs
        with np.errstate(divide="ignore"):
            log_start = np.log(m.startprob_)
            log_trans = np.log(m.transmat_)
        n, k = framelogprob.shape
        log_alpha = np.empty((n, k))
        log_alpha[0] = log_start + framelogprob[0]
        for t in range(1, n):
            # log_alpha[t, j] = emission[t, j] + logsumexp_i(log_alpha[t-1, i] + log_trans[i, j])
            prev = log_alpha[t - 1][:, None] + log_trans
            log_alpha[t] = framelogprob[t] + logsumexp(prev, axis=0)
        # argmax over states of the (row-normalized) filtered posterior; normalization is a
        # per-row constant so it does not move the argmax.
        return log_alpha.argmax(axis=1)

    # -- diagnostics ---------------------------------------------------------
    def transition_matrix(self) -> np.ndarray:
        """Transition matrix reordered into canonical (ascending-risk) label space. HMM only."""
        if self.engine != "hmm":
            raise NotImplementedError("transition_matrix is HMM-specific")
        return self._model.transmat_[np.ix_(self._raw_order, self._raw_order)]

    def bic(self, X: np.ndarray) -> float:
        """Bayesian information criterion of the fitted HMM on X (lower is better)."""
        if self.engine != "hmm":
            raise NotImplementedError("bic is HMM-specific")
        return float(self._model.bic(np.asarray(X, dtype=float)))


def dwell_times(labels: np.ndarray) -> dict[int, float]:
    """Mean run length (persistence) per label in a decoded sequence."""
    labels = np.asarray(labels)
    if labels.size == 0:
        return {}
    change = np.flatnonzero(np.diff(labels)) + 1
    run_starts = np.concatenate(([0], change))
    run_lengths = np.diff(np.concatenate((run_starts, [labels.size])))
    run_labels = labels[run_starts]
    out: dict[int, list[int]] = {}
    for lab, length in zip(run_labels, run_lengths, strict=True):
        out.setdefault(int(lab), []).append(int(length))
    return {lab: float(np.mean(lengths)) for lab, lengths in out.items()}


def bic_sweep(X: np.ndarray, n_states_range=(2, 3, 4, 5), **hmm_kwargs) -> dict[int, float]:
    """Fit an HMM for each candidate state count and return BIC per count.

    Diagnostic used once on the first train window to justify K=3, then frozen. Lower BIC
    is better; the elbow, not the raw minimum, is what matters for regime interpretability.
    """
    X = np.asarray(X, dtype=float)
    scores: dict[int, float] = {}
    for k in n_states_range:
        try:
            scores[k] = RegimeModel(n_states=k, **hmm_kwargs).fit(X).bic(X)
        except Exception as exc:  # noqa: BLE001 - a state count may fail to converge on short data
            warnings.warn(f"BIC fit failed for n_states={k}: {type(exc).__name__}", stacklevel=2)
            scores[k] = float("nan")
    return scores


def _make_jump_model(n_states: int, jump_penalty: float, random_state: int):
    """Lazy jumpmodels import: it is an optional extra, so only required when engine='jump'."""
    try:
        from jumpmodels.jump import JumpModel
    except ImportError as exc:  # pragma: no cover - exercised only without the optional extra
        raise ImportError(
            "engine='jump' needs the optional 'jumpmodels' package "
            "(uv add jumpmodels). The HMM engine has no such dependency."
        ) from exc
    return JumpModel(n_components=n_states, jump_penalty=jump_penalty, random_state=random_state)

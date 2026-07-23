"""Per-regime convex optimization in cvxpy: shrinkage covariance, constraints. Phase 5.

Bull: max Sharpe (convex reformulation). Bear: min variance. Crisis: defensive.
Inputs (mu, Sigma) are estimated train-only with Ledoit-Wolf shrinkage.
"""

from __future__ import annotations

import cvxpy as cp
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf


def ledoit_wolf_cov(returns) -> np.ndarray:
    """Ledoit-Wolf shrinkage covariance (train-only). Biggest cheap robustness win over the
    raw sample covariance, whose noise blows up the optimizer."""
    return LedoitWolf().fit(np.asarray(returns, dtype=float)).covariance_


def shrink_mu(returns, intensity: float = 0.5) -> np.ndarray:
    """Expected returns shrunk toward the cross-asset grand mean. intensity in [0, 1]; 1 =
    fully equal. In-sample means are extremely noisy, so pulling each toward the grand mean
    is a standard guard against max-Sharpe blow-up."""
    mu = np.asarray(returns, dtype=float).mean(axis=0)
    return (1 - intensity) * mu + intensity * mu.mean()


def _base_constraints(w, weight_cap):
    return [cp.sum(w) == 1, w >= 0, w <= weight_cap]


def _clean(w, k: int) -> np.ndarray:
    if w is None:
        return np.full(k, 1.0 / k)  # solver failure -> equal-weight fallback
    w = np.clip(np.asarray(w, dtype=float), 0, None)
    s = w.sum()
    return w / s if s > 0 else np.full(k, 1.0 / k)


def min_variance_weights(cov, weight_cap: float) -> np.ndarray:
    """Long-only minimum-variance portfolio under the weight cap."""
    k = cov.shape[0]
    w = cp.Variable(k)
    obj = cp.Minimize(cp.quad_form(w, cp.psd_wrap(cov)))
    cp.Problem(obj, _base_constraints(w, weight_cap)).solve()
    return _clean(w.value, k)


def max_sharpe_weights(mu, cov, weight_cap: float) -> np.ndarray:
    """Long-only max-Sharpe via the Schaible homogenization (Sharpe is a ratio, not convex).

    Solve min y'Sigma y s.t. mu'y = 1, y >= 0, y <= cap*sum(y); recover w = y/sum(y). The
    cap constraint w_i <= cap becomes y_i <= cap*sum(y), still linear in y. Needs some
    positive expected return; if max(mu) <= 0 the ratio is ill-posed, so fall back to
    minimum variance.
    """
    mu = np.asarray(mu, dtype=float)
    if mu.max() <= 0:
        return min_variance_weights(cov, weight_cap)
    k = cov.shape[0]
    y = cp.Variable(k)
    cons = [mu @ y == 1, y >= 0, y <= weight_cap * cp.sum(y)]
    cp.Problem(cp.Minimize(cp.quad_form(y, cp.psd_wrap(cov))), cons).solve()
    if y.value is None or y.value.sum() <= 0:
        return min_variance_weights(cov, weight_cap)
    return _clean(y.value / y.value.sum(), k)


def defensive_weights(cov, asset_cols, weight_cap: float, equity_cap: float = 0.1) -> np.ndarray:
    """Crisis stance: minimum variance with the equity sleeve hard-capped low, forcing mass
    into the defensive assets (bonds/gold). Plain min-variance if no equity column is present.

    equity_cap is a deliberate defensive knob, not a value that never changes -- tune it or
    lift it into config if the crisis stance needs to be more or less risk-off.
    """
    k = cov.shape[0]
    w = cp.Variable(k)
    cons = _base_constraints(w, weight_cap)
    cons += [w[i] <= equity_cap for i, c in enumerate(asset_cols) if "equity" in c]
    cp.Problem(cp.Minimize(cp.quad_form(w, cp.psd_wrap(cov))), cons).solve()
    return _clean(w.value, k)


def regime_weights(
    regime: int, train_returns: pd.DataFrame, cfg, mu_shrink: float = 0.5
) -> pd.Series:
    """Convex target weights for one regime, all inputs estimated train-only.

    Canonical labels (0 = calmest): 0 -> Bull (max-Sharpe), n_states-1 -> Crisis (defensive),
    anything strictly between -> Bear (min-variance). Returns a Series indexed by the return
    columns of train_returns.

    ponytail: no turnover penalty here -- the backtest controls churn via rebalance cadence /
    hysteresis. Add an L1 |w - w_prev| term to the objectives if per-rebalance drift matters.
    """
    cols = list(train_returns.columns)
    cov = ledoit_wolf_cov(train_returns)
    cap = cfg.weight_cap
    last = cfg.hmm.n_states - 1

    if regime <= 0:
        w = max_sharpe_weights(shrink_mu(train_returns, mu_shrink), cov, cap)
    elif regime >= last:
        w = defensive_weights(cov, cols, cap)
    else:
        w = min_variance_weights(cov, cap)
    return pd.Series(w, index=cols, name=f"regime_{regime}")

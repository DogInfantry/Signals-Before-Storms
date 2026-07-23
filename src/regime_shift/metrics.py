"""Performance metrics: Sharpe, Sortino, Max DD, Calmar, turnover, plus research-grade
deflated/probabilistic Sharpe and bootstrap confidence intervals. Phase 7.

Everything here takes SIMPLE per-period returns, which is what backtest.run_book emits as
ret_gross / ret_net. Annualization assumes 252 trading days unless told otherwise.

The point of the last three functions: a Sharpe ratio computed once, on one strategy, out of
many tried, is a biased number. PSR asks whether the Sharpe survives the sample's own skew and
fat tails; the deflated version additionally charges for how many variants were searched.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew

_EULER = 0.5772156649015329


def _arr(r) -> np.ndarray:
    a = np.asarray(r, dtype=float)
    return a[~np.isnan(a)]


def ann_return(r, periods: int = 252) -> float:
    """Geometric annualized return of a simple-return series."""
    a = _arr(r)
    if a.size == 0:
        return float("nan")
    return float(np.prod(1.0 + a) ** (periods / a.size) - 1.0)


def ann_vol(r, periods: int = 252) -> float:
    a = _arr(r)
    return float(a.std(ddof=1) * np.sqrt(periods))


def sharpe(r, periods: int = 252, rf: float = 0.0) -> float:
    """Annualized Sharpe. rf is an annual rate, spread evenly over the periods."""
    a = _arr(r) - rf / periods
    s = a.std(ddof=1)
    return float(a.mean() / s * np.sqrt(periods)) if s > 0 else float("nan")


def sortino(r, periods: int = 252, target: float = 0.0) -> float:
    """Like Sharpe but punished only by downside deviation below the (annual) target."""
    a = _arr(r) - target / periods
    dd = np.sqrt(np.mean(np.minimum(a, 0.0) ** 2))
    return float(a.mean() / dd * np.sqrt(periods)) if dd > 0 else float("nan")


def max_drawdown(r) -> float:
    """Worst peak-to-trough loss on the compounded path. Negative by convention."""
    eq = np.cumprod(1.0 + _arr(r))
    return float((eq / np.maximum.accumulate(eq) - 1.0).min())


def calmar(r, periods: int = 252) -> float:
    dd = abs(max_drawdown(r))
    return float(ann_return(r, periods) / dd) if dd > 0 else float("nan")


def probabilistic_sharpe(r, benchmark: float = 0.0, periods: int = 252) -> float:
    """Bailey & Lopez de Prado PSR: P(true Sharpe > benchmark) given n, skew and kurtosis.

    benchmark is annualized, same units as sharpe(). Negative skew and fat tails inflate the
    standard error of the estimate and drag PSR down, which is exactly the point: the same
    Sharpe is worth less when it came from a lumpy, crash-prone return stream.
    """
    a = _arr(r)
    n = a.size
    s = a.std(ddof=1)
    if n < 3 or s <= 0:
        return float("nan")
    sr = a.mean() / s  # per period, as the formula requires
    var = (1.0 - skew(a) * sr + (kurtosis(a, fisher=False) - 1.0) / 4.0 * sr**2) / (n - 1)
    if var <= 0:
        return float("nan")
    return float(norm.cdf((sr - benchmark / np.sqrt(periods)) / np.sqrt(var)))


def expected_max_sharpe(n_trials: int, trial_sr_std: float) -> float:
    """Annualized Sharpe you would expect from the BEST of n_trials worthless strategies.

    trial_sr_std is the spread of annualized Sharpes across the variants actually searched.
    Search hard enough and a zero-skill best-of will clear 1.0, which is why it is subtracted.
    """
    if n_trials < 2 or trial_sr_std <= 0:
        return 0.0
    z1 = norm.ppf(1.0 - 1.0 / n_trials)
    z2 = norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    return float(trial_sr_std * ((1.0 - _EULER) * z1 + _EULER * z2))


def deflated_sharpe(r, n_trials: int, trial_sr_std: float, periods: int = 252) -> float:
    """PSR measured against expected_max_sharpe instead of zero: the selection-bias haircut."""
    return probabilistic_sharpe(r, expected_max_sharpe(n_trials, trial_sr_std), periods)


def _flat_top(s: np.ndarray) -> np.ndarray:
    """Politis-Romano flat-top lag window: 1 on the plateau, linear shoulder, 0 past the edge."""
    a = np.abs(s)
    return np.where(a <= 0.5, 1.0, np.where(a <= 1.0, 2.0 * (1.0 - a), 0.0))


def optimal_block_length(r) -> float:
    """Politis & White (2004) automatic block length for the stationary bootstrap.

    Reads the mean block off the series' own correlogram instead of hand-setting it. Bandwidth is
    twice the last lag where the autocorrelation is still significant; the block then solves the
    usual bias-variance trade-off for the spectral density at zero. Independent data collapses to
    a block near 1, persistent data asks for long blocks.
    """
    a = _arr(r)
    n = a.size
    if n < 16:
        return 1.0
    x = a - a.mean()
    k_n = max(5, int(np.ceil(np.sqrt(np.log10(n)))))
    m_max = min(n - 1, int(np.ceil(np.sqrt(n))) + k_n)
    acov = np.array([float(x[: n - k] @ x[k:]) / n for k in range(m_max + 1)])
    if acov[0] <= 0:
        return 1.0
    rho = acov / acov[0]

    crit = 2.0 * np.sqrt(np.log10(n) / n)  # the usual correlogram significance band
    m = m_max
    for i in range(m_max):
        window = rho[i + 1 : min(i + k_n, m_max) + 1]
        if window.size and np.all(np.abs(window) < crit):
            m = i
            break
    bandwidth = int(min(2 * max(m, 1), m_max))

    lags = np.arange(-bandwidth, bandwidth + 1)
    w = _flat_top(lags / bandwidth)
    cov = acov[np.abs(lags)]
    g = float(np.sum(w * np.abs(lags) * cov))
    d = 2.0 * float(np.sum(w * cov)) ** 2
    if d <= 0 or g == 0.0:
        return 1.0
    b = (2.0 * g**2 / d) ** (1.0 / 3.0) * n ** (1.0 / 3.0)
    return float(np.clip(b, 1.0, np.ceil(min(3.0 * np.sqrt(n), n / 3.0))))


def _stationary_indices(n: int, n_boot: int, mean_block: float, rng) -> np.ndarray:
    """Politis-Romano stationary bootstrap indices: geometric block lengths, wrapped.

    Daily strategy returns are serially dependent (vol clusters, regimes persist), so an iid
    resample would shred the dependence and hand back a CI that is far too tight.
    """
    p = 1.0 / max(mean_block, 1)
    pos = np.arange(n)
    restart = rng.random((n_boot, n)) < p
    restart[:, 0] = True
    starts = rng.integers(0, n, (n_boot, n))
    last = np.maximum.accumulate(np.where(restart, pos, -1), axis=1)  # index of last block start
    return (np.take_along_axis(starts, last, axis=1) + (pos - last)) % n


def bootstrap_ci(
    r,
    stat=sharpe,
    n_boot: int = 1000,
    alpha: float = 0.05,
    mean_block: float | None = None,
    seed: int = 42,
) -> tuple[float, float]:
    """Percentile confidence interval for any statistic, via the stationary bootstrap.

    mean_block None reads the block length off the data (optimal_block_length); pass a number to
    pin it. Guessing 21 because a month has 21 trading days is not tuning, it is a habit.
    """
    a = _arr(r)
    block = optimal_block_length(a) if mean_block is None else mean_block
    idx = _stationary_indices(a.size, n_boot, block, np.random.default_rng(seed))
    vals = np.array([stat(a[row]) for row in idx])
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return float("nan"), float("nan")
    return float(np.quantile(vals, alpha / 2)), float(np.quantile(vals, 1.0 - alpha / 2))


def summary(book, col: str = "ret_net", periods: int = 252) -> pd.Series:
    """One-line scorecard. Accepts a backtest book (reads `col`) or a bare return Series."""
    is_book = isinstance(book, pd.DataFrame)
    r = book[col] if is_book else book
    out = {
        "ann_return": ann_return(r, periods),
        "ann_vol": ann_vol(r, periods),
        "sharpe": sharpe(r, periods),
        "sortino": sortino(r, periods),
        "max_drawdown": max_drawdown(r),
        "calmar": calmar(r, periods),
        "psr": probabilistic_sharpe(r, 0.0, periods),
    }
    if is_book and "turnover" in book.columns:
        out["turnover_ann"] = float(book["turnover"].sum() * periods / len(book))
        out["cost_drag_ann"] = float(book["cost"].sum() * periods / len(book))
    return pd.Series(out, name=col if is_book else book.name)

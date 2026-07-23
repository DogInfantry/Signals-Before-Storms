"""Backtest engine: 1-day weight lag, turnover, transaction costs, equity curve. Phase 6.

Consumes the causal out-of-sample labels from walkforward.run_walk_forward and the per-regime
convex targets from optimize.regime_weights. One rule governs the whole file: a regime observed
at the close of day t may only move the weights that earn day t+1's return. Hysteresis, drift
and costs all hang off that single lag.

run_book is the shared engine; run_backtest is the regime-driven strategy on top of it, and the
static benchmarks in benchmarks.py sit on the same engine so they pay identical costs.

Master asset columns are LOG returns (data.build_master), so they are converted to simple
returns before any portfolio aggregation: a weighted sum of log returns is not the log return
of the weighted portfolio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from regime_shift.optimize import regime_weights


def asset_cols(returns: pd.DataFrame) -> list[str]:
    """The *_ret columns of a master frame, i.e. the things we can hold."""
    cols = [c for c in returns.columns if c.endswith("_ret")]
    if not cols:
        raise ValueError("returns has no *_ret asset columns to allocate over")
    return cols


def _drift(w: np.ndarray, r: np.ndarray) -> np.ndarray:
    """Weights carried out of a day, after its returns but before any trade. Flat stays flat."""
    grown = w * (1.0 + r)
    total = grown.sum()
    return grown / total if total > 0 else grown


def run_book(rets: pd.DataFrame, dates, decide, cfg) -> pd.DataFrame:
    """Mark a book day by day: charge the trades `decide` asks for, drift it in between.

    rets: *_ret LOG return columns. dates: the span to trade. decide(t) -> (label, target or
    None), called at the CLOSE of t; its target sets the weights that earn t+1's return, which
    is the one-day execution lag every strategy in this package shares. Returning None holds and
    lets the book drift, which costs exactly nothing.

    Returns a frame indexed by dates: regime (nullable label, whatever decide reported),
    w_<asset> weights in force, turnover, cost, ret_gross, ret_net, equity_gross, equity_net.
    """
    cols = list(rets.columns)
    simple = np.expm1(rets)  # portfolio math needs simple, not log, returns
    w_cols = [f"w_{c.removesuffix('_ret')}" for c in cols]
    cost_rate = cfg.costs_bps / 10_000.0
    k = len(cols)

    w_in = np.zeros(k)  # weights earning today's return, set at yesterday's close
    w_held = np.zeros(k)  # weights carried out of yesterday, after drift
    label = None
    labels, rows = [], []

    for t in dates:
        r = simple.loc[t].to_numpy()
        turnover = float(np.abs(w_in - w_held).sum())
        cost = turnover * cost_rate
        gross = float(w_in @ r)
        labels.append(label)
        rows.append(
            {
                **dict(zip(w_cols, w_in, strict=True)),
                "turnover": turnover,
                "cost": cost,
                "ret_gross": gross,
                "ret_net": gross - cost,
            }
        )
        w_held = _drift(w_in, r)

        # decide sees nothing fresher than the close of t and can only move the weights that
        # earn t+1's return. The execution lag lives here so every strategy inherits it.
        label, target = decide(t)
        w_in = w_held if target is None else np.asarray(target, dtype=float)

    res = pd.DataFrame(rows, index=dates)
    res.insert(0, "regime", pd.array(labels, dtype="Int64"))  # day 1 is flat, so it has no label
    res["equity_gross"] = (1.0 + res["ret_gross"]).cumprod()
    res["equity_net"] = (1.0 + res["ret_net"]).cumprod()
    return res


def run_backtest(
    regimes: pd.Series,
    returns: pd.DataFrame,
    cfg,
    confirm_days: int | None = None,
    mu_shrink: float = 0.5,
    conditional: bool | None = None,
) -> pd.DataFrame:
    """Trade the regime path and return the per-day book.

    regimes: causal OOS labels (walkforward.run_walk_forward). returns: any frame carrying the
    master *_ret log-return columns; history before the first regime date is used for estimation
    but never traded.

    Rebalance cadence is cfg.rebalance: "on_regime_change" (with a confirm_days hysteresis, so a
    one-day flicker in the filter does not cost a round trip) or "monthly". Turnover on a trade
    day is sum|w_target - w_drifted|, charged at cfg.costs_bps.

    conditional (default cfg.conditional_moments) estimates mu/Sigma from the PAST DAYS THAT
    CARRIED THE SAME LABEL rather than from all history, so a crisis portfolio is built on crisis
    covariances. Below cfg.conditional_min_obs same-label days the estimate is too thin to trust
    and it falls back to full history. Set False for the unconditional ablation, where the regime
    only picks the objective and every regime sees the same moments.
    """
    cols = asset_cols(returns)
    rets = returns[cols].astype(float)
    missing = regimes.index.difference(rets.index)
    if len(missing):
        raise ValueError(f"{len(missing)} regime dates absent from returns (e.g. {missing[0]})")

    confirm = cfg.rebalance_confirm_days if confirm_days is None else confirm_days
    by_regime = cfg.conditional_moments if conditional is None else conditional
    monthly = cfg.rebalance == "monthly"
    traded, cand, run_len, month = None, None, 0, None

    def sample(t, label):
        """Estimation window at the close of t: same-label history if there is enough of it."""
        if not by_regime:
            return rets.loc[:t]
        past = regimes.loc[:t]
        same = past.index[past.to_numpy() == label]
        return rets.loc[same] if len(same) >= cfg.conditional_min_obs else rets.loc[:t]

    def decide(t):
        nonlocal traded, cand, run_len, month
        regime_t = int(regimes.loc[t])
        if monthly:
            traded = regime_t
            trade = month is None or t.month != month
            month = t.month
        else:
            trade = traded is None
            if trade:
                traded = regime_t
            elif regime_t != traded:
                run_len = run_len + 1 if regime_t == cand else 1
                cand = regime_t
                if run_len >= confirm:  # flicker must persist before it costs us a round trip
                    traded, trade, cand, run_len = regime_t, True, None, 0
            else:
                cand, run_len = None, 0
        if not trade:
            return traded, None
        return traded, regime_weights(traded, sample(t, traded), cfg, mu_shrink).to_numpy()

    return run_book(rets, regimes.index, decide, cfg)

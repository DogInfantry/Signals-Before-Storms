"""Phase 6 tests for the backtest engine.

The two properties that make the whole engine trustworthy: a regime seen at the close of t can
only move PnL at t+1 (never t), and a day with no trade is charged nothing. Synthetic, seeded,
offline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from regime_shift.backtest import run_backtest
from regime_shift.config import load_config

_COLS = ["equity_ret", "bond_ret", "gold_ret"]
_N, _OOS = 400, 150


def _log_returns(seed: int = 0) -> pd.DataFrame:
    """Log returns shaped like the master frame: equity hot, bond calm, gold in between."""
    rng = np.random.default_rng(seed)
    data = np.column_stack(
        [
            rng.normal(0.0010, 0.012, _N),
            rng.normal(0.0002, 0.003, _N),
            rng.normal(0.0005, 0.008, _N),
        ]
    )
    return pd.DataFrame(data, columns=_COLS, index=pd.bdate_range("2015-01-02", periods=_N))


def _regimes(index) -> pd.Series:
    return pd.Series(0, index=index[-_OOS:], name="regime")


def test_regime_change_moves_pnl_only_from_the_next_day():
    cfg = load_config()
    rets = _log_returns()
    base = _regimes(rets.index)
    switched = base.copy()
    i = 100  # flip to the crisis label from here on
    switched.iloc[i:] = cfg.hmm.n_states - 1

    # confirm_days=1 so the switch is acted on immediately; any lag seen is the execution lag
    res_base = run_backtest(base, rets, cfg, confirm_days=1)
    res_switch = run_backtest(switched, rets, cfg, confirm_days=1)

    # the regime read at close(i) cannot touch anything up to and including day i
    pd.testing.assert_frame_equal(res_base.iloc[: i + 1], res_switch.iloc[: i + 1])
    # and it must have moved the book by day i+1
    w = [c for c in res_base.columns if c.startswith("w_")]
    assert not np.allclose(res_base[w].iloc[i + 1], res_switch[w].iloc[i + 1])
    assert res_switch["turnover"].iloc[i] == 0.0  # trade lands on i+1, not i
    assert res_switch["turnover"].iloc[i + 1] > 0.0


def test_flat_first_day_then_entry_is_the_only_trade_under_a_constant_regime():
    cfg = load_config()
    rets = _log_returns()
    res = run_backtest(_regimes(rets.index), rets, cfg)
    w = [c for c in res.columns if c.startswith("w_")]

    # day one has no prior close to have decided anything, so the book is flat and earns nothing
    assert res[w].iloc[0].abs().sum() == 0.0
    assert res["ret_gross"].iloc[0] == 0.0
    # entry on day two is the only turnover; the regime never changes, so nothing else trades
    assert abs(res["turnover"].iloc[1] - 1.0) < 1e-9
    assert (res["turnover"].iloc[2:] == 0.0).all()


def test_conditional_moments_change_the_book():
    cfg = load_config()
    cfg.rebalance = "monthly"  # several trades, so which sample feeds the optimizer matters
    cfg.conditional_min_obs = 20
    rets = _log_returns()
    reg = _regimes(rets.index)

    cond = run_backtest(reg, rets, cfg, conditional=True)
    uncond = run_backtest(reg, rets, cfg, conditional=False)
    w = [c for c in cond.columns if c.startswith("w_")]
    assert not np.allclose(cond[w].to_numpy(), uncond[w].to_numpy())


def test_conditional_falls_back_to_full_history_when_the_regime_is_thin():
    cfg = load_config()
    cfg.rebalance = "monthly"
    cfg.conditional_min_obs = 10**6  # never enough same-label days to trust
    rets = _log_returns()
    reg = _regimes(rets.index)

    pd.testing.assert_frame_equal(
        run_backtest(reg, rets, cfg, conditional=True),
        run_backtest(reg, rets, cfg, conditional=False),
    )


def test_target_vol_de_risks_without_ever_levering():
    cfg = load_config()
    rets = _log_returns()
    reg = _regimes(rets.index)

    full = run_backtest(reg, rets, cfg)
    scaled = run_backtest(reg, rets, cfg, target_vol=0.03)  # far below the book's natural vol
    w = [c for c in scaled.columns if c.startswith("w_")]

    invested = scaled[w].sum(axis=1)
    assert invested.max() <= 1.0 + 1e-9  # long-only, never levered
    assert invested.iloc[1] < 0.9  # and genuinely scaled down, not merely reweighted
    assert scaled["ret_net"].std() < full["ret_net"].std()  # less risk taken, as asked


def test_zero_turnover_is_free_and_costs_only_drag():
    cfg = load_config()
    rets = _log_returns()
    res = run_backtest(_regimes(rets.index), rets, cfg)

    assert (res.loc[res["turnover"] == 0.0, "cost"] == 0.0).all()
    np.testing.assert_allclose(res["cost"], res["turnover"] * cfg.costs_bps / 10_000.0)
    np.testing.assert_allclose(res["ret_net"], res["ret_gross"] - res["cost"])
    assert res["equity_net"].iloc[-1] < res["equity_gross"].iloc[-1]  # costs can only subtract

"""Phase 7 tests for the static benchmarks and the rule-based ablation.

The benchmarks only mean something if they are costed like the strategy, so these assert the
weights they actually hold, the trades they actually pay for, and that the ablation labels are
causal. Synthetic, seeded, offline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from regime_shift.benchmarks import equal_weight, sixty_forty, static_book, vol_rule_regimes
from regime_shift.config import load_config
from regime_shift.optimize import regime_weights

_COLS = ["equity_ret", "bond_ret", "gold_ret"]
_N = 500


def _log_returns(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    data = np.column_stack(
        [
            rng.normal(0.0010, 0.012, _N),
            rng.normal(0.0002, 0.003, _N),
            rng.normal(0.0005, 0.008, _N),
        ]
    )
    return pd.DataFrame(data, columns=_COLS, index=pd.bdate_range("2015-01-02", periods=_N))


def test_equal_weight_holds_one_over_n_after_entry():
    cfg = load_config()
    rets = _log_returns()
    book = equal_weight(rets, rets.index, cfg)
    w = book[["w_equity", "w_bond", "w_gold"]].iloc[1]
    np.testing.assert_allclose(w.to_numpy(), np.full(3, 1 / 3), atol=1e-12)


def test_sixty_forty_renormalizes_when_the_bond_sleeve_is_missing():
    cfg = load_config()
    rets = _log_returns()

    row = sixty_forty(rets, rets.index, cfg).iloc[1]
    assert abs(row["w_equity"] - 0.6) < 1e-12
    assert abs(row["w_bond"] - 0.4) < 1e-12
    assert row["w_gold"] == 0.0

    # neither a bond nor a cash sleeve: nothing can fill the defensive leg, so renormalize
    # rather than sit 40% idle
    stripped = rets[["equity_ret", "gold_ret"]]
    row = sixty_forty(stripped, stripped.index, cfg).iloc[1]
    assert abs(row["w_equity"] - 1.0) < 1e-12


def test_sixty_forty_falls_back_to_cash_when_there_is_no_bond_sleeve():
    """India's defensive leg is an overnight fund, not duration. Without the fallback the book
    labelled 60/40 is really 100% NIFTY, and the strategy gets judged against a pure equity
    benchmark carrying four times its volatility."""
    cfg = load_config()
    rng = np.random.default_rng(2)
    india = _log_returns()[["equity_ret", "gold_ret"]].copy()
    india["cash_ret"] = rng.normal(0.00015, 0.0002, _N)

    row = sixty_forty(india, india.index, cfg).iloc[1]
    assert abs(row["w_equity"] - 0.6) < 1e-12
    assert abs(row["w_cash"] - 0.4) < 1e-12
    assert row["w_gold"] == 0.0

    # a real bond sleeve still wins the leg when both are present
    both = _log_returns()
    both["cash_ret"] = rng.normal(0.00015, 0.0002, _N)
    row = sixty_forty(both, both.index, cfg).iloc[1]
    assert abs(row["w_bond"] - 0.4) < 1e-12
    assert row["w_cash"] == 0.0


def test_cash_sleeve_is_allocated_and_absorbs_the_crisis_stance():
    """India has no usable bond ETF, so cash is the defensive sleeve. It has to be a real asset
    to the optimizer, not a column that gets quietly ignored."""
    cfg = load_config()
    rng = np.random.default_rng(1)
    rets = _log_returns()
    rets["cash_ret"] = rng.normal(0.00015, 0.0002, _N)  # overnight fund: yield, almost no risk

    row = equal_weight(rets, rets.index, cfg).iloc[1]
    assert abs(row["w_cash"] - 0.25) < 1e-12  # 1/N counts cash as one of the N

    crisis = regime_weights(cfg.hmm.n_states - 1, rets, cfg)
    assert crisis["cash_ret"] > 0.5  # the defensive stance parks in the calmest asset
    assert crisis["equity_ret"] <= 0.1 + 1e-9  # and equity stays hard-capped


def test_monthly_rebalance_pays_only_at_month_turns():
    cfg = load_config()
    rets = _log_returns()

    held = static_book(rets, rets.index, cfg, rebalance="never")
    monthly = static_book(rets, rets.index, cfg, rebalance="monthly")

    assert (held["turnover"].iloc[2:] == 0.0).all()  # bought once, never touched again

    # each month's first close decides, and the trade lands the next day (execution lag), so the
    # final month's decision falls off the end of the span
    firsts = monthly.index.to_series().groupby(monthly.index.to_period("M")).first()
    landed = [p for p in (monthly.index.get_loc(d) + 1 for d in firsts) if p < len(monthly.index)]
    pd.testing.assert_index_equal(monthly.index[monthly["turnover"] > 0], monthly.index[landed])
    assert monthly["cost"].sum() > held["cost"].sum()  # rebalancing is not free


def test_vol_rule_labels_are_binary_and_causal():
    cfg = load_config()
    rets = _log_returns()
    base = vol_rule_regimes(rets, cfg)

    assert set(np.unique(base.to_numpy())) <= {0, cfg.hmm.n_states - 1}

    cut = base.index[len(base) // 2]
    shocked = rets.copy()
    shocked.loc[shocked.index > cut, "equity_ret"] *= 10.0  # blow up the future only
    after = vol_rule_regimes(shocked, cfg)
    pd.testing.assert_series_equal(base.loc[:cut], after.loc[:cut])

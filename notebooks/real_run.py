"""Real-data end-to-end run: cached yfinance master -> features -> walk-forward -> books.

Writes the three figures to results/ and prints the scorecard. US universe by default (India has
no bond ticker resolved yet, so it runs equity+gold only).
"""

import pathlib
import sys
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from regime_shift.backtest import run_backtest
from regime_shift.benchmarks import equal_weight, sixty_forty, vol_rule_regimes
from regime_shift.config import load_config
from regime_shift.data import build_master
from regime_shift.features import build_features
from regime_shift.metrics import bootstrap_ci, deflated_sharpe, optimal_block_length, summary
from regime_shift.plots import equity_drawdown, regime_overlay, transition_heatmap
from regime_shift.regime import RegimeModel, dwell_times
from regime_shift.walkforward import run_walk_forward

warnings.filterwarnings("ignore")
market = sys.argv[1] if len(sys.argv) > 1 else "us"
out = pathlib.Path("results")
out.mkdir(exist_ok=True)

cfg = load_config()
master = build_master(cfg.universes[market], cfg.dates["start"], cfg.dates["end"])
feats = build_features(master, cfg)
print(f"[{market}] master={master.shape} cols={list(master.columns)}")
print(f"[{market}] features={feats.shape} cols={list(feats.columns)}")

regimes = run_walk_forward(feats, cfg)
oos = regimes.index
print(f"[{market}] OOS {oos[0].date()} -> {oos[-1].date()} n={len(oos)}")
print("  label counts:", regimes.value_counts().sort_index().to_dict())
print("  mean dwell (days):", {k: round(v, 1) for k, v in dwell_times(regimes.to_numpy()).items()})

books = {
    "hmm_conditional": run_backtest(regimes, master, cfg, conditional=True),
    "hmm_unconditional": run_backtest(regimes, master, cfg, conditional=False),
    "vol_rule_ablation": run_backtest(vol_rule_regimes(master, cfg).loc[oos], master, cfg),
    "60_40": sixty_forty(master, oos, cfg),
    "equal_weight": equal_weight(master, oos, cfg),
}
table = pd.DataFrame({k: summary(v) for k, v in books.items()}).T
print("\n=== net of costs ===")
print(table.round(3).to_string())

strat = books["hmm_conditional"]["ret_net"]
block = optimal_block_length(strat)
lo, hi = bootstrap_ci(strat, n_boot=2000)
print(f"\nauto block length = {block:.1f} days")
print(f"sharpe 95% CI (stationary bootstrap) = ({lo:.3f}, {hi:.3f})")
print(f"deflated sharpe, 10 trials, sr spread 0.4 = {deflated_sharpe(strat, 10, 0.4):.3f}")

# descriptive full-sample fit, for the overlay and the transition matrix only
scaled = StandardScaler().fit_transform(feats.to_numpy(dtype=float))
model = RegimeModel(
    n_states=cfg.hmm.n_states,
    covariance_type=cfg.hmm.covariance_type,
    n_iter=cfg.hmm.n_iter,
    tol=cfg.hmm.tol,
    random_state=cfg.seed,
).fit(scaled, rank_by=feats["vol_21"].to_numpy())

level = np.exp(master["equity_ret"].cumsum())
ax = regime_overlay(level.loc[oos] / level.loc[oos].iloc[0], regimes)
ax.set_title(f"{market.upper()} equity, walk-forward out-of-sample regimes")
ax.figure.savefig(out / f"{market}_regime_overlay.png", dpi=140, bbox_inches="tight")

axes = equity_drawdown(books)
axes[0].set_title(f"{market.upper()} strategy vs benchmarks, net of {cfg.costs_bps} bps")
axes[0].figure.savefig(out / f"{market}_equity_drawdown.png", dpi=140, bbox_inches="tight")

ax = transition_heatmap(model.transition_matrix())
ax.set_title(f"{market.upper()} regime transitions (full-sample fit)")
ax.figure.savefig(out / f"{market}_transition_heatmap.png", dpi=140, bbox_inches="tight")
plt.close("all")

print(f"\nfigures -> {out.resolve()}")
print("transition matrix (rows=from):")
print(np.round(model.transition_matrix(), 3))

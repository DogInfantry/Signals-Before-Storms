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

# Constant risk budget instead of a directional bet: the honest response to states that
# predict variance rather than direction.
books["hmm_vol_targeted"] = run_backtest(regimes, master, cfg, target_vol=0.10)

# Does a directional feature give the state space something to separate crash from rebound?
dd_regimes = run_walk_forward(build_features(master, cfg, drawdown=True), cfg)
books["hmm_drawdown_feat"] = run_backtest(dd_regimes.loc[oos], master, cfg)

# Second engine, optional dependency: uv sync --extra jump
label_sets = {"hmm": regimes, "hmm_drawdown": dd_regimes.loc[oos]}
try:
    jump = run_walk_forward(feats, cfg, engine="jump").loc[oos]
    label_sets["jump"] = jump
    books["jump_regime"] = run_backtest(jump, master, cfg)
except ImportError as exc:
    print(f"[{market}] jump engine skipped: {exc}")


def label_profile(labels):
    """Next-day behaviour of each label, measured at the lag the strategy actually trades."""
    fwd = np.expm1(master.shift(-1)).loc[labels.index]
    rows = []
    for label, grp in fwd.groupby(labels):
        r = grp["equity_ret"].dropna()
        rows.append(
            {
                "label": label,
                "days": len(r),
                "eq_ann_ret": (1 + r).prod() ** (252 / len(r)) - 1,
                "eq_ann_vol": r.std(ddof=1) * np.sqrt(252),
                "eq_sharpe": r.mean() / r.std(ddof=1) * np.sqrt(252),
                "vix_mean": master.loc[grp.index, "vix"].mean(),
            }
        )
    return pd.DataFrame(rows).set_index("label").round(3)


for name, labels in label_sets.items():
    print(f"\n=== {name}: next-day equity by label (does the state predict direction?) ===")
    print(label_profile(labels).to_string())
    print("  mean dwell:", {k: round(v, 1) for k, v in dwell_times(labels.to_numpy()).items()})
if "jump" in label_sets:
    print("  hmm/jump label agreement:", round(float((label_sets["jump"] == regimes).mean()), 3))
# With a cash sleeve in the universe, scoring against rf=0 would hand every defensive book a
# free Sharpe boost for simply holding cash. Charge the cash rate the book could have earned.
rf = 0.0
if "cash_ret" in master.columns:
    cash = np.expm1(master["cash_ret"].loc[oos])
    rf = float((1 + cash).prod() ** (252 / len(cash)) - 1)
    print(f"[{market}] cash sleeve present, scoring Sharpe against rf={rf:.4f}")

table = pd.DataFrame({k: summary(v, rf=rf) for k, v in books.items()}).T
print("\n=== net of costs ===")
print(table.round(3).to_string())

# Honest trial count: rank_vol, rank_return, conditional/unconditional moments, vol rule,
# jump engine, volatility targeting, drawdown feature. Searching more lowers every DSR, which
# is the point of reporting it.
TRIALS = 7
print(f"\n=== deflation, all books, {TRIALS} trials, sr spread 0.4 (excess of rf) ===")
for name, book in books.items():
    excess = book["ret_net"] - rf / 252.0
    lo, hi = bootstrap_ci(excess, n_boot=2000)
    print(
        f"{name:20s} block={optimal_block_length(excess):5.1f}d  "
        f"CI=({lo:6.3f}, {hi:6.3f})  DSR={deflated_sharpe(excess, TRIALS, 0.4):.3f}"
    )

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

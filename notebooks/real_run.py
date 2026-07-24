"""Real-data end-to-end run: cached yfinance master -> features -> walk-forward -> books.

India is the primary universe and the default: NIFTY equity, an overnight cash fund as the
defensive sleeve, and gold. There is deliberately no Indian bond sleeve, because no usable
duration ETF exists on Yahoo for this window (every candidate was measured before being
rejected; see README). US runs the same pipeline as an out-of-sample robustness check.

Prints the scorecard both gross and net of costs, the forward-return-by-label diagnostic and
the deflation table, then writes every figure to results/.

    uv run python notebooks/real_run.py [india|us]
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

from regime_shift.backtest import asset_cols, run_backtest, sensitivity_sweep
from regime_shift.benchmarks import equal_weight, sixty_forty, sixty_forty_target, vol_rule_regimes
from regime_shift.config import load_config
from regime_shift.data import build_master
from regime_shift.features import build_features
from regime_shift.metrics import (
    bootstrap_ci,
    deflated_sharpe,
    episode_profile,
    label_profile,
    optimal_block_length,
    paired_bootstrap,
    sharpe,
    subperiod_summary,
    summary,
)
from regime_shift.plots import (
    bic_curve,
    episode_bars,
    equity_drawdown,
    feature_sanity,
    gross_vs_net,
    label_profile_bars,
    regime_overlay,
    regime_weight_heatmap,
    return_panel,
    rolling_sharpe,
    sensitivity_panel,
    sharpe_forest,
    story_panel,
    transition_heatmap,
    weight_stack,
)
from regime_shift.regime import RegimeModel, bic_sweep, dwell_times
from regime_shift.walkforward import run_walk_forward

warnings.filterwarnings("ignore")
market = sys.argv[1] if len(sys.argv) > 1 else "india"
out = pathlib.Path("results")
out.mkdir(exist_ok=True)


def save(axes, name: str) -> None:
    """Save whatever the plot helpers hand back: a single axis, or an array of them."""
    ax = np.atleast_1d(np.asarray(axes, dtype=object)).ravel()[0]
    ax.figure.savefig(out / f"{market}_{name}.png", dpi=140, bbox_inches="tight")


cfg = load_config()
# Macro is requested explicitly. Where FRED is reachable these become real state variables;
# where it is blocked build_master warns and continues, and the run is macro-free. Passing the
# list is what makes the claim checkable either way.
master = build_master(
    cfg.universes[market], cfg.dates["start"], cfg.dates["end"], cfg.macro_fred_series
)
feats = build_features(master, cfg)
print(f"[{market}] master={master.shape} cols={list(master.columns)}")
print(f"[{market}] features={feats.shape} cols={list(feats.columns)}")

# build_master warns and continues when FRED is unreachable, but this module silences warnings,
# so say it out loud instead. A reader has to know whether the published numbers saw macro.
landed = [s for s in cfg.macro_fred_series if s in master.columns]
print(
    f"[{market}] macro requested={cfg.macro_fred_series} landed={landed or 'NONE'}"
    + ("" if landed else "  <- FRED unreachable, these results are macro-free")
)

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
# Say which asset actually fills the 40%: on India it is cash, not duration, and a reader
# comparing drawdowns deserves to know that without reading the source.
leg = next(k for k in sixty_forty_target(asset_cols(master)) if k != "equity_ret")
print(f"[{market}] 60/40 defensive leg = {leg}")

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

for name, labels in label_sets.items():
    print(f"\n=== {name}: next-day equity by label (does the state predict direction?) ===")
    print(label_profile(labels, master).to_string())
    # The same question at episode granularity. `days` is not a sample size: a label spanning 94
    # days across 2 episodes is n=2, and ann_ret_ex_largest says whether one event is carrying it.
    print(f"--- {name}: by EPISODE, not by day ---")
    print(episode_profile(labels, master).to_string())
if "jump" in label_sets:
    print("\n  hmm/jump label agreement:", round(float((label_sets["jump"] == regimes).mean()), 3))
    print("  labels cross-tab (rows hmm, cols jump):")
    print(pd.crosstab(regimes, label_sets["jump"]).to_string())

# With a cash sleeve in the universe, scoring against rf=0 would hand every defensive book a
# free Sharpe boost for simply holding cash. Charge the cash rate the book could have earned.
rf = 0.0
if "cash_ret" in master.columns:
    cash = np.expm1(master["cash_ret"].loc[oos])
    rf = float((1 + cash).prod() ** (252 / len(cash)) - 1)
    print(f"\n[{market}] cash sleeve present, scoring Sharpe against rf={rf:.4f}")

# Both sides of the cost question, as the brief asks. The gap between the two tables is what
# the churn actually costs, and reporting net alone hides whether the shortfall is stance or
# trading.
for col, header in (("ret_gross", "gross of costs"), ("ret_net", f"net of {cfg.costs_bps} bps")):
    table = pd.DataFrame({k: summary(v, col=col, rf=rf) for k, v in books.items()}).T
    print(f"\n=== {header} ===")
    print(table.round(3).to_string())

# Honest trial count: rank_vol, rank_return, conditional/unconditional moments, vol rule, jump
# engine, volatility targeting, drawdown feature. The cash-leg 60/40 and the cash_ret feature
# fix are a benchmark and a bug fix, not searched variants, so neither moves this count.
TRIALS = 7
# Two block lengths, because they answer two different questions. optimal_block_length reads
# ~2.3 days off RETURN autocorrelation, which is right for a claim about daily returns. A claim
# about a REGIME is supported by how often the regime recurred, and these regimes persist ~25
# days, so the regime-scale interval is the honest one for anything said about the states.
regime_block = float(np.mean(list(dwell_times(regimes.to_numpy()).values())))
print(f"\n=== deflation, all books, {TRIALS} trials, sr spread 0.4 (excess of rf) ===")
print(f"    regime block = {regime_block:.1f}d (mean dwell) vs the return-derived block per row")
sharpes, cis = {}, {}
for name, book in books.items():
    excess = book["ret_net"] - rf / 252.0
    sharpes[name] = sharpe(excess)
    cis[name] = bootstrap_ci(excess, n_boot=2000)
    wide = bootstrap_ci(excess, n_boot=2000, mean_block=regime_block)
    print(
        f"{name:20s} block={optimal_block_length(excess):5.1f}d  "
        f"CI=({cis[name][0]:6.3f}, {cis[name][1]:6.3f})  "
        f"regimeCI=({wide[0]:6.3f}, {wide[1]:6.3f})  "
        f"DSR={deflated_sharpe(excess, TRIALS, 0.4):.3f}"
    )

# Overlapping marginal intervals say nothing about a difference. These books hold the same assets
# on the same days, so the paired difference has far less variance than either book alone: this is
# the test the comparison claim actually rests on.
print("\n=== paired Sharpe difference vs each static benchmark (95%, same resampled dates) ===")
# Feed the SAME excess series the point estimates use. Sharpe is not translation invariant, so
# bootstrapping raw returns against rf-adjusted point estimates silently answers a different
# question and produces an interval that does not bracket its own point estimate.
excess_books = {k: v["ret_net"] - rf / 252.0 for k, v in books.items()}
paired_vs: dict[str, dict[str, tuple[float, float, float]]] = {}
for bench in ("60_40", "equal_weight"):
    print(f"--- vs {bench} ---")
    for name in books:
        if name == bench:
            continue
        d = sharpes[name] - sharpes[bench]
        lo, hi = paired_bootstrap(excess_books[name], excess_books[bench], n_boot=2000)
        verdict = "EXCLUDES 0" if lo > 0 or hi < 0 else "spans 0"
        paired_vs.setdefault(bench, {})[name] = (d, lo, hi)
        print(f"  {name:20s} dSharpe={d:+6.3f}  CI=({lo:+6.3f}, {hi:+6.3f})  {verdict}")

# Does the whole result live inside one market episode? Splits are named from market history, not
# chosen after seeing which ones flatter the strategy.
SPLITS = [
    ("pre_covid", cfg.dates["start"], "2020-02-14"),
    ("covid", "2020-02-15", "2020-12-31"),
    ("post_covid", "2021-01-01", cfg.dates["end"]),
]
print("\n=== sub-period stability (net; days quoted because these blocks are short) ===")
print(subperiod_summary(books, SPLITS, rf=rf).to_string())

# Is the result an artifact of one knob setting? Report the surface, adopt nothing: picking the
# best cell here would spend a DSR trial, which is exactly what the trial count protects.
GRID = {
    "costs_bps": [0.0, 2.5, 5.0, 7.5, 15.0, 25.0],
    "rebalance_confirm_days": [0, 1, 3, 5, 10],
    "weight_cap": [0.4, 0.5, 0.6, 0.8, 1.0],
    "conditional_min_obs": [63, 126, 252],
}
sweep_table = sensitivity_sweep(regimes, master, cfg, GRID, rf=rf, conditional=True)
print("\n=== parameter sensitivity (hmm_conditional; surface reported, nothing adopted) ===")
print(sweep_table.to_string(index=False))

# --- figures -------------------------------------------------------------------------------
# Look at the data before anything clever happens to it, and confirm the volatility feature
# spikes where everyone already knows it should.
save(return_panel(master), "returns")
save(feature_sanity(feats), "feature_sanity")

level = np.exp(master["equity_ret"].cumsum())
ax = regime_overlay(level.loc[oos] / level.loc[oos].iloc[0], regimes)
ax.set_title(f"{market.upper()} equity, walk-forward out-of-sample regimes")
save(ax, "regime_overlay")

axes = equity_drawdown(books)
axes[0].set_title(f"{market.upper()} every book, net of {cfg.costs_bps} bps")
save(axes, "equity_drawdown")

ax = gross_vs_net(books["hmm_conditional"])
ax.set_title(f"{market.upper()} HMM strategy, gross vs net of {cfg.costs_bps} bps")
save(ax, "gross_vs_net")

ax = weight_stack(books["hmm_conditional"], regimes)
ax.set_title(f"{market.upper()} regime-switched weights, regime path in the ribbon above")
save(ax, "weight_stack")

prof = label_profile(regimes, master)
save(label_profile_bars(prof), "label_profile")

# The whole argument as one image: what the states predict, how much evidence is behind it,
# whether any book beats its benchmark, and what the overlay does buy.
fig = story_panel(
    prof,
    regimes,
    master,
    paired_vs["60_40"],
    "60/40",
    {k: float(summary(v, rf=rf)["max_drawdown"]) for k, v in books.items()},
    market=market.upper(),
)
fig.savefig(out / f"{market}_story.png", dpi=140, bbox_inches="tight")

# Effective sample size, made visual: the crisis label's whole reputation is one bar.
ax = episode_bars(regimes, master)
save(ax, "episode_bars")

ax = sharpe_forest(sharpes, cis)
ax.set_title(f"{market.upper()} Sharpe with 95% bootstrap intervals")
save(ax, "sharpe_forest")

ax = regime_weight_heatmap(books["hmm_conditional"])
ax.set_title(f"{market.upper()} mean weight by regime: the stance map in one frame")
save(ax, "regime_weights")

ax = rolling_sharpe(books, rf=rf)
ax.set_title(f"{market.upper()} rolling 252d Sharpe: is any ranking stable through time?")
save(ax, "rolling_sharpe")

axes = sensitivity_panel(sweep_table)
axes[0].figure.suptitle(f"{market.upper()} parameter sensitivity (flat = conclusion is robust)")
save(axes, "sensitivity")

# Descriptive full-sample fit. The overlay above is the honest walk-forward path; the
# transition matrix and the BIC sweep are model diagnostics and feed no trading decision.
scaled = StandardScaler().fit_transform(feats.to_numpy(dtype=float))
hmm_kwargs = {
    "covariance_type": cfg.hmm.covariance_type,
    "n_iter": cfg.hmm.n_iter,
    "tol": cfg.hmm.tol,
    "random_state": cfg.seed,
}
model = RegimeModel(n_states=cfg.hmm.n_states, **hmm_kwargs).fit(
    scaled, rank_by=feats["vol_21"].to_numpy()
)

ax = transition_heatmap(model.transition_matrix())
ax.set_title(f"{market.upper()} regime transitions (full-sample fit)")
save(ax, "transition_heatmap")

sweep = bic_sweep(scaled, **hmm_kwargs)
ax = bic_curve(sweep)
ax.set_title(f"{market.upper()} BIC by state count: no elbow, no support for K=3")
save(ax, "bic_curve")
plt.close("all")

print(f"\nfigures -> {out.resolve()}")
print("BIC sweep:", {k: round(v) for k, v in sweep.items()})
print("transition matrix (rows=from):")
print(np.round(model.transition_matrix(), 3))

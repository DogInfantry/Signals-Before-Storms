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
from regime_shift.data import build_master, load_credit_proxies, load_macro
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
    paired_forest,
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


# Figures the landing page embeds. These also get an SVG, because the page is read on phones and
# a raster plate either blurs when zoomed or ships at four times the weight to avoid it. Vector
# text stays sharp at any size and the line art is smaller than the PNG. The PNG is still written
# for the README and the notebook, and og:image scrapers, which do not render SVG.
SITE_FIGURES = frozenset(
    {
        "story",
        "label_profile",
        "episode_bars",
        "paired_forest",
        "regime_weights",
        "sensitivity",
    }
)
# regime_overlay and equity_drawdown stay raster on purpose. They draw several thousand points
# per series, so the vector version came out 590 kB against a 224 kB PNG: SVG wins on sparse line
# art and loses on a dense multi-year series.


def save_figure(fig, name: str) -> None:
    """Write one figure: always a PNG, plus an SVG when the site embeds it."""
    fig.savefig(out / f"{market}_{name}.png", dpi=140, bbox_inches="tight")
    if name in SITE_FIGURES:
        fig.savefig(out / f"{market}_{name}.svg", format="svg", bbox_inches="tight")


def save(axes, name: str) -> None:
    """Save whatever the plot helpers hand back: a single axis, or an array of them."""
    ax = np.atleast_1d(np.asarray(axes, dtype=object)).ravel()[0]
    save_figure(ax.figure, name)


cfg = load_config()
# The MODEL master is deliberately macro-free. build_features promotes any column that is not an
# asset return and not vix into a state variable, so passing macro here would silently widen the
# feature matrix and move every published number the moment FRED became reachable. Macro is
# loaded separately below and used only as a diagnostic, which keeps the trial count at 7.
master = build_master(cfg.universes[market], cfg.dates["start"], cfg.dates["end"])
feats = build_features(master, cfg)
print(f"[{market}] master={master.shape} cols={list(master.columns)}")
print(f"[{market}] features={feats.shape} cols={list(feats.columns)}")

# Macro, tried in preference order and reported honestly whichever leg answers. FRED is the
# source the brief names, so it is asked first; it has been unreachable from this network since
# 2026-07-24 and still times out, so the Yahoo credit proxies are the fallback that actually
# lands. Both are lagged one day and BOTH are diagnostic: no book trades on either, which is why
# a change of network cannot move a published number.
macro, macro_source = None, "NONE"
try:
    macro = load_macro(cfg.macro_fred_series, cfg.dates["start"], cfg.dates["end"])
    macro_source = f"FRED {cfg.macro_fred_series}"
except Exception as exc:  # noqa: BLE001
    print(f"[{market}] FRED unreachable ({type(exc).__name__}), falling back to Yahoo proxies")
    try:
        macro = load_credit_proxies(cfg.macro_yahoo_proxies, cfg.dates["start"], cfg.dates["end"])
        macro_source = f"Yahoo proxies {list(cfg.macro_yahoo_proxies.values())}"
    except Exception as exc2:  # noqa: BLE001
        print(f"[{market}] Yahoo proxies failed too: {type(exc2).__name__}: {exc2}")

if macro is not None:
    grid = pd.bdate_range(master.index.min(), master.index.max())
    macro = macro.reindex(grid).ffill().shift(1).reindex(master.index)
    macro = macro.loc[:, macro.notna().any()]
print(
    f"[{market}] macro source={macro_source} cols="
    f"{list(macro.columns) if macro is not None else 'NONE'}  (diagnostic only, no book uses it)"
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
save_figure(fig, "story")

# The composite's panels are also written standalone, so the landing page can stack readable
# plates on a narrow viewport instead of shrinking a four-panel image to illegibility.
save(paired_forest(paired_vs["60_40"], "60/40"), "paired_forest")

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

# The credit spread against the same regime path, and the reason macro is worth pulling at all.
# The fitted states order volatility perfectly and direction not at all, because realized vol and
# VIX are both symmetric in sign: they rise in a crash and rise again in the rebound. A credit
# spread is not symmetric. It widens in a credit event and stays wide, and it barely moves in a
# rates selloff, so it separates two episodes that look identical to a volatility feature. That
# is what a directional state variable would have to be built from. Diagnostic, not a feature.
_have = set(macro.columns) if macro is not None else set()
spread_col = next(
    (c for c in ("credit_hy_spread", "BAA10Y", "credit_ig_spread") if c in _have), None
)
if spread_col:
    spread = macro[spread_col].loc[oos].dropna()
    ax = regime_overlay(spread, regimes.loc[spread.index], log=False)
    ax.set_ylabel(f"{spread_col} (up = wider = more stress)")
    ax.set_title(f"{market.upper()} credit spread under the same walk-forward regimes")
    save(ax, "macro_spread")

    # The numeric form of the same claim, so the figure is not carrying it alone.
    print(f"\n=== {spread_col}: does a SIGNED variable separate what volatility cannot? ===")
    EPISODES = (
        ("covid_crash", "2020-02-15", "2020-03-23"),
        ("rates_2022", "2022-01-01", "2022-10-15"),
    )
    for tag, lo_d, hi_d in EPISODES:
        seg = macro[spread_col].loc[lo_d:hi_d].dropna()
        vol = feats["vol_21"].loc[lo_d:hi_d].dropna()
        if len(seg) and len(vol):
            print(
                f"  {tag:12s} spread {seg.iloc[0]:+.3f} -> {seg.iloc[-1]:+.3f} "
                f"(move {seg.iloc[-1] - seg.iloc[0]:+.3f})   vol_21 peak {vol.max():.3f}"
            )

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

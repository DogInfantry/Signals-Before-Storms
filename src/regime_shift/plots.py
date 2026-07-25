"""Plots: regime-overlaid price, equity curve plus drawdown, transition-matrix heatmap. Phase 3+.

Descriptive only. Nothing here feeds a decision, so a whole-sequence Viterbi path is fair game
for the overlay even though the backtest may only ever use the causal filter.

Every function draws on an axis you pass or one it makes, and returns the axis, so the notebook
can compose panels without this module knowing anything about layout or files.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from regime_shift.regime import REGIME_NAMES_3, label_episodes
from regime_shift.style import (
    INK,
    INK_FAINT,
    NEUTRAL,
    REGIME_RAMP,
    SERIES_A,
    SERIES_B,
    SURFACE,
    bar_labels,
    callout,
    pct_axis,
    subtitle,
    use_house_style,
)

use_house_style()

# Ascending risk, encoded as a lightness ramp rather than three arbitrary hues: the regimes are
# ORDERED, so an ordered encoding both says so and survives colour blindness. See style.py for the
# validator result that rejected the previous green/amber/red triad.
REGIME_COLORS = REGIME_RAMP

# Known stress windows, named from memory of the period rather than read off the data, so that
# shading them is a genuine out-of-model check on the volatility features rather than a
# circular one. Used by feature_sanity.
STRESS_SPANS = (
    ("2020-02-15", "2020-05-31", "COVID crash"),
    ("2022-01-01", "2022-10-31", "2022 bear"),
)


def _blocks(labels: pd.Series):
    """Contiguous runs of a single label, as (start, end, label).

    Thin adapter over regime.label_episodes so the project has exactly one run-length
    implementation. The episode count is the sample size behind every regime claim, and two
    implementations that can drift apart are two chances to get that wrong.
    """
    for row in label_episodes(labels).itertuples():
        yield row.start, row.end, int(row.label)


def _names(n: int, names) -> tuple[str, ...]:
    if names is not None:
        return tuple(names)
    return REGIME_NAMES_3 if n == 3 else tuple(f"S{i}" for i in range(n))


def regime_overlay(level: pd.Series, regimes: pd.Series, names=None, ax=None, log: bool = True):
    """Price level with the regime path shaded behind it.

    level: a cumulative growth series, e.g. np.exp(master["equity_ret"].cumsum()). regimes: the
    label path (use the walk-forward OOS labels for the honest picture). Log scale by default,
    because equal vertical distance should mean equal percentage move.
    """
    ax = ax or plt.subplots(figsize=(12, 5))[1]
    labels = regimes.dropna().astype(int)
    shown = _names(int(labels.max()) + 1, names)

    # shade each run up to where the next one starts, otherwise a one-day flicker is a
    # zero-width span and shows up as a white stripe
    blocks = list(_blocks(labels))
    stops = [b[0] for b in blocks[1:]] + [labels.index[-1]]
    for (start, _, label), stop in zip(blocks, stops, strict=True):
        ax.axvspan(start, stop, color=REGIME_COLORS[label % len(REGIME_COLORS)], alpha=0.18, lw=0)

    ax.plot(level.index, level.to_numpy(), color=INK, lw=1.0)
    if log:
        ax.set_yscale("log")
    ax.set_xlim(labels.index[0], labels.index[-1])
    ax.set_ylabel("growth of 1")
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=REGIME_COLORS[i % len(REGIME_COLORS)], alpha=0.35)
        for i in range(len(shown))
    ]
    ax.legend(handles, shown, loc="upper left", frameon=False, ncols=len(shown))
    return ax


def equity_drawdown(books: dict, col: str = "ret_net", axes=None):
    """Growth of 1 for each book in `books`, with the drawdowns underneath.

    Drawdowns are lines rather than filled bands so several strategies stay legible together.
    """
    if axes is None:
        _, axes = plt.subplots(
            2, 1, figsize=(12, 7), sharex=True, gridspec_kw={"height_ratios": [2, 1]}
        )
    top, bottom = axes

    for name, book in books.items():
        eq = (1.0 + book[col]).cumprod()
        line = top.plot(eq.index, eq.to_numpy(), lw=1.3, label=name)[0]
        dd = eq / eq.cummax() - 1.0
        bottom.plot(dd.index, dd.to_numpy(), lw=1.0, color=line.get_color())

    top.set_yscale("log")
    top.set_ylabel("growth of 1")
    top.legend(frameon=False, ncols=len(books))
    bottom.set_ylabel("drawdown")
    bottom.axhline(0.0, color=INK, lw=0.6)
    return axes


def return_panel(master: pd.DataFrame, axes=None):
    """Raw daily log returns per asset, each with its marginal distribution beside it.

    The first thing to do with price data is look at it, before anything clever happens to it.
    Two properties are visible here with no model fitted at all, and both are why a regime
    model is plausible in the first place: volatility clusters (the series breathes in and out
    rather than holding a constant width), and the marginals are far too fat-tailed to be
    Gaussian. The count axis is logarithmic, because on a linear one the tails that matter are
    invisible.
    """
    cols = [c for c in master.columns if c.endswith("_ret")]
    if not cols:
        raise ValueError(f"no *_ret columns to plot in {list(master.columns)}")
    if axes is None:
        _, axes = plt.subplots(
            len(cols),
            2,
            figsize=(12, 2.1 * len(cols)),
            sharex="col",
            gridspec_kw={"width_ratios": [3, 1], "wspace": 0.05},
        )
    axes = np.atleast_2d(axes)

    for (ts, marg), col in zip(axes, cols, strict=True):
        r = master[col].dropna()
        ts.plot(r.index, r.to_numpy(), lw=0.4, color=NEUTRAL)
        ts.axhline(0.0, color=INK, lw=0.5)
        ts.set_ylabel(col.removesuffix("_ret"))
        marg.hist(r.to_numpy(), bins=80, orientation="horizontal", color=NEUTRAL)
        marg.set_xscale("log")
        marg.set_ylim(ts.get_ylim())  # same return scale, so the tails line up across panels
        marg.tick_params(labelleft=False)

    axes[0, 0].set_title("daily log returns")
    axes[0, 1].set_title("marginal (log count)")
    return axes


def feature_sanity(feats: pd.DataFrame, spans=STRESS_SPANS, cols=("vol_21", "vix"), axes=None):
    """Stress-sensitive features over time with known crisis windows shaded.

    The check every downstream claim rests on: if realized volatility does not spike where
    everyone already knows the market was stressed, the feature is broken and the regimes
    fitted on it mean nothing.
    """
    cols = [c for c in cols if c in feats.columns]
    if not cols:
        raise ValueError(f"none of the requested columns are in {list(feats.columns)}")
    if axes is None:
        _, axes = plt.subplots(len(cols), 1, figsize=(12, 2.6 * len(cols)), sharex=True)
    axes = np.atleast_1d(axes)

    for ax, col in zip(axes, cols, strict=True):
        ax.plot(feats.index, feats[col].to_numpy(), lw=0.9, color=NEUTRAL)
        for start, stop, _ in spans:
            ax.axvspan(
                pd.Timestamp(start), pd.Timestamp(stop), color=REGIME_COLORS[2], alpha=0.16, lw=0
            )
        ax.set_ylabel(col)

    top = axes[0]
    for start, stop, name in spans:
        mid = pd.Timestamp(start) + (pd.Timestamp(stop) - pd.Timestamp(start)) / 2
        top.annotate(
            name, (mid, top.get_ylim()[1]), ha="center", va="top", fontsize=9, color=SERIES_B
        )
    return axes


def gross_vs_net(book: pd.DataFrame, ax=None):
    """Growth of 1 before and after transaction costs, with the compounding drag shaded.

    The gap between the two lines IS the cost of the strategy's churn, and it compounds: a book
    turning over four times a year at 7.5 bps pays far more over seven years than four times
    7.5 bps suggests. Reporting net alone hides how much of the shortfall is trading rather
    than stance.
    """
    ax = ax or plt.subplots(figsize=(12, 5))[1]
    gross, net = book["equity_gross"], book["equity_net"]
    ax.plot(gross.index, gross.to_numpy(), lw=1.3, color=NEUTRAL, label="gross of costs")
    ax.plot(net.index, net.to_numpy(), lw=1.3, color=SERIES_B, label="net of costs")
    ax.fill_between(
        net.index,
        net.to_numpy(),
        gross.to_numpy(),
        color=SERIES_B,
        alpha=0.20,
        lw=0,
        label="cumulative cost drag",
    )
    ax.set_yscale("log")
    ax.set_ylabel("growth of 1")
    ax.legend(frameon=False)
    return ax


def weight_stack(book: pd.DataFrame, regimes: pd.Series | None = None, ax=None):
    """Stacked portfolio weights over time, with the regime path as a ribbon above them.

    The stance map as a picture: the weights have to visibly move when the ribbon changes
    colour, or the regimes are not driving anything. The ribbon sits above the stack rather
    than behind it so it can never be mistaken for a weight.
    """
    wcols = [c for c in book.columns if c.startswith("w_")]
    if not wcols:
        raise ValueError("book carries no w_<asset> columns")
    ax = ax or plt.subplots(figsize=(12, 5))[1]

    ax.stackplot(
        book.index,
        *[book[c].to_numpy() for c in wcols],
        labels=[c[2:] for c in wcols],
        alpha=0.85,
    )
    ax.set_ylim(0.0, 1.16)
    ax.set_ylabel("weight")

    if regimes is not None:
        labels = regimes.reindex(book.index).ffill().dropna().astype(int)
        blocks = list(_blocks(labels))
        stops = [b[0] for b in blocks[1:]] + [labels.index[-1]]
        for (start, _, label), stop in zip(blocks, stops, strict=True):
            ax.axvspan(
                start,
                stop,
                ymin=1.02 / 1.16,
                ymax=1.0,
                color=REGIME_COLORS[label % len(REGIME_COLORS)],
                lw=0,
            )
    ax.legend(frameon=False, ncols=len(wcols), loc="lower left")
    return ax


def label_profile_bars(profile: pd.DataFrame, names=None, ax=None):
    """Annualized next-day return and volatility per regime label, with the contradiction marked.

    The central finding of the whole project, and the one figure that has to work without a
    caption. Volatility rises with the label exactly as the ranking intends, so the model is doing
    what it was asked. Return rises with it too, and that is the wrong direction.

    The dashed guide is what a working risk signal would have to look like: return FALLING as risk
    climbs. Drawing the expectation next to the measurement is the difference between a reader
    seeing the finding and being told it.
    """
    ax = ax or plt.subplots(figsize=(9, 5.2))[1]
    shown = _names(len(profile), names)
    x = np.arange(len(profile))
    ret = profile["eq_ann_ret"].to_numpy(dtype=float)
    vol = profile["eq_ann_vol"].to_numpy(dtype=float)

    b1 = ax.bar(x - 0.21, ret, 0.4, label="next-day return", color=SERIES_A, zorder=3)
    b2 = ax.bar(x + 0.21, vol, 0.4, label="next-day volatility", color=SERIES_B, zorder=3)
    bar_labels(ax, b1, dy=vol.max() * 0.015)
    bar_labels(ax, b2, dy=vol.max() * 0.015)

    # what a signal that actually predicted direction would look like: return falling with risk
    guide = np.linspace(ret.max(), ret.min() * 0.35, len(x))
    ax.plot(x - 0.21, guide, ls=(0, (4, 3)), lw=1.6, color=INK_FAINT, zorder=4)
    # annotations sit in the empty band above the low bars and below the legend, and point at the
    # marks from the side, so neither one lands on a value label
    span = float(guide[0] - guide[-1])
    ax.annotate(
        "what a working risk signal\nwould look like",
        xy=(x[0] + 0.55, guide[0] - 0.76 * span * (0.55 + 0.21) / max(len(x) - 1, 1)),
        xytext=(x[0] + 0.15, vol.max() * 0.70),
        fontsize=9,
        color=INK_FAINT,
        ha="center",
        arrowprops={"arrowstyle": "->", "color": INK_FAINT, "lw": 1.1},
    )
    callout(
        ax,
        "measured: return RISES with risk",
        xy=(x[-1] - 0.40, ret[-1] * 0.95),
        xytext=(x[-1] - 0.85, vol.max() * 0.93),
    )

    ax.set_xticks(x, [f"{i}  {n}" for i, n in enumerate(shown)])
    ax.set_ylabel("annualized, next day")
    pct_axis(ax)
    ax.set_ylim(0, vol.max() * 1.18)
    ax.legend(loc="upper left", ncols=2)
    subtitle(
        ax,
        "Volatility orders correctly. Return orders backwards, so de-risking sells the best days.",
    )
    return ax


def bic_curve(sweep: dict, ax=None):
    """BIC against state count.

    A model finding genuinely discrete states shows an elbow: one state past the true count
    stops buying much fit. A monotone decline says the opposite, that the fit is carving up a
    fat-tailed continuum and would happily keep taking states forever, which is no support for
    any particular K.
    """
    ax = ax or plt.subplots(figsize=(6, 4))[1]
    ks = sorted(sweep)
    ax.plot(ks, [sweep[k] for k in ks], marker="o", color=NEUTRAL)
    ax.set_xticks(ks)
    ax.set_xlabel("n_states")
    ax.set_ylabel("BIC (lower is better)")
    return ax


def sharpe_forest(sharpes: dict, cis: dict, ax=None):
    """Per-book Sharpe with its bootstrap confidence interval, sorted, zero marked.

    Point estimates invite a ranking; the intervals show how little that ranking is worth. A
    book whose interval straddles zero has demonstrated no skill at all, however it placed.
    """
    ax = ax or plt.subplots(figsize=(8, 0.45 * len(sharpes) + 1.5))[1]
    order = sorted(sharpes, key=lambda k: sharpes[k])
    y = np.arange(len(order))
    lo = [cis[k][0] for k in order]
    hi = [cis[k][1] for k in order]

    ax.hlines(y, lo, hi, color=NEUTRAL, lw=1.4)
    # colour on whether the interval clears zero, not on rank: that is the claim being made, and
    # it is the same encoding paired_forest uses, so the two forests read the same way
    ax.scatter(
        [sharpes[k] for k in order],
        y,
        zorder=3,
        color=[NEUTRAL if x <= 0 else SERIES_A for x in lo],
    )
    ax.axvline(0.0, color=INK, lw=0.8, ls="--")
    ax.set_yticks(y, order)
    ax.set_xlabel("Sharpe (95% stationary-bootstrap interval)")
    return ax


def episode_bars(labels: pd.Series, master: pd.DataFrame, label: int | None = None, ax=None):
    """One bar per episode of a regime: how that episode actually paid, in date order.

    The figure that makes effective sample size impossible to ignore. A state that genuinely
    predicts down moves shows a row of negative bars. A state whose whole reputation rests on one
    crash shows a single deep bar and a crowd of positive ones, and no amount of day-count
    n = 1814 makes that a repeatable effect.

    Bar width is proportional to episode length, so the eye weights a 64-day episode above a
    3-day flicker rather than treating every run as one vote.
    """
    labels = pd.Series(labels).dropna().astype(int)
    label = int(labels.max()) if label is None else label
    eps = label_episodes(labels)
    eps = eps[eps["label"] == label]
    if eps.empty:
        raise ValueError(f"no episodes for label {label}")

    fwd = np.expm1(master.shift(-1)).loc[labels.index, "equity_ret"]
    idx = labels.index
    rets, widths, centres, pos = [], [], [], 0.0
    for start, end, days in zip(eps["start"], eps["end"], eps["days"], strict=True):
        r = fwd[(idx >= start) & (idx <= end)].dropna()
        rets.append(float((1.0 + r).prod() - 1.0))
        w = float(days)
        widths.append(w)
        centres.append(pos + w / 2.0)
        pos += w * 1.25  # a gap, so adjacent episodes stay countable

    ax = ax or plt.subplots(figsize=(11, 4.5))[1]
    ax.bar(
        centres,
        rets,
        width=widths,
        # sign by the validated two-series pair, never green/red: the zero rule already carries
        # sign, so hue reinforces it rather than being the only channel that says it
        color=[SERIES_B if v < 0 else SERIES_A for v in rets],
        edgecolor=SURFACE,  # a 2px surface gap, so adjacent episodes stay countable
        linewidth=1.2,
        zorder=3,
    )
    ax.axhline(0.0, color=INK, lw=0.9, zorder=4)
    pct_axis(ax, decimals=0)
    ax.grid(axis="x", visible=False)
    # Label only episodes wide enough to carry text. A three-day flicker and a sixty-day crisis
    # both get a bar, but only the second gets a date, otherwise the short ones overprint.
    floor = 0.04 * pos
    ax.set_xticks(
        centres,
        [
            pd.Timestamp(s).strftime("%Y-%m") if w >= floor else ""
            for s, w in zip(eps["start"], widths, strict=True)
        ],
        rotation=90,
    )
    ax.set_ylabel("episode cumulative return")
    neg = sum(v < 0 for v in rets)
    subtitle(
        ax,
        f"Crisis label: {len(rets)} episodes over {int(eps['days'].sum())} days, only {neg} "
        f"negative. Bar width = duration.",
    )
    return ax


def regime_weight_heatmap(book: pd.DataFrame, names=None, ax=None):
    """Mean portfolio weight per asset per regime: the stance map as one object.

    The weight stack shows the same information as a time series, which is the right figure for
    asking WHEN the book moved. This one answers WHAT each regime actually buys, and makes the
    project's central problem legible at a glance: equity gets a small allocation in the calm
    state and a smaller one everywhere else, so there is no state in which the book is positioned
    to earn the returns the crisis label turns out to deliver.
    """
    wcols = [c for c in book.columns if c.startswith("w_")]
    if not wcols or "regime" not in book.columns:
        raise ValueError("book needs a regime column and at least one w_<asset> column")
    grid = book.dropna(subset=["regime"]).groupby("regime")[wcols].mean()
    shown = _names(int(grid.index.max()) + 1, names)

    ax = ax or plt.subplots(figsize=(1.5 * len(wcols) + 3, 0.8 * len(grid) + 2))[1]
    im = ax.imshow(grid.to_numpy(), cmap="Blues", vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(wcols)), [c[2:] for c in wcols])
    ax.set_yticks(range(len(grid)), [f"{int(i)} {shown[int(i)]}" for i in grid.index])
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            v = grid.iat[i, j]
            ax.text(
                j, i, f"{v:.2f}", ha="center", va="center",
                color="white" if v > 0.5 else INK,
            )
    ax.figure.colorbar(im, ax=ax, shrink=0.8, label="mean weight")
    return ax


def rolling_sharpe(books: dict, window: int = 252, col: str = "ret_net", rf: float = 0.0, ax=None):
    """Trailing annualized Sharpe per book.

    A full-sample Sharpe is one number standing in for seven years, and it cannot say whether a
    ranking held throughout or was decided by one stretch. If the lines cross repeatedly, the
    league table at the end of the run is an end-point artifact and should not be read as a
    ranking at all.
    """
    ax = ax or plt.subplots(figsize=(12, 5))[1]
    for name, book in books.items():
        excess = book[col] - rf / 252.0
        roll = (
            excess.rolling(window).mean() / excess.rolling(window).std() * np.sqrt(252)
        ).dropna()
        ax.plot(roll.index, roll.to_numpy(), lw=1.2, label=name)
    ax.axhline(0.0, color=INK, lw=0.8, ls="--")
    ax.set_ylabel(f"rolling {window}d Sharpe")
    ax.legend(frameon=False, ncols=3, fontsize=8)
    return ax


def sensitivity_panel(table: pd.DataFrame, metric: str = "sharpe", axes=None):
    """Small multiples of the parameter sweep: one panel per knob, shipped default marked.

    Reads the tidy frame from backtest.sensitivity_sweep. Flat lines are the good outcome: they
    say the conclusion does not depend on the knob. A steep line says the headline number is
    really a statement about that setting, and should be reported as such.
    """
    knobs = list(dict.fromkeys(table["knob"]))
    if axes is None:
        _, axes = plt.subplots(1, len(knobs), figsize=(3.2 * len(knobs), 3.2), sharey=True)
    axes = np.atleast_1d(axes)

    for ax, knob in zip(axes, knobs, strict=True):
        sub = table[table["knob"] == knob].sort_values("value")
        ax.plot(sub["value"], sub[metric], marker="o", color=NEUTRAL)
        shipped = sub[sub["is_default"]]
        if not shipped.empty:
            ax.scatter(
                shipped["value"], shipped[metric], s=110, facecolors="none",
                edgecolors=SERIES_B, lw=2, zorder=3, label="shipped default",
            )
            ax.legend(frameon=False, fontsize=8)
        ax.set_xlabel(knob)
    axes[0].set_ylabel(metric)
    return axes


def paired_forest(paired: dict, bench: str, ax=None):
    """Sharpe DIFFERENCE against one benchmark, with its paired bootstrap interval.

    The correct object for a comparison, and a different question from the per-book intervals in
    sharpe_forest. Those ask whether a book beats zero; this asks whether it beats the benchmark.
    Zero is the only line that matters, so it is the only line drawn.
    """
    ax = ax or plt.subplots(figsize=(8, 0.5 * len(paired) + 1.6))[1]
    order = sorted(paired, key=lambda k: paired[k][0])
    y = np.arange(len(order))
    diff = [paired[k][0] for k in order]
    lo = [paired[k][1] for k in order]
    hi = [paired[k][2] for k in order]
    # an interval clearing zero is the only thing that would count as beating the benchmark
    clears = [a > 0 or b < 0 for a, b in zip(lo, hi, strict=True)]

    ax.hlines(y, lo, hi, color=INK_FAINT, lw=2.2, zorder=2)
    ax.scatter(diff, y, s=46, zorder=3, color=[SERIES_A if c else NEUTRAL for c in clears])
    ax.axvline(0.0, color=INK, lw=1.3, ls="--", zorder=1)
    ax.set_yticks(y, order)
    ax.set_xlabel(f"Sharpe difference vs {bench}  (95% paired bootstrap)")
    ax.grid(axis="y", visible=False)
    subtitle(ax, "Every interval spans zero: no book separates from the benchmark.")
    return ax


def story_panel(
    profile, labels, master, paired, bench: str, drawdowns: dict, market: str = "", fig=None
):
    """The whole argument as one figure: what the model found, and what it is worth.

    Four panels in reading order. What the states predict (and fail to), how much evidence sits
    behind that, whether any book actually beats its benchmark, and what the overlay does buy.
    Built for the top of a README, where a reader gives a project about ten seconds.
    """
    fig = fig or plt.figure(figsize=(15.5, 9.6))
    gs = fig.add_gridspec(2, 2, hspace=0.42, wspace=0.20)

    label_profile_bars(profile, ax=fig.add_subplot(gs[0, 0]))
    episode_bars(labels, master, ax=fig.add_subplot(gs[0, 1]))
    paired_forest(paired, bench, ax=fig.add_subplot(gs[1, 0]))

    ax4 = fig.add_subplot(gs[1, 1])
    dd = dict(sorted(drawdowns.items(), key=lambda kv: kv[1]))
    names = list(dd)
    bars = ax4.bar(
        np.arange(len(names)),
        [dd[n] for n in names],
        0.62,
        color=[SERIES_A if abs(dd[n]) < 0.10 else SERIES_B for n in names],
        zorder=3,
    )
    bar_labels(ax4, bars, dy=0.004)
    ax4.set_xticks(np.arange(len(names)), names, rotation=20, ha="right")
    pct_axis(ax4)
    ax4.set_ylabel("worst drawdown")
    ax4.grid(axis="x", visible=False)
    ax4.set_ylim(min(dd.values()) * 1.22, 0)  # headroom, else the deepest label clips off-axis
    subtitle(ax4, "What it DOES buy: a fraction of the benchmark's worst loss.")

    fig.suptitle(
        f"{market} regime overlay: the model works, the bet does not".strip(),
        fontsize=15,
        weight="semibold",
        color=INK,
        x=0.008,
        ha="left",
        y=0.99,
    )
    return fig


def transition_heatmap(matrix, names=None, ax=None):
    """Regime transition probabilities. The diagonal is the story: regimes are sticky."""
    p = np.asarray(matrix, dtype=float)
    ax = ax or plt.subplots(figsize=(5, 4))[1]
    labels = _names(p.shape[0], names)

    im = ax.imshow(p, cmap="Blues", vmin=0.0, vmax=1.0)
    ax.set_xticks(range(len(labels)), labels)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("to")
    ax.set_ylabel("from")
    for i in range(p.shape[0]):
        for j in range(p.shape[1]):
            ax.text(
                j,
                i,
                f"{p[i, j]:.2f}",
                ha="center",
                va="center",
                color="white" if p[i, j] > 0.5 else INK,
            )
    ax.figure.colorbar(im, ax=ax, shrink=0.8)
    return ax

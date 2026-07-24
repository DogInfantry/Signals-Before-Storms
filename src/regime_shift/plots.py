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

REGIME_COLORS = ("#2e7d32", "#f9a825", "#c62828")  # ascending risk: calm, stressed, crisis

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

    ax.plot(level.index, level.to_numpy(), color="black", lw=1.0)
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
    bottom.axhline(0.0, color="black", lw=0.6)
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
        ts.plot(r.index, r.to_numpy(), lw=0.4, color="#37474f")
        ts.axhline(0.0, color="black", lw=0.5)
        ts.set_ylabel(col.removesuffix("_ret"))
        marg.hist(r.to_numpy(), bins=80, orientation="horizontal", color="#37474f")
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
        ax.plot(feats.index, feats[col].to_numpy(), lw=0.9, color="#37474f")
        for start, stop, _ in spans:
            ax.axvspan(
                pd.Timestamp(start), pd.Timestamp(stop), color=REGIME_COLORS[2], alpha=0.16, lw=0
            )
        ax.set_ylabel(col)

    top = axes[0]
    for start, stop, name in spans:
        mid = pd.Timestamp(start) + (pd.Timestamp(stop) - pd.Timestamp(start)) / 2
        top.annotate(
            name, (mid, top.get_ylim()[1]), ha="center", va="top", fontsize=9, color="#c62828"
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
    ax.plot(gross.index, gross.to_numpy(), lw=1.3, color="#37474f", label="gross of costs")
    ax.plot(net.index, net.to_numpy(), lw=1.3, color="#c62828", label="net of costs")
    ax.fill_between(
        net.index,
        net.to_numpy(),
        gross.to_numpy(),
        color="#c62828",
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
    """Annualized next-day return and volatility per regime label, side by side.

    The central finding in one frame. Volatility rises monotonically with the label, exactly as
    the vol ranking intends. Return rises with it too, and that is the wrong direction: a book
    that de-risks as the label climbs is selling its best days. For the bet to pay, the return
    bars would have to FALL as the risk label rises.
    """
    ax = ax or plt.subplots(figsize=(8, 4.5))[1]
    shown = _names(len(profile), names)
    x = np.arange(len(profile))

    ax.bar(x - 0.2, profile["eq_ann_ret"], 0.4, label="next-day ann return", color="#2e7d32")
    ax.bar(x + 0.2, profile["eq_ann_vol"], 0.4, label="next-day ann vol", color="#c62828")
    ax.axhline(0.0, color="black", lw=0.6)
    ax.set_xticks(x, [f"{i} {n}" for i, n in enumerate(shown)])
    ax.set_ylabel("annualized")
    ax.legend(frameon=False)
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
    ax.plot(ks, [sweep[k] for k in ks], marker="o", color="#37474f")
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

    ax.hlines(y, lo, hi, color="#37474f", lw=1.4)
    # colour on whether the interval clears zero, not on rank: that is the claim being made
    ax.scatter(
        [sharpes[k] for k in order],
        y,
        zorder=3,
        color=["#c62828" if x <= 0 else "#2e7d32" for x in lo],
    )
    ax.axvline(0.0, color="black", lw=0.8, ls="--")
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
        color=["#c62828" if v < 0 else "#2e7d32" for v in rets],
        edgecolor="white",
    )
    ax.axhline(0.0, color="black", lw=0.8)
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
    ax.set_title(
        f"label {label}: {len(rets)} episodes over {int(eps['days'].sum())} days, "
        f"{neg} negative (bar width = days)"
    )
    return ax


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
                color="white" if p[i, j] > 0.5 else "black",
            )
    ax.figure.colorbar(im, ax=ax, shrink=0.8)
    return ax

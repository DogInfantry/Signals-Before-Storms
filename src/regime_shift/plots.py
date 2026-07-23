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

from regime_shift.regime import REGIME_NAMES_3

REGIME_COLORS = ("#2e7d32", "#f9a825", "#c62828")  # ascending risk: calm, stressed, crisis


def _blocks(labels: pd.Series):
    """Contiguous runs of a single label, as (start, end, label)."""
    runs = labels.ne(labels.shift()).cumsum()
    for _, grp in labels.groupby(runs):
        yield grp.index[0], grp.index[-1], int(grp.iloc[0])


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

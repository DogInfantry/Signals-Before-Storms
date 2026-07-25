"""House chart style: one place that decides what every figure in this project looks like.

Two rules drive everything here.

**Colour is computed, not chosen.** Every palette below is run through `tools/validate_palette.py`
rather than picked by eye, and `tests/test_style.py` fails the build if one stops clearing the
floors. The validator has caught two real defects in palettes this project actually shipped: the
old Bear amber sat at 1.92:1 contrast against the chart surface, and its replacement Bull gold at
1.80:1, both under the 3:1 floor.

It also corrected this docstring. An earlier version claimed the old green/amber/red triad had a
"worst adjacent pair separated by ~3 units where 8 is the floor". That number does not reproduce:
measured, the triad's worst pair is 17.2 dE, comfortably above the floor, because those three
colours differ enough in LIGHTNESS to stay separable. The real defect is one the dE never sees.
After simulating a dichromat the triad collapses to a single hue, its pairs landing 0.6, 1.1 and
1.4 degrees apart, so the colours are distinguishable only by being lighter or darker. That is why
the validator checks hue separation as well, and why sign is encoded blue against orange (166.6
degrees) instead of green against red (1.1).

**Regimes are ordinal, not categorical.** They run Bull -> Bear -> Crisis in ascending risk, so
they get a sequential ramp ordered by lightness rather than three arbitrary hues. That encodes the
ordering the data actually has, and it survives colour blindness because lightness does.
"""

from __future__ import annotations

import matplotlib as mpl

# Sequential risk ramp, lightness-ordered light -> dark. Ordinal data, ordinal encoding.
# Measured 3.17:1, 6.27:1 and 11.90:1 against the surface, worst pairwise CVD separation 23.4.
# The previous light end (#e8b84b) sat at 1.80:1, WORSE than the 1.92:1 amber this module's
# docstring condemns, and shipped that way until the validator below was written and run. Contrast
# is quoted at full opacity because that is how the legend swatch and the weight-stack ribbon draw
# it; the time-series washes dilute the same hues with alpha and come out lighter by construction.
REGIME_RAMP = ("#b8860b", "#9e4310", "#6b1210")

# Two-series categorical pair. Validated: all checks pass, worst CVD separation 19.9 (protan)
# against a floor of 8, contrast >= 3:1 on both.
SERIES_A = "#1a6ca8"  # return
SERIES_B = "#c8501e"  # volatility, cost, whatever works against you

INK = "#1c1c1c"
INK_SOFT = "#5c5c5c"
INK_FAINT = "#8a8a8a"
SURFACE = "#fcfcfb"
NEUTRAL = "#37474f"

# Every group is checked by tools/validate_palette.py and pinned by tests/test_style.py. Each one
# declares WHICH CHANNEL it encodes with, because that decides which floor applies to it:
#
#   contrast   >= 3:1 vs SURFACE          every colour, no exceptions
#   dE         >= 8 units                 every pair, after protanope and deuteranope simulation
#   hue        >= 90 degrees              pairs in a "hue" palette only
#
# The hue floor is the one that matters and it is why sign is not encoded green/red. Simulate a
# dichromat and green #2e7d32 and red #c62828 land 1.1 degrees apart in hue: to that reader they
# are one colour at two lightnesses. SERIES_A against SERIES_B lands 166.6 degrees apart, which is
# why it is the pair every sign encoding in this project uses.
#
# A "lightness" palette is exempt from the hue floor by design rather than by convenience. The
# regime ramp is ordinal and encodes its order as lightness, so constant hue is the intent, not a
# defect. The verdict pair is binary and is always drawn against the zero rule, so position states
# the distinction and colour only reinforces it.
PALETTES = {
    "regime": (REGIME_RAMP, "lightness"),
    "series": ((SERIES_A, SERIES_B), "hue"),
    "verdict": ((SERIES_A, NEUTRAL), "lightness"),
}

# Every ink value that lands on the chart surface as a mark or a rule.
INKS = (INK, INK_SOFT, INK_FAINT, NEUTRAL)


def use_house_style() -> None:
    """Set rcParams for every figure. Called once at import time by plots."""
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            # recessive chrome: the data should be the darkest thing on the page
            "axes.edgecolor": INK_FAINT,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": INK_SOFT,
            "axes.labelsize": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "semibold",
            "axes.titlecolor": INK,
            "axes.titlelocation": "left",
            "axes.titlepad": 10,
            "axes.grid": True,
            "grid.color": "#e4e4e1",
            "grid.linewidth": 0.7,
            "axes.axisbelow": True,  # grid behind the marks, never through them
            "xtick.color": INK_SOFT,
            "ytick.color": INK_SOFT,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "legend.frameon": False,
            "legend.fontsize": 9.5,
            "font.size": 10,
            "figure.dpi": 140,
        }
    )


def pct_axis(ax, axis: str = "y", decimals: int = 0) -> None:
    """Percentages, because 0.184 is a number and 18.4% is a fact."""
    fmt = mpl.ticker.PercentFormatter(xmax=1.0, decimals=decimals)
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def callout(ax, text: str, xy, xytext, color: str = SERIES_B) -> None:
    """A pointed annotation. Used only where the reader would otherwise miss the point."""
    ax.annotate(
        text,
        xy=xy,
        xytext=xytext,
        fontsize=9.5,
        color=color,
        weight="semibold",
        ha="center",
        arrowprops={"arrowstyle": "->", "color": color, "lw": 1.4, "shrinkA": 2, "shrinkB": 4},
    )


def bar_labels(ax, bars, fmt="{:.1%}", color: str = INK_SOFT, dy: float = 0.004) -> None:
    """Direct-label bars so the reader never has to trace a value back to an axis."""
    for b in bars:
        h = b.get_height()
        ax.text(
            b.get_x() + b.get_width() / 2,
            h + dy if h >= 0 else h - dy,
            fmt.format(h),
            ha="center",
            va="bottom" if h >= 0 else "top",
            fontsize=9,
            color=color,
        )


def subtitle(ax, text: str) -> None:
    """One plain-language line under the title saying what to SEE.

    A chart that needs a paragraph of surrounding prose to be understood has failed.
    """
    ax.set_title(text, fontsize=9.5, color=INK_SOFT, weight="normal", loc="left", pad=6)

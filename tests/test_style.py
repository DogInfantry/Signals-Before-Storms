"""The palette claim, as a test rather than a sentence.

`style.py` says its colours were computed rather than chosen. These tests are what make that true:
they run the validator, so a palette cannot be edited into the module without clearing the floors
the module advertises.

The last test is the important one. It reintroduces the exact green/red pair this project used to
encode sign with and asserts the validator rejects it, so the guard is demonstrated to bite rather
than merely to exist.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from validate_palette import (  # noqa: E402
    CONTRAST_FLOOR,
    CVD_FLOOR,
    HUE_FLOOR,
    contrast_ratio,
    failures,
    worst_cvd_distance,
    worst_hue_separation,
)

from regime_shift.style import INKS, PALETTES, SURFACE

_COLOURS = [(g, c) for g, (cs, _) in PALETTES.items() for c in cs] + [("ink", c) for c in INKS]
_PAIRS = [
    (g, ch, a, b)
    for g, (cs, ch) in PALETTES.items()
    for i, a in enumerate(cs)
    for b in cs[i + 1 :]
]


def test_no_palette_violates_either_floor():
    assert failures() == []


@pytest.mark.parametrize(("group", "colour"), _COLOURS)
def test_every_colour_clears_the_contrast_floor(group, colour):
    ratio = contrast_ratio(colour, SURFACE)
    assert ratio >= CONTRAST_FLOOR, f"{group}: {colour} is {ratio:.2f}:1 against the surface"


@pytest.mark.parametrize(("group", "channel", "a", "b"), _PAIRS)
def test_every_pair_survives_colour_blindness(group, channel, a, b):
    dist, kind = worst_cvd_distance(a, b)
    assert dist >= CVD_FLOOR, f"{group}: {a} vs {b} is {dist:.1f} units as a {kind}ope"


@pytest.mark.parametrize(("group", "channel", "a", "b"), _PAIRS)
def test_hue_encodings_do_not_lean_on_lightness(group, channel, a, b):
    """A palette that says it encodes by hue has to still do so once hue is degraded."""
    if channel != "hue":
        pytest.skip(f"{group} encodes by {channel}, so a constant hue is the intent")
    gap, kind = worst_hue_separation(a, b)
    assert gap >= HUE_FLOOR, f"{group}: {a} vs {b} is {gap:.1f} degrees apart as a {kind}ope"


def test_the_regime_ramp_is_ordered_by_lightness():
    """Regimes are ordinal, so the encoding has to be too, and lightness survives CVD."""
    contrasts = [contrast_ratio(c, SURFACE) for c in PALETTES["regime"][0]]
    assert contrasts == sorted(contrasts), f"ramp is not monotone in lightness: {contrasts}"


def test_the_hue_floor_rejects_the_green_red_sign_pair():
    """The guard has to bite.

    This is the pair three figures in this project used to encode sign with. It passes the dE
    floor at 17.2, which is exactly why the hue floor exists: a dichromat separates these two by
    lightness and by nothing else, so the encoding fails wherever lightness is unreliable.
    """
    dist, _ = worst_cvd_distance("#2e7d32", "#c62828")
    gap, _ = worst_hue_separation("#2e7d32", "#c62828")
    assert dist >= CVD_FLOOR, "green/red is distinguishable by lightness, as measured"
    assert gap < HUE_FLOOR, (
        f"green/red sits {gap:.1f} degrees apart in simulated hue, which would mean the floor "
        "no longer catches the defect this module was written to prevent"
    )

"""Check every palette this project ships against a contrast floor and a colour-blindness floor.

`style.py` has always claimed its palettes were "run through a contrast and colour-vision-deficiency
validator rather than picked by eye". Until this file existed that was an unbacked boast, which is
exactly the kind of claim the rest of the repository refuses to make. This is the validator, and
`tests/test_style.py` runs it, so the claim is now a tested fact rather than a sentence.

Two checks, both over `style.PALETTES`:

**Contrast.** WCAG 2.1 relative luminance, ratio against the chart SURFACE. Floor 3:1, the
non-text bar, because these colours are marks and fills rather than body copy. This is the check
that condemned the previously shipped Bear amber at 1.92:1.

**Colour-vision deficiency.** Every pair within a palette is simulated as a protanope and as a
deuteranope (Vienot, Brettel and Mollon 1999, the standard LMS projection) and compared two ways.

*Distance*, CIE76 dE in L*a*b*, floor 8: are these two colours distinguishable at all.

*Hue*, the L*a*b* hue angle, floor 90 degrees, applied only to palettes that declare they encode
by hue: are they distinguishable WITHOUT relying on one being lighter than the other. This is the
check that does the real work. Green and red survive the distance floor comfortably at 17.2,
because a dichromat does see red as darker than green, but they sit 1.1 degrees apart in hue, so
that reader is reading lightness and nothing else. Encodings that lean on lightness alone fail
wherever lightness is unreliable: small marks, print, a projector, bars of differing height.
A palette encoding an ORDINAL variable is exempt from the hue floor, since a constant-hue
lightness ramp is exactly the right answer there.

Run it directly to see the numbers:

    uv run python tools/validate_palette.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from regime_shift.style import INKS, PALETTES, SURFACE  # noqa: E402

CONTRAST_FLOOR = 3.0
CVD_FLOOR = 8.0
HUE_FLOOR = 90.0

# Vienot, Brettel and Mollon (1999). Linear RGB -> LMS, then a projection onto the dichromat's
# reduced colour plane, then back. Applied to LINEARIZED rgb, not gamma-encoded, so the simulation
# happens in the space where light actually adds.
_RGB_TO_LMS = np.array(
    [
        [17.8824, 43.5161, 4.11935],
        [3.45565, 27.1554, 3.86714],
        [0.0299566, 0.184309, 1.46709],
    ]
)
_LMS_TO_RGB = np.linalg.inv(_RGB_TO_LMS)
_DICHROMAT = {
    "protan": np.array([[0.0, 2.02344, -2.52581], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
    "deutan": np.array([[1.0, 0.0, 0.0], [0.494207, 0.0, 1.24827], [0.0, 0.0, 1.0]]),
}

# D65, the white point sRGB is defined against.
_WHITE = np.array([0.95047, 1.0, 1.08883])
_RGB_TO_XYZ = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ]
)


def _srgb(hex_colour: str) -> np.ndarray:
    h = hex_colour.lstrip("#")
    return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=float) / 255.0


def _linearize(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _clamp(c: np.ndarray) -> np.ndarray:
    """A simulated colour can land outside the sRGB gamut; a monitor would clip it, so we do."""
    return np.clip(c, 0.0, 1.0)


def relative_luminance(hex_colour: str) -> float:
    """WCAG 2.1 relative luminance."""
    return float(_linearize(_srgb(hex_colour)) @ np.array([0.2126, 0.7152, 0.0722]))


def contrast_ratio(a: str, b: str) -> float:
    """WCAG 2.1 contrast ratio, always >= 1 whichever way round the arguments go."""
    lo, hi = sorted((relative_luminance(a), relative_luminance(b)))
    return (hi + 0.05) / (lo + 0.05)


def simulate(hex_colour: str, kind: str) -> np.ndarray:
    """Linear rgb as seen by a protanope or a deuteranope."""
    lms = _RGB_TO_LMS @ _linearize(_srgb(hex_colour))
    return _clamp(_LMS_TO_RGB @ (_DICHROMAT[kind] @ lms))


def _to_lab(lin_rgb: np.ndarray) -> np.ndarray:
    xyz = (_RGB_TO_XYZ @ lin_rgb) / _WHITE
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16.0 / 116.0)
    return np.array([116.0 * f[1] - 16.0, 500.0 * (f[0] - f[1]), 200.0 * (f[1] - f[2])])


def cvd_distance(a: str, b: str, kind: str) -> float:
    """CIE76 dE between two colours after simulating one kind of dichromacy."""
    return float(np.linalg.norm(_to_lab(simulate(a, kind)) - _to_lab(simulate(b, kind))))


def worst_cvd_distance(a: str, b: str) -> tuple[float, str]:
    """The harder of the two dichromacies for this pair, and which one it was."""
    scores = {kind: cvd_distance(a, b, kind) for kind in _DICHROMAT}
    kind = min(scores, key=scores.get)
    return scores[kind], kind


def hue_angle(hex_colour: str, kind: str) -> float:
    """L*a*b* hue angle in degrees, after simulating one kind of dichromacy."""
    _, a, b = _to_lab(simulate(hex_colour, kind))
    return float(np.degrees(np.arctan2(b, a)) % 360.0)


def worst_hue_separation(a: str, b: str) -> tuple[float, str]:
    """Smallest angle between two hues across both dichromacies. Near zero means one colour."""
    scores = {}
    for kind in _DICHROMAT:
        gap = abs((hue_angle(a, kind) - hue_angle(b, kind) + 180.0) % 360.0 - 180.0)
        scores[kind] = gap
    kind = min(scores, key=scores.get)
    return scores[kind], kind


def _groups() -> list[tuple[str, tuple[str, ...], str]]:
    # Inks get the contrast check only: they are one hue at several lightnesses, deliberately
    # confusable in hue and separable in weight, which is the opposite goal from a palette.
    return [(n, tuple(cs), ch) for n, (cs, ch) in PALETTES.items()] + [("ink", INKS, "ink")]


def failures() -> list[str]:
    """Every violation of any floor, as readable lines. Empty means the palettes are honest."""
    bad = []
    for name, colours, channel in _groups():
        for c in colours:
            ratio = contrast_ratio(c, SURFACE)
            if ratio < CONTRAST_FLOOR:
                bad.append(
                    f"{name}: {c} sits at {ratio:.2f}:1 against the surface, "
                    f"under the {CONTRAST_FLOOR:.0f}:1 floor"
                )
        if channel == "ink":
            continue
        for i, a in enumerate(colours):
            for b in colours[i + 1 :]:
                dist, kind = worst_cvd_distance(a, b)
                if dist < CVD_FLOOR:
                    bad.append(
                        f"{name}: {a} and {b} separate by only {dist:.1f} units "
                        f"as a {kind}ope, under the {CVD_FLOOR:.0f}-unit floor"
                    )
                if channel != "hue":
                    continue
                gap, kind = worst_hue_separation(a, b)
                if gap < HUE_FLOOR:
                    bad.append(
                        f"{name} encodes by hue, but {a} and {b} sit {gap:.1f} degrees apart "
                        f"as a {kind}ope, under the {HUE_FLOOR:.0f}-degree floor: that reader "
                        "would be separating them by lightness alone"
                    )
    return bad


def report() -> int:
    for name, colours, channel in _groups():
        print(f"\n{name}  (encodes by {channel})")
        for c in colours:
            print(f"  {c}  contrast vs surface {contrast_ratio(c, SURFACE):6.2f}:1")
        if channel == "ink":
            continue
        for i, a in enumerate(colours):
            for b in colours[i + 1 :]:
                dist, dkind = worst_cvd_distance(a, b)
                gap, hkind = worst_hue_separation(a, b)
                note = "" if channel == "hue" else "  (hue floor n/a)"
                print(
                    f"  {a} vs {b}  dE {dist:5.1f} ({dkind}ope)"
                    f"   hue {gap:6.1f} deg ({hkind}ope){note}"
                )

    bad = failures()
    print("\n" + ("PASS: every palette clears every floor" if not bad else "FAIL"))
    for line in bad:
        print(f"  {line}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(report())

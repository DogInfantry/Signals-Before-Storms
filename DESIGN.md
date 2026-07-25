---
name: Signals-Before-Storms
description: A ruled research log that inherits its palette from the module that draws its figures.
colors:
  surface: "#fcfcfb"
  ink: "#1c1c1c"
  ink-soft: "#5c5c5c"
  ink-faint: "#8a8a8a"
  rule: "#e4e4e1"
  link: "#1a6ca8"
  link-hover: "#15578a"
  good: "#2e7d32"
  bad: "#b3261e"
  regime-0: "#e8b84b"
  regime-1: "#d2691e"
  regime-2: "#8f1d14"
  ground-dark: "#16171a"
  ink-dark: "#ececea"
  ink-soft-dark: "#b3b2ae"
  ink-faint-dark: "#85847f"
  rule-dark: "#2e3036"
  link-dark: "#7ab8e5"
  link-hover-dark: "#a3d0f2"
  good-dark: "#6fbf73"
  bad-dark: "#ef8a80"
  regime-0-dark: "#f0cd72"
  regime-1-dark: "#e08343"
  regime-2-dark: "#cf5344"
typography:
  display:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(2.05rem, 1.25rem + 3.1vw, 3rem)"
    fontWeight: 680
    lineHeight: 1.15
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(1.5rem, 1.2rem + 1.1vw, 2.05rem)"
    fontWeight: 640
    lineHeight: 1.15
    letterSpacing: "-0.015em"
  title:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.02rem"
    fontWeight: 640
    lineHeight: 1.15
  lede:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.075rem"
    fontWeight: 400
    lineHeight: 1.62
  body:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(1rem, 0.96rem + 0.2vw, 1.0625rem)"
    fontWeight: 400
    lineHeight: 1.62
  secondary:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.15
    letterSpacing: "0.06em"
  control:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 550
    lineHeight: 1.15
  micro:
    fontFamily: "ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
    letterSpacing: "0.08em"
  diagram-sublabel:
    fontFamily: "ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace"
    fontSize: "11px"
    fontWeight: 400
    note: "SVG user units inside the 420-unit pipeline viewBox, not a page-level step. The diagram is capped at 26rem so this resolves near 12.9px on screen, below body."
rounded:
  hairline: "2px"
  control: "3px"
  dot: "50%"
spacing:
  tight: "0.55rem"
  caption: "0.7rem"
  para: "1.1rem"
  block: "1.75rem"
  section: "2rem"
  gutter: "clamp(1.25rem, 3vw, 2.25rem)"
  margin-col: "5.5rem"
  entry: "clamp(2.5rem, 6vw, 4rem)"
components:
  action-primary:
    backgroundColor: "{colors.link}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "0.62rem 1.05rem"
  action-primary-hover:
    backgroundColor: "#15578a"
    textColor: "{colors.surface}"
  action-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0.62rem 1.05rem"
  entry-number:
    textColor: "{colors.ink-faint}"
    typography: "{typography.label}"
  stamp-fail:
    textColor: "{colors.bad}"
    rounded: "{rounded.hairline}"
    padding: "0.12rem 0.4rem"
    typography: "{typography.micro}"
  stamp-held:
    textColor: "{colors.good}"
    rounded: "{rounded.hairline}"
    padding: "0.12rem 0.4rem"
    typography: "{typography.micro}"
  plate:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.hairline}"
  table-header:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-soft}"
    typography: "{typography.label}"
    padding: "0.5rem 0.55rem"
  regime-key-crisis:
    backgroundColor: "{colors.regime-2}"
    rounded: "{rounded.hairline}"
    size: "0.62rem"
---

# Design System: Signals-Before-Storms

## Overview

**Creative North Star: "The Ruled Research Log"**

This is a laboratory notebook that happens to be a web page. Numbered entries run down a ruled
margin in the order the work actually happened, an index of entries sits where a contents page
would, marginal notes interrupt the argument where a researcher would have written in the gutter,
and every finding arrives attached to a tabular figure. The page reports a failed strategy in the
order it failed, so the form is chronological rather than promotional. There is no card grid, no
hero gradient, no downloaded typeface, and no scoreboard.

The palette is not original to this page and must not be treated as such. It is inherited verbatim
from `src/regime_shift/style.py`, the Python module that draws every PNG the page embeds. That
module validated its colours with a contrast and colour-vision-deficiency script rather than
choosing them by eye, and that check caught a real defect in the previously shipped palette (an
amber at 1.92:1 against the chart surface, under the 3:1 floor, in a green/amber/red triad that
collapses under red-green colour blindness). The page therefore agrees with its contents instead of
fighting them, and the CSS declares the upstream hexes as the source values with derived aliases on
top.

Density is high and deliberately so. Body text is capped at 68ch, secondary text at 52 to 66ch, and
headings at 24ch, because the reader is a recruiter or a practising quant scanning on a phone with
under a minute of patience. Every visual device on the page is either a hairline rule, a numeral, or
a chart. The one authored motion moment (the margin rule drawing downward on scroll) is gated and
defaults to fully drawn, so nothing on the page depends on animation, JavaScript, or a network
request beyond the stylesheet and the committed PNGs.

**Key Characteristics:**
- Inherited palette, validated upstream in `style.py`, never re-picked at the page level
- Ordinal regime encoding by lightness, never by three arbitrary hues
- System font stack by decision: no build step, and the matplotlib figures set the typographic register
- Hairline rules and tonal shift only; no drop shadows anywhere
- Numbered entries against a ruled margin column, with an index of entries above them
- Every number set in tabular figures, mono at the masthead, entry numbers, index numbers and diagram sublabels
- Zero build step, zero JavaScript, zero external requests

## Colors

A validated research-instrument palette: near-white paper, three greys of ink, one blue for action,
one red and one green reserved for verdicts, and a three-step ordinal ramp used only where a regime
is named.

### Primary
- **Instrument Blue** (`{colors.link}`): the only action colour. It fills the primary button to the
  repository, carries every inline link, and draws the focus ring. It is inherited from the figures'
  `SERIES_A`, so a link on the page and a return series in a chart are the same blue.

### Secondary
- **Warning Vermilion** (`{colors.bad}`): verdict red. It rules the left edge of the cover verdict,
  outlines the `failed` stamp on each rescue, strikes through the retracted number, and marks the two
  leak-proofing guards in the pipeline diagram. It never fills an area.
- **Held Green** (`{colors.good}`): the counterpart, outlining the `held` stamp on each check that
  survived scrutiny. Used only in that pairing, so a reader learns the two stamps as a set.

### Tertiary
- **Regime Ramp** (`{colors.regime-0}` sand, `{colors.regime-1}` ember, `{colors.regime-2}` oxide):
  a sequential lightness ramp for Bull, Bear, Crisis. It appears only as the 0.62rem swatch beside a
  named regime in a table, so the page key and the chart shading read as one encoding.

### Neutral
- **Paper** (`{colors.surface}`): the page ground in light mode, and the fixed plate behind every
  figure in both modes.
- **Ink** (`{colors.ink}`): body copy, headings, emphasis.
- **Soft Ink** (`{colors.ink-soft}`): ledes, captions, marginal notes, table headers, benchmark rows,
  the masthead. Everything that is context rather than claim.
- **Faint Ink** (`{colors.ink-faint}`): entry numbers, index numbers, diagram connector lines, the
  hover border on ghost actions.
- **Hairline** (`{colors.rule}`): every rule, table border, plate edge and control border on the page.
- **Night Ground** (`{colors.ground-dark}`) with its ink, rule and link variants: the dark scheme,
  declared through `color-scheme: light dark` and a single `prefers-color-scheme` block.

### Named Rules

**The Upstream Palette Rule.** `src/regime_shift/style.py` is the source of truth for colour. A
change to the page palette happens there first and reaches the CSS second, because the page embeds
PNGs drawn with those exact values. Edit the CSS alone and the container drifts away from its
contents. A colour that has not been through that module's contrast and colour-vision check does not
belong on this page.

**The Ordinal Ramp Rule.** Regimes are ordinal (Bull to Bear to Crisis, ascending risk), so they are
encoded by lightness, not by hue. Three arbitrary hues would lose the ordering and collapse under
red-green colour blindness. Any new ordered scale on this page follows the same discipline.

**The Regime-Only Rule.** The ramp appears only where a regime is named. It is never borrowed as a
generic accent, a highlight, or decoration, because its meaning is the whole reason it survives a
colour-vision check.

**The Dark Swatch Exception.** In dark mode the three regime swatches lighten to
`{colors.regime-0-dark}`, `{colors.regime-1-dark}`, `{colors.regime-2-dark}`, because
`{colors.regime-2}` on `{colors.ground-dark}` is nearly invisible. Lightness ordering is preserved,
so the encoding stays ordinal. The figures themselves keep the true ramp, since they sit on a fixed
light plate.

**The Fixed Plate Rule.** Figures always render on `{colors.surface}` regardless of colour scheme.
The PNGs carry a baked-in light surface, so the container matches the image rather than the page.
In dark mode the plate keeps its light fill and swaps only its border to `{colors.rule-dark}`.

## Typography

**Display Font:** system UI stack (`system-ui`, `-apple-system`, Segoe UI, Roboto, Helvetica Neue, Arial)
**Body Font:** the same system UI stack
**Label/Mono Font:** system mono stack (`ui-monospace`, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono)

**Character:** Plain, local, and unbranded. The typographic register is set by the embedded
matplotlib figures, which draw in the platform's own faces, so a downloaded typeface would make the
page and its charts disagree. With no build step there is also nothing to subset a webfont with, and
no request budget worth spending on one. The mono face does the notebook work: masthead metadata,
entry numbers, index numbers, stamps, and diagram sublabels.

### Hierarchy
- **Display** (680, `clamp(2.05rem, 1.25rem + 3.1vw, 3rem)`, 1.15, -0.03em): the cover headline only,
  one per page, with a 0.42em standfirst at weight 500 in soft ink underneath it.
- **Headline** (640, `clamp(1.5rem, 1.2rem + 1.1vw, 2.05rem)`, 1.15, max 24ch): the title of each
  numbered entry. The 24ch cap keeps every entry title to two or three lines.
- **Title** (640, `1.02rem`): sub-headings inside an entry, often prefixed by a stamp.
- **Lede** (400, `1.075rem`, soft ink, max 60ch): the one-paragraph statement of what an entry
  contains, directly under its headline. Every entry has exactly one.
- **Body** (400, `clamp(1rem, 0.96rem + 0.2vw, 1.0625rem)`, 1.62, max 68ch): argument text. `strong`
  runs at 650 in full ink and carries the claim a scanning reader should catch.
- **Secondary** (400, `0.875rem`, 1.55, soft ink, max 52 to 66ch): marginal notes, figure captions,
  table captions, colophon.
- **Label** (mono, `0.8125rem`, 0.06em): entry numbers, and at 600 weight in the sans face, table
  column headers and masthead identity.
- **Micro** (mono, `0.75rem`, 0.08em): index numbers and the outlined `failed` / `held` stamps.

### Named Rules

**The System Stack Rule.** No downloaded typeface, ever. The figures are drawn in platform faces and
there is no build step to subset anything, so a webfont would cost a request to create a mismatch.

**The Tabular Numeral Rule.** Every number on the page is set with `font-variant-numeric: tabular-nums`:
table cells, inline code, and the `.num` span. Scorecard columns are read down, and proportional
figures make a column of Sharpe ratios ragged and slower to scan.

**The One Lede Rule.** Each entry opens with exactly one soft-ink lede at `1.075rem` before any body
copy. A reader skimming only the eight ledes gets the whole argument in order.

## Layout

A single centred column of maximum 78rem, padded by `clamp(1.15rem, 4vw, 3rem)` horizontally, holding
a stack of full-bleed horizontal bands separated by 1px rules: masthead, cover, index, eight entries,
close. There is no card, no box, and no nested container; the rule between bands is the only divider.

At 62rem and above each entry gains `5.5rem` of left padding and a ruled margin column drawn 2.25rem
inside it, with the entry number absolutely positioned at the left edge and a 7px hollow dot sitting
on the rule beside it. Below 62rem the margin column collapses entirely: the entry number becomes a
block label above the headline and the rule disappears rather than compressing.

Four breakpoints, all in rem so they respond to user text size: 42rem takes the index of entries from
one column to two, 48rem gives the rescue ledger a two-column definition list and the colophon a
two-column grid, 62rem introduces the margin column and the two-column cover, 68rem takes the index
to four columns.

The vertical rhythm is coarse at the band level and fine inside it. Entries pad by
`clamp(2.5rem, 6vw, 4rem)`, figures and tables sit on `1.75rem` blocks, sub-headings open on `2rem`,
paragraphs close on `1.1em`, and captions sit `0.7rem` under their figure. Measure is enforced per
role rather than globally: 68ch for body, 60ch for ledes, 66ch for captions, 52ch for marginal notes
and the cover verdict, 46ch for colophon copy, 24ch for entry headlines.

### Named Rules

**The Margin Rule.** Above 62rem every entry carries a 1px ruled edge in `{colors.rule}` with its
number outside the rule. This is the page's signature and its only structural ornament. It is also
the page's only authored motion: the rule scales from `scaleY(0)` to `scaleY(1)` across
`animation-range: entry 5%` to `entry 55%` using `animation-timeline: view()`, gated behind both
`@supports` and `prefers-reduced-motion: no-preference`, and defaults to fully drawn so nothing
depends on it.

**The Measure Rule.** No text block runs wider than its role's cap. Secondary text is always narrower
than body text, which is always narrower than the container. The hierarchy is legible from line
length alone.

## Elevation & Depth

There are no drop shadows on this page. Depth is conveyed entirely by 1px hairline rules in
`{colors.rule}` and by tonal shift between the three ink greys. Figures get a hairline border and a
fixed light plate rather than a lift; buttons get a border rather than a raise; the sticky table
header covers scrolled rows with an opaque ground fill rather than a shadow edge.

The single `box-shadow` in the stylesheet is not an elevation token: it is `inset 0 0 0 1px` on the
7px entry marker, drawing a hollow ring on the margin rule. Reading it as elevation and generalising
from it would introduce the exact depth vocabulary this system refuses.

### Named Rules

**The Hairline-Only Rule.** Separation is a 1px rule or a tonal step, never a shadow. If a surface
needs to be distinguished, rule it or shift its ink; do not lift it.

## Shapes

The form language is rectangular and barely rounded. Three radii exist: 2px on plates, code blocks,
stamps, regime swatches and focus rings; 3px on the two action buttons; and a full circle on the 7px
entry marker. Nothing else is rounded, and there is no pill, no capsule, and no large-radius card.

Borders are always 1px and almost always `{colors.rule}`. The exceptions are semantic rather than
decorative: the cover verdict's left border in `{colors.bad}`, the stamps' `currentColor` outline,
and the pipeline diagram's guard boxes stroked in `{colors.bad}`. Colour on a border means the border
is making a claim.

The pipeline diagram is authored inline SVG on a 420 by 706 viewBox, capped at `max-width: 26rem`.
Left at full width its 13px labels scale up to headline size and a subordinate schematic becomes the
largest thing on the page.

## Components

### Buttons
- **Shape:** softly squared (3px radius), 1px border, inline-flex with a 0.45rem gap
- **Primary:** instrument blue fill with paper text, `0.62rem 1.05rem` padding, weight 550, `0.9375rem`.
  Used twice on the page, both times pointing at the repository.
- **Ghost:** transparent with an ink label and a hairline border, same padding and metrics. Used for
  the in-page skip link on the cover.
- **Hover / Focus:** 140ms ease on border, colour and background. Primary darkens to `#15578a`
  (lightens to `#a3d0f2` in dark mode, where its label flips to the night ground). Ghost shifts its
  border to faint ink. Focus is a global 2px `{colors.link}` outline at 3px offset with a 2px radius.

### Cards / Containers
There are none. Bands separated by hairline rules do the work a card grid would do elsewhere, and
introducing a card would break the log form.

### Tables (signature component)
- **Style:** full width, collapsed borders, `0.9rem`, minimum 34rem inside a horizontally scrollable
  region. All cells right-aligned and `white-space: nowrap` with tabular figures; the first column
  left-aligned, wrapping, at a 13rem minimum.
- **Header:** soft ink at `0.8125rem` weight 600, sticky to the top of the scroll region with an
  opaque ground fill.
- **Benchmark rows:** soft ink throughout with an italic first cell. Benchmarks are distinguished,
  not scored.
- **Caption:** a `.table-caption` paragraph sitting outside the scroll container, linked by
  `aria-describedby`. A real `<caption>` inherits the table's 34rem minimum width and gets clipped
  off screen on a phone.
- **Scroll region:** carries `tabindex="0"`, `role="region"` and an `aria-label` so a keyboard user
  can reach and scroll it.

### Figure Plates (signature component)
- **Style:** full-width image on a fixed `{colors.surface}` plate with a 1px hairline
  border (`{colors.rule}`, swapping to `{colors.rule-dark}` in dark mode) and 2px radius, wrapped in a link to the full-size PNG because a dense four-panel composite
  renders at roughly 170px per panel on a phone.
- **Caption:** `0.875rem` soft ink at 66ch, opening with a bold ink lead-in that states the finding.
- **Alt text:** describes what the chart shows, not what it is named. The charts carry the argument,
  so a screen reader user gets the finding.

### Entry Header (signature component)
- **Style:** a mono number in faint ink at `0.8125rem` / 0.06em, absolutely positioned outside the
  margin column above 62rem with a 7px hollow ring sitting on the rule, and inline above the headline
  below 62rem. Marked `aria-hidden` because the index and the headline already carry the structure.

### Stamps (signature component)
- **Style:** mono `0.75rem` / 0.08em in a `currentColor` outline with 2px radius and
  `0.12rem 0.4rem` padding. Two variants only: `failed` in `{colors.bad}`, `held` in `{colors.good}`.
- **Placement:** inline at the head of the sentence it qualifies, so the verdict is read before the
  explanation.

### Navigation
- **Style:** an ordered index of entries in a 1, 2 or 4 column grid at `0.9rem`, each item a mono
  number in faint ink beside an ink link underlined by a hairline `border-bottom`.
- **Hover:** the underline shifts from `{colors.rule}` to `{colors.ink-faint}`. No colour change, no
  movement.
- **Mobile:** single column, still above the first entry. It is the contents page of the log and the
  honest answer to a reader with forty seconds.

## Do's and Don'ts

### Do:
- **Do** change `src/regime_shift/style.py` first when the palette must change, then mirror it into
  the CSS `:root` block. The page embeds figures drawn from that module.
- **Do** encode ordered data by lightness, following the regime ramp's precedent.
- **Do** set every number in tabular figures, in mono or with `font-variant-numeric: tabular-nums`.
- **Do** separate content with 1px hairline rules in `{colors.rule}` and tonal ink steps.
- **Do** keep the regime ramp exclusive to places where a regime is named.
- **Do** put table captions outside the scroll container and link them with `aria-describedby`.
- **Do** give scrollable regions `tabindex="0"`, `role="region"` and an `aria-label`.
- **Do** cap authored SVG at its intended scale (the pipeline diagram at `max-width: 26rem`) so
  schematic labels stay subordinate to body text.
- **Do** open every entry with exactly one soft-ink lede.
- **Do** gate any motion behind `prefers-reduced-motion` and a `@supports` test, and default to the
  finished state.

### Don't:
- **Don't** introduce a colour that has not been through the upstream contrast and colour-vision
  check, and don't re-pick a page colour that already exists in `style.py`.
- **Don't** substitute three arbitrary hues for the lightness ramp on ordered data.
- **Don't** add a drop shadow. The one `box-shadow` present is an inset hairline ring on the entry
  marker, not an elevation step.
- **Don't** add a downloaded typeface. There is no build step, and the figures set the register.
- **Don't** colour-rank cells in the scorecards. Several rows tie on max drawdown and Calmar, and a
  best-in-column marker would be wrong by inspection before it was ever misleading.
- **Don't** wrap content in cards or a card grid. Ruled bands are the container vocabulary.
- **Don't** exceed the per-role measure caps (68ch body, 60ch lede, 66ch caption, 52ch note, 24ch
  entry headline).
- **Don't** add JavaScript, an external font or an external asset request. The page ships as HTML,
  one stylesheet, one SVG favicon and committed PNGs.
- **Don't** use em dashes or en dashes anywhere on the page or in its comments. Hyphens, commas and
  parentheses only.

# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary: a recruiter or a hiring quant**, scanning to decide whether this person can do rigorous
research. They arrive from a link (a resume, a GitHub profile, a message), give it well under a
minute before deciding to keep reading or leave, and are often on a phone. They are not here to
learn regime switching. They are here to find out whether the work is honest and whether the method
holds up.

**Secondary: quant practitioners and peers**, who will judge the leak-proofing, the deflated Sharpe,
the paired difference test and the episode counting on the merits. Anything that survives their
reading also convinces the first audience; anything that would not survive it must not be claimed.

## Product Purpose

Signals-Before-Storms detects hidden market regimes (Bull, Bear, Crisis) with a Hidden Markov Model,
then reallocates across equity, cash and gold using a per-regime convex program, validated by a
leak-proof expanding walk-forward with transaction costs charged to every book alike.

**The strategy does not work, and the project exists to say so precisely.** It does not beat a
static 60/40 or equal weight on risk-adjusted return. It does cut maximum drawdown by roughly two
thirds on Indian data. Success for this product is a reader who leaves understanding *why* it fails,
believing the failure was measured rather than assumed, and trusting the person who measured it.

## Positioning

Most public backtest repositories report a Sharpe ratio and stop. Three things here cannot be
truthfully copied by a repository that did not do the work:

1. **A diagnosis, not just a negative.** The HMM finds volatility states, and volatility is
   symmetric in sign, so it cannot tell a crash from a rebound. Next-day return orders backwards
   against the volatility label on both universes. That is a reusable finding that outlives this
   codebase.
2. **A documented retraction.** An apparent discovery (a Jump Model crisis label reading -17.1%
   annualized over 94 days) was written up and then withdrawn the same day by an episode count: it
   was two episodes, one of them positive, and all 94 days sat inside the HMM's own crisis label.
   The retraction is published rather than quietly dropped.
3. **Leak-proofing asserted by unit tests rather than claimed in prose.** Five defences, each pinned
   by a test that fails if the defence is removed.

## Operating Context

The page is read cold, from a link, with no prior context about the project, frequently on a phone
and frequently in under a minute. The reader's next action is either closing the tab or opening the
GitHub repository. Nothing on the page can assume the reader has read the README, and nothing can
require them to run code.

The underlying work is a Python research package (`src/regime_shift/`), a driver script, a rendered
notebook and 80 tests. The reader will never execute any of it before deciding.

## Capabilities and Constraints

- **A static one-page site**, at `docs/index.html`, served by Vercel with framework preset `Other`
  and Root Directory `docs`. No build step, no install step, no Node dependency, no lockfile.
- **No live compute, ever.** The backtest cannot run in a Vercel Function: dependency size against
  the 500 MB uncompressed cap, a walk-forward that runs for minutes against `maxDuration`, and
  yfinance being rate-limited from datacenter IPs. Everything worth showing is already rendered to
  PNG.
- **No JavaScript libraries.** With no build step, shipping a library for one diagram is a bad
  trade; diagrams are authored inline SVG.
- Figures are **precomputed PNGs** already committed at `docs/img/`, and the site reuses them in
  place so `README.md`'s existing paths stay valid.
- Total figure payload is roughly 700 KB with no build step available to optimize it.
- Terminology the page must use correctly: regime, walk-forward, lookahead bias, causal decode,
  deflated Sharpe, paired bootstrap, episode versus day, ablation.

## Brand Commitments

- **Attribution: "Anklesh Rawat (DogInfantry)"**, matching the LICENSE and NOTICE. Real name plus
  handle, both visible.
- **Apache-2.0**, and attribution is a license condition rather than a courtesy (Section 4). The
  citation block from the README carries onto the page verbatim.
- **The course is not named.** This stands as independent research; the work is identical either
  way.
- **No em dashes or en dashes anywhere**, in copy or in comments. Standing user rule.
- **`src/regime_shift/style.py` is the incumbent visual authority.** Its palette was validated by a
  contrast and colour-vision-deficiency script rather than picked by eye, and the page embeds figures
  drawn with it, so the page inherits it. Regimes use a lightness ramp because they are ordinal.
- Repository: `https://github.com/DogInfantry/Signals-Before-Storms`.

## Evidence on Hand

Real, already produced, and safe to show:

- Seven committed figures at `docs/img/`: `india_story` (the four-panel composite),
  `india_label_profile`, `india_regime_weights`, `india_equity_drawdown`, `india_episode_bars`,
  `india_sensitivity`, `india_regime_overlay`.
- Full scorecards for both universes, gross and net, in `README.md`: India out-of-sample
  2016-07-22 to 2023-12-29 (n = 1,814) and US 2016-07-05 to 2023-12-29 (n = 1,886).
- The label profile table, the episode table with its ex-largest column, the paired difference
  intervals, and the deflated Sharpe at a stated 7 trials.
- 80 passing tests (4 skipped), ruff clean, CI green, `LICENSE` and `NOTICE`.

**Absences that must never be filled in by invention:**

- No live trading record, no paper-trading record, no capital deployed.
- No macro results. `fred.stlouisfed.org` is unreachable from the network this was run on, so every
  published number is macro-free and both entry points print `landed=NONE` to say so.
- No user testimonials, no citations by others, no benchmarks against commercial products.
- No third universe. India is primary and graded, the US is the robustness check, and that is all.

## Product Principles

1. **The negative result is the product.** It is stated plainly and early, never softened into a
   qualified positive, and never buried under the drawdown win.
2. **Every claim has its number attached.** No adjective does work that a figure could do.
3. **Report what was measured, including what contradicts the story.** The US does not reproduce
   India, the drawdown variant that tops the India table failed its pre-registered criterion and is
   not adopted, and the retraction stays published.
4. **The reader is not assumed to trust anything.** Rigor is shown as mechanism (a test that fails,
   a paired interval, an episode count), not asserted as a quality.
5. **Nothing on the page is recomputed or invented.** Every number comes from the README and the
   committed run.

## Accessibility & Inclusion

- The embedded charts are dense and carry the finding, so each needs substantive `alt` text and a
  real caption. A screen reader user should get the finding, not the filename.
- The inherited palette already meets a 3:1 contrast floor and survives colour-vision deficiency,
  because regimes are encoded by lightness rather than hue. The page must not introduce a colour
  that has not been through that check.
- Keyboard navigation must reach the primary action, with visible focus.

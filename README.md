# Signals-Before-Storms: Macro-Aware Tactical Asset Allocation Engine

Detect hidden market regimes (Bull, Bear, Crisis) with a Hidden Markov Model, then switch
portfolio weights across equities, bonds, and gold using convex optimization. Everything is
validated with a strictly leak-proof expanding walk-forward and charged realistic transaction
costs, then compared against static 60/40 and equal-weight benchmarks.

**Headline result: the states are volatility states, and volatility carries no directional
information.** That is confirmed on two universes and by two unrelated estimators, and it is the
robust finding. What follows from it is split, and the split is the interesting part: on the
primary Indian universe the overlay still buys real drawdown protection, holding a -6.2% worst
drawdown against -15.2% for equal weight and -23.7% for a genuine 60/40, with Calmar roughly 1.9x
and 2.8x those benchmarks, while finishing mid-pack on Sharpe. On the US it loses on every metric.
Two of the three metrics the brief names favour it on India; one does not. It is worked through in
[Results](#results) below.

## Results

Every book, strategy and benchmark alike, runs through the same cost engine at 7.5 bps per unit of
turnover with a one-day execution lag. Results are reported **both gross and net**, since a
benchmark costed on different terms is not a benchmark, and a strategy shown only net hides whether
its shortfall comes from stance or from trading.

### India (primary universe)

^NSEI / LIQUIDBEES.NS / GOLDBEES.NS / ^INDIAVIX, out-of-sample 2016-07-22 to 2023-12-29, n = 1814.
No liquid Indian duration ETF exists on Yahoo for this window (see
[data quality](#why-the-key-decisions)), so the defensive sleeve is an overnight cash fund,
labelled cash rather than pretending to be a bond. **The 60/40 benchmark routes its 40% to that
cash sleeve**, because dropping the leg entirely renormalizes it to 100% NIFTY and would judge a
defensive strategy against a pure-equity book carrying four times its volatility.

**Sharpe here is measured against the 3.79% rate that cash sleeve actually paid.** With a
near-riskless asset in the opportunity set, scoring against rf = 0 hands every defensive book a
large free Sharpe simply for holding cash: it inflated these numbers to 1.2-1.7 and reversed the
ranking.

| strategy | ann return | ann vol | Sharpe (net) | Sharpe (gross) | Sortino | max DD | Calmar | turnover/yr | DSR | Sharpe 95% CI |
|---|---|---|---|---|---|---|---|---|---|---|
| HMM + drawdown feature | 7.5% | 4.0% | 0.877 | 0.896 | 1.291 | -6.4% | 1.169 | 0.99x | 0.805 | (0.10, 1.61) |
| **vol-threshold rule (ablation)** | 7.5% | 4.2% | 0.848 | 0.863 | 1.244 | -6.5% | 1.165 | 0.88x | 0.783 | (0.08, 1.59) |
| Jump Model regimes | 7.6% | 4.3% | 0.829 | 0.833 | 1.204 | -7.3% | 1.038 | **0.24x** | 0.767 | (0.03, 1.59) |
| **HMM, regime-conditional moments** | 7.2% | 3.9% | 0.824 | 0.841 | 1.211 | **-6.2%** | **1.161** | 0.87x | 0.764 | (0.05, 1.56) |
| HMM + volatility targeting | 7.2% | 3.9% | 0.824 | 0.841 | 1.211 | -6.2% | 1.161 | 0.87x | 0.764 | (0.05, 1.56) |
| equal weight | 9.5% | 6.8% | 0.815 | 0.819 | 1.167 | -15.2% | 0.625 | 0.41x | 0.752 | (0.07, 1.56) |
| HMM, unconditional moments | 6.9% | 3.9% | 0.748 | 0.758 | 1.097 | -6.2% | 1.103 | 0.50x | 0.697 | (0.01, 1.47) |
| static 60/40 (equity/cash) | 9.8% | 10.0% | 0.604 | 0.607 | 0.827 | -23.7% | 0.413 | 0.36x | 0.552 | (-0.16, 1.44) |

Read the Sharpe column alone and the strategy is unremarkable: mid-pack, inside a cluster spanning
0.75 to 0.88 that no confidence interval can separate. Read the two columns the brief names
alongside it, **max drawdown and Calmar**, and the picture inverts. That is not noise; it is the
mechanical consequence of routing to minimum variance whenever the label is not calm. The overlay
buys drawdown protection and pays for it in return, and whether that trade is worth making is a
mandate question rather than a statistical one.

The drawdown-feature variant tops the table and is **not** counted as a win. Its criterion was
pre-registered before any Sharpe was computed (see
[the failed rescues](#why-the-hmm-does-not-earn-its-sharpe)) and it failed on that criterion.

### US (robustness universe)

SPY / TLT / GLD / VIX, walk-forward out-of-sample 2016-07-05 to 2023-12-29, n = 1886 trading days.
No cash sleeve exists here, so Sharpe is against rf = 0 and the 60/40 gets a real bond leg (TLT).

| strategy | ann return | ann vol | Sharpe (net) | Sharpe (gross) | Sortino | max DD | Calmar | turnover/yr | DSR | Sharpe 95% CI |
|---|---|---|---|---|---|---|---|---|---|---|
| **vol-threshold rule (ablation)** | **9.8%** | 10.3% | **0.958** | 0.984 | 1.369 | **-21.9%** | **0.446** | 3.61x | **0.863** | **(0.24, 1.65)** |
| static 60/40 | 7.5% | 11.5% | 0.690 | 0.693 | 0.956 | -27.6% | 0.273 | 0.41x | 0.643 | (-0.02, 1.42) |
| Jump Model regimes | 6.6% | 10.1% | 0.682 | 0.693 | 0.962 | -25.1% | 0.262 | **1.46x** | 0.636 | (-0.09, 1.40) |
| equal weight | 5.9% | 9.6% | 0.650 | 0.653 | 0.921 | -23.0% | 0.258 | 0.42x | 0.602 | (-0.09, 1.38) |
| HMM + drawdown feature | 5.4% | 9.6% | 0.590 | 0.620 | 0.840 | -28.0% | 0.191 | 3.88x | 0.538 | (-0.13, 1.34) |
| HMM + volatility targeting | 5.0% | 9.4% | 0.562 | 0.595 | 0.793 | -27.3% | 0.182 | 4.10x | 0.508 | (-0.18, 1.27) |
| HMM, regime-conditional moments | 4.9% | 9.6% | 0.542 | 0.575 | 0.765 | -28.7% | 0.170 | 4.19x | 0.486 | (-0.21, 1.26) |
| HMM, unconditional moments | 4.8% | 9.6% | 0.535 | 0.556 | 0.758 | -27.4% | 0.174 | 2.74x | 0.478 | (-0.17, 1.25) |

Deflated Sharpe is quoted at **7 trials**, the honest count of variants actually searched. It was
0.928 for the rule at 4 trials; searching three more ideas lowered every number in that column,
which is exactly what deflation is for.

**The US does not reproduce India, and saying so is the point of running it.** Here the strategy
loses outright on every metric including the two that vindicated it on India, and only the
volatility rule has an interval excluding zero. Minimum variance had nowhere to hide in 2022, when
bonds fell alongside equities. A result that held on one market and was quietly assumed to hold on
the other would be the more comfortable story; it is not the one the data tells.

### Why the HMM does not earn its Sharpe

The states are volatility states, and volatility carries no directional information. Measured at
the lag the strategy actually trades (label at close of t, return on t+1):

| label | India days | India ann ret | India vol | US days | US ann ret | US vol |
|---|---|---|---|---|---|---|
| 0 Bull | 821 | +10.2% | 11.2% | 665 | +10.9% | 8.7% |
| 1 Bear | 731 | +15.0% | 14.9% | 841 | +14.7% | 15.6% |
| 2 Crisis | 261 | +18.4% | 31.7% | 379 | +16.1% | 32.2% |

Volatility is ordered perfectly on both universes. Return is ordered backwards on both. De-risking
on the Crisis label sells the highest-returning days, because the violent rebounds of April 2020
and late 2022 are as volatile as the crashes that preceded them. Supporting checks:

- The stance map routes the modal Bear label to minimum variance even though it is a perfectly
  healthy regime. On India that label carries the **highest Sharpe of any label (1.01) across 731
  days**, so the largest single drag is a design choice, not a model failure.
- Outside COVID the picture is starker still: the India crisis label runs **+58.3% annualized**
  ex-COVID. The state the strategy de-risks on is, one event aside, the best-returning state in
  the data.
- Re-ranking states by trailing return instead of volatility lifts US Sharpe only 0.542 -> 0.620
  and leaves the Crisis label byte-identical. Reordering cannot add information the state space
  does not contain.
- The portfolio-weight figure shows equity never exceeding a quarter of the book and mostly
  sitting between 10% and 20%. The strategy is not taking too much risk; it is taking far too
  little, which is also why volatility targeting at 10% barely binds.

**BIC supports K=3 on India but not on the US.** Marginal fit bought per added state: India 2->3
6256, 3->4 **392**, 4->5 3125, a genuine elbow at three. US 2->3 5467, 3->4 3005, 4->5 1891, a
steady decline with no elbow, which is the signature of a model carving up a fat-tailed continuum
rather than finding discrete states. Three states is defensible on the graded universe and is not a
general fact.

**A second estimator reaches the same place.** A Statistical Jump Model penalizes switching
directly; it agrees with the HMM only 57.5% of the time on India (58.6% on the US). It does what it
advertises on turnover: US mean dwell rises from 27 days to 194 and turnover drops from 4.19x to
1.46x.

| Jump label | India days | India episodes | India ann ret | India vol | US days | US ann ret | US vol |
|---|---|---|---|---|---|---|---|
| 0 | 1272 | 3 | +16.9% | 13.7% | 1164 | +13.5% | 12.8% |
| 1 | 447 | 4 | +10.7% | 13.8% | 615 | +12.8% | 19.3% |
| 2 | 94 | **2** | -17.1% | 46.6% | 106 | **+20.0%** | 46.6% |

The `episodes` column is the one that matters, and it is the column almost every backtest omits.

On the US its crisis label is the *best*-returning state, reproducing the HMM's broken ordering
from a completely different estimator and pointing squarely at the state space rather than at the
HMM.

The India column looks at first like a genuine discovery: the only negative-return state anywhere
in this project. **It is not, and the reason is the most important methodological point in this
repo.** Those 94 days are not 94 independent observations. They are two episodes:

```
2020-03-06 -> 2020-06-12   64 days   -10.70%   <- COVID
2018-10-11 -> 2018-11-26   30 days    +4.41%   <- positive
```

Drop COVID and the same label runs **+30.17% annualized** over the remaining 40 days, the identical
backwards ordering as everything else. The effective sample behind "the Jump Model finds a
directional state" is one event. Worse, the label cross-tabulation shows all 94 of those days sit
*inside* the HMM's own crisis label, so the Jump Model was never finding a different state at all,
just a tighter threshold that happened to isolate March 2020.

There is no directional state, on either universe, under either estimator, once a single event is
controlled for.

**Two fixes were pre-registered and both failed.**

*Volatility targeting.* If the states predict variance, stop betting on direction and target
constant risk instead. Sharpe moved 0.542 to 0.562 on US and was bit-identical on India. The
reason is instructive: minimum variance already holds the book at 9.6% (US) and 3.9% (India)
volatility, so a 10% target almost never binds. The strategy's problem is that it is *already*
too de-risked, and giving up return is what costs it.

*A directional feature.* Drawdown-from-peak was added to the state space, since realized
volatility is symmetric in sign and cannot tell a crash from an equally violent rebound. The
success criterion was stated before looking at any Sharpe: **the crisis label's next-day equity
return has to turn negative.** It went the wrong way on both universes, +16.1% to +17.6% on the US
and +18.4% to +29.7% on India. It did not turn negative, so the feature failed on its own terms.
That it then tops the India Sharpe table is exactly the situation the pre-registration exists to
handle: it is not counted as a win, and the config default does not adopt it.

### Figures

Ten per universe, written to `results/` by the driver and embedded in the notebook (`results/` is
gitignored; the notebook outputs are how a reader sees them without running anything):

- `*_returns.png` - raw daily returns per asset with log-count marginals. Volatility clustering
  and fat tails, visible before any model is fitted.
- `*_feature_sanity.png` - `vol_21` and VIX with COVID and the 2022 bear shaded. On India `vol_21`
  goes from a ~0.10 baseline to 0.88 and India VIX from ~15 to 83, which is the check every
  downstream claim rests on.
- `*_label_profile.png` - next-day return and volatility per label. The central finding in one
  frame: volatility ordered, return ordered backwards.
- `*_weight_stack.png` - portfolio weights over time under the regime ribbon. Shows the stance map
  working, and shows equity pinned under 25% throughout.
- `*_gross_vs_net.png` - the two equity curves with the compounding cost wedge between them.
- `*_sharpe_forest.png` - every book's Sharpe with its bootstrap interval. The intervals are ~1.5
  wide, so the ranking is mostly noise.
- `*_bic_curve.png` - BIC by state count; an elbow at K=3 on India, none on the US.
- `*_regime_overlay.png` - out-of-sample regime path behind the equity curve. It independently
  flags Feb 2018, Q4 2018, COVID and 2022.
- `*_equity_drawdown.png` - every book in the scorecard, log growth over drawdown.
- `*_transition_heatmap.png` - transition matrix. The diagonal runs 0.96 to 0.98, and Bull never
  jumps straight to Crisis in either direction: the market always passes through the middle state.

## Why the key decisions

- **3 regimes (Bull / Bear / Crisis):** chosen to match the economic states we allocate against,
  and then checked with a BIC sweep rather than assumed. The sweep supports it on the graded Indian
  universe (a clear elbow at three) and does not support it on the US (above). Both are reported.
- **These features:** multi-window momentum (direction), realized volatility (stress), VIX level
  and its daily change, plus a small set of FRED macro series (yield-curve slope, credit spread,
  financial conditions) requested at both entry points.
  **Every number published here was produced without macro columns**, because
  `fred.stlouisfed.org` is unreachable from the network this was run on. The loader requests the
  series, warns, and continues; the driver and the notebook both print `landed=NONE` so the
  situation is visible rather than implied. On a network where FRED resolves the same command
  picks the series up, and the results would have to be regenerated.
- **Only equity drives the regime.** The state is a property of the market being timed, not of the
  sleeves used to express the view, so `_RETURN_COLS` excludes every asset return from the feature
  matrix. This was a live bug: `cash_ret` was missing from that list, so India silently fitted a
  10th feature the US never saw, which both broke the like-for-like comparison and depressed every
  Indian HMM score (fixing it moved regime-conditional Sharpe 0.744 -> 0.824). A test now asserts
  no `*_ret` column can reach the feature matrix.
- **India primary, US robustness:** the graded universe is Indian (NIFTY, gold, India VIX); the
  same pipeline re-runs on US assets as an out-of-sample check.
- **No Indian bond sleeve, because no usable one exists here.** Every candidate duration ETF on
  Yahoo was measured before being rejected: SETF10GILT.NS shows 39.0% annualised volatility with
  21.7% zero-return days, LTGILTBEES.NS 15.7% with 9.1%, and both start mid-sample (2016-06 and
  2018-05), which would truncate the out-of-sample window. A 10-year G-Sec ETF does not have 39%
  volatility; that is thin-trading noise around NAV, and `drop_return_outliers` at 0.5 would not
  catch it because no single print is absurd. LIQUIDBEES.NS (1.1% vol, 53.6% zero-return days,
  full history) is used instead and is called cash, not a bond.
- **Vendor data is guarded, not trusted:** GOLDBEES.NS on Yahoo prints a 100x round trip over
  2019-12-19 to 2019-12-23 (log returns of -4.61 then +4.61). Left alone it inflates gold's return
  standard deviation from 0.011 to 0.139 and, through the covariance, every Indian result: the
  strategy appeared to run at 44.5% volatility with a Sharpe of 0.45. Two bad prints out of 2193.
  `drop_return_outliers` now rejects any daily |log return| above 0.5 with a loud warning, and a
  test pins the case. The guard leaves a -13% crash day untouched.
- **Leak-proof by construction:** features are causal, standardization uses train-only statistics,
  the regime model is re-fit inside every fold, test regimes are decoded with a causal forward
  filter (never whole-sequence Viterbi), and weights are applied with a one-day execution lag.
  Each of those is asserted by a unit test, not just claimed.
- **Benchmarks share the cost engine:** every book, strategy and benchmark alike, runs through the
  same `run_book` loop. A benchmark costed on different terms is not a benchmark.
- **Results are deflated:** a Sharpe reported once, from one strategy out of several tried, is a
  biased number. Probabilistic and deflated Sharpe plus a stationary-bootstrap CI (with the block
  length chosen from the data, Politis-White) are reported alongside every headline figure.

## Layout

```
src/regime_shift/   core package (data, features, regime, walkforward, optimize,
                    backtest, metrics, benchmarks, plots)
config/config.yaml  all knobs: universe, dates, windows, costs, seed
notebooks/          top-to-bottom driver
results/            generated figures (gitignored)
tests/              leak-proofing and metric checks
```

## Quickstart

```bash
uv sync --extra jump
uv run pytest -q
uv run python notebooks/real_run.py india
uv run python notebooks/real_run.py us
```

The `jump` extra pulls `jumpmodels` for the second regime engine. Without it the pipeline still
runs end to end and simply skips the Jump Model book.

The first run downloads prices from Yahoo and caches them under `data/`; every later run is
offline. India is the default because it is the graded universe.

`notebooks/driver.ipynb` runs the same pipeline India-first with the full narrative and the US as a
robustness section, and is committed with its outputs and all ten figures embedded. Re-execute it
in place with:

```bash
uv run papermill notebooks/driver.ipynb notebooks/driver.ipynb --kernel python3
```

## Reproducibility

Seeds are fixed in `config/config.yaml`. Downloaded data is cached under `data/` so reruns are
offline and deterministic. The config default deliberately keeps the volatility-ranked variant
even though the return-ranked one scored higher, because silently promoting the better-scoring
variant is the selection bias the deflated Sharpe exists to catch. For the same reason the
drawdown feature stays off by default despite topping the India table: it failed its
pre-registered test.

The deflated Sharpe is quoted at 7 trials throughout. The cash-leg 60/40 and the `cash_ret`
feature fix are a benchmark and a bug fix respectively, not searched variants, so neither moves
that count.

## License and attribution

Apache License 2.0. See [LICENSE](LICENSE).

Attribution is a condition of the license, not a courtesy: Section 4 requires anyone
redistributing this work or a derivative of it to retain the copyright and attribution notices
and to reproduce the contents of [NOTICE](NOTICE). If you use this in a paper, post, product,
model or presentation, cite it as:

> Anklesh Rawat, "Signals-Before-Storms: a macro-aware tactical asset allocation engine", 2026.
> https://github.com/DogInfantry/Signals-Before-Storms

Market data is fetched at runtime from Yahoo Finance and FRED, is subject to their terms, and is
not redistributed here.

## Disclaimer

Research and educational code. Nothing here is investment advice, and none of these results are a
recommendation to trade. The headline finding is that the strategy underperforms simple
benchmarks.

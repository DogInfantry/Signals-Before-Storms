# Signals-Before-Storms: Macro-Aware Tactical Asset Allocation Engine

Detect hidden market regimes (Bull, Bear, Crisis) with a Hidden Markov Model, then switch
portfolio weights across equities, bonds, and gold using convex optimization. Everything is
validated with a strictly leak-proof expanding walk-forward and charged realistic transaction
costs, then compared against static 60/40 and equal-weight benchmarks.

**Headline result: the regime overlay does not earn its complexity.** On both universes it loses
to a two-line volatility rule, to a Statistical Jump Model, and to equal weight, while trading up
to ten times as much. Two pre-registered fixes and a second regime estimator were tried; all of
them failed, and they failed in the same direction, which is what makes the diagnosis credible.
That is the finding, not a bug, and it is worked through in [Results](#results) below.

## Results

### US (robustness universe)

SPY / TLT / GLD / VIX, walk-forward out-of-sample 2016-07-05 to 2023-12-29, n = 1886 trading days,
all books net of 7.5 bps per unit turnover and run through the identical cost engine.

| strategy | ann return | ann vol | Sharpe | max DD | turnover/yr | DSR | Sharpe 95% CI |
|---|---|---|---|---|---|---|---|
| **vol-threshold rule (ablation)** | **9.8%** | 10.3% | **0.958** | **-21.9%** | 3.61x | **0.863** | **(0.24, 1.65)** |
| static 60/40 | 7.5% | 11.5% | 0.690 | -27.6% | 0.41x | 0.643 | (-0.02, 1.42) |
| Jump Model regimes | 6.6% | 10.1% | 0.682 | -25.1% | **1.46x** | 0.636 | (-0.09, 1.40) |
| equal weight | 5.9% | 9.6% | 0.650 | -23.0% | 0.42x | 0.602 | (-0.09, 1.38) |
| HMM + drawdown feature | 5.4% | 9.6% | 0.590 | -28.0% | 3.88x | 0.538 | (-0.13, 1.34) |
| HMM + volatility targeting | 5.0% | 9.4% | 0.562 | -27.3% | 4.10x | 0.508 | (-0.18, 1.27) |
| HMM, vol-ranked states | 4.9% | 9.6% | 0.542 | -28.7% | 4.19x | 0.486 | (-0.21, 1.26) |
| HMM, unconditional moments | 4.8% | 9.6% | 0.535 | -27.4% | 2.74x | 0.478 | (-0.17, 1.25) |

Deflated Sharpe is quoted at **7 trials**, the honest count of variants actually searched. It was
0.928 for the rule at 4 trials; searching three more ideas lowered every number in that column,
which is exactly what deflation is for. Only the rule has a bootstrap interval excluding zero.
Every HMM variant straddles it.

### India (primary universe)

^NSEI / LIQUIDBEES.NS / GOLDBEES.NS / ^INDIAVIX, out-of-sample 2016-07-22 to 2023-12-29, n = 1814.
No liquid Indian duration ETF exists on Yahoo for this window (see
[data quality](#why-the-key-decisions)), so the defensive sleeve is an overnight cash fund,
labelled cash rather than pretending to be a bond. The 60/40 benchmark therefore renormalizes to
100% equity.

**Sharpe here is measured against the 3.79% rate that cash sleeve actually paid.** With a
near-riskless asset in the opportunity set, scoring against rf = 0 hands every defensive book a
large free Sharpe simply for holding cash: it inflated these numbers to 1.2-1.7 and reversed the
ranking.

| strategy | ann return | ann vol | Sharpe | max DD | turnover/yr | DSR |
|---|---|---|---|---|---|---|
| **vol-threshold rule (ablation)** | 7.5% | 4.2% | **0.848** | -6.5% | 0.88x | **0.783** |
| Jump Model regimes | 7.6% | 4.3% | 0.839 | -7.1% | **0.25x** | 0.775 |
| equal weight | 9.5% | 6.8% | 0.815 | -15.2% | 0.41x | 0.752 |
| HMM + drawdown feature | 7.0% | 4.0% | 0.759 | -6.1% | 1.24x | 0.707 |
| HMM, unconditional moments | 6.9% | 3.9% | 0.755 | -6.2% | 0.52x | 0.704 |
| HMM, regime-conditional moments | 7.0% | 4.1% | 0.744 | -6.1% | 1.10x | 0.693 |
| 60/40 (= 100% equity here) | 13.3% | 17.0% | 0.594 | -38.4% | 0.14x | 0.541 |

Same ordering as the US: the two-line rule first, the Jump Model close behind at a quarter of the
turnover, equal weight next, and every HMM variant below all three. An earlier version of this
table showed the HMM winning; that was an artifact of having no cash sleeve and scoring against a
zero risk-free rate. Fixing both reversed it.

### Why the HMM loses

The states are volatility states, and on this sample volatility carries no directional
information. Measured at the lag the strategy actually trades (label at close of t, return on
t+1):

| label | days | equity ann return | equity vol | equity Sharpe | mean VIX |
|---|---|---|---|---|---|
| 0 Bull | 665 | +10.9% | 8.7% | 1.23 | 13.0 |
| 1 Bear | 841 | +14.7% | 15.6% | 0.96 | 19.3 |
| 2 Crisis | 379 | +16.1% | 32.2% | 0.63 | 28.1 |

Volatility is ordered perfectly. Return is ordered backwards. De-risking on the Crisis label sells
the highest-returning days, because the violent rebounds of April 2020 and late 2022 are as
volatile as the crashes that preceded them. Three supporting checks:

- The modal label is Bear (45% of days) with equity Sharpe 0.96 - a perfectly healthy regime - and
  the stance map routes it to minimum variance. That, not Crisis, is where most of the drag is.
- Re-ranking states by trailing return instead of volatility lifts Sharpe only 0.542 -> 0.620 and
  leaves the Crisis label byte-identical. Reordering cannot add information the state space does
  not contain.
- BIC falls monotonically from K=2 through K=5 (39821, 34354, 31349, 29458), the signature of a
  model fitting a fat-tailed continuum rather than finding discrete states. There is no BIC
  support for K=3.

**A second, structurally different estimator fails identically.** A Statistical Jump Model was run
through the same walk-forward. Its jump penalty suppresses spurious switching and it does exactly
what it promises: mean dwell rises from 27 days to 194, turnover drops from 4.19x to 1.46x, and
Sharpe improves to 0.682. Yet its states agree with the HMM only 58.6% of the time and produce the
same broken ordering:

| Jump Model label | days | equity ann return | equity vol | mean VIX |
|---|---|---|---|---|
| 0 | 1164 | +13.5% | 12.8% | 16.3 |
| 1 | 615 | +12.8% | 19.3% | 21.4 |
| 2 | 106 | **+20.0%** | 46.6% | 31.8 |

Two different estimators, low label agreement, and both order volatility perfectly while ordering
direction not at all. That points at the state space, not at the HMM.

**Two fixes were pre-registered and both failed.**

*Volatility targeting.* If the states predict variance, stop betting on direction and target
constant risk instead. Sharpe moved 0.542 to 0.562 on US and was bit-identical on India. The
reason is instructive: minimum variance already holds the book at 9.6% (US) and 4.1% (India)
volatility, so a 10% target almost never binds. The strategy's problem is that it is *already*
too de-risked, and giving up return is what costs it.

*A directional feature.* Drawdown-from-peak was added to the state space, since realized
volatility is symmetric in sign and cannot tell a crash from an equally violent rebound. The
success criterion was stated before looking at any Sharpe: **the crisis label's next-day equity
return has to turn negative.** It went from +16.1% to +17.6%. It did not turn negative, so the
feature failed on its own terms. Sharpe did drift up to 0.590, and that is explicitly not being
counted as a win.

The overlay is not useless: it is barely dented in March 2020 while 60/40 takes -14%. It fails in
2022, a slow bear where bonds fell alongside equities and minimum variance had nowhere to hide.

### Figures

Written to `results/` by the driver (gitignored, regenerate in one command):

- `us_regime_overlay.png` - out-of-sample regime path shaded behind the equity curve. It
  independently flags Feb 2018, Q4 2018, COVID, and 2022.
- `us_equity_drawdown.png` - all five books, log growth over drawdown.
- `us_transition_heatmap.png` - transition matrix; the diagonal runs 0.96 to 0.98, so the states
  are genuinely persistent.

## Why the key decisions

- **3 regimes (Bull / Bear / Crisis):** chosen to match the economic states we allocate against,
  and then checked with a BIC sweep rather than assumed. The sweep does not support it (above).
- **These features:** multi-window momentum (direction), realized volatility (stress), VIX level,
  and a small set of FRED macro series (yield-curve slope, credit spread, financial conditions).
  FRED is fetched keyless and degrades gracefully when the endpoint is unreachable.
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
uv run python notebooks/real_run.py us
uv run python notebooks/real_run.py india
```

The `jump` extra pulls `jumpmodels` for the second regime engine. Without it the pipeline still
runs end to end and simply skips the Jump Model book.

The first run downloads prices from Yahoo and caches them under `data/`; every later run is
offline. `notebooks/driver.ipynb` is the same pipeline with the narrative attached.

## Reproducibility

Seeds are fixed in `config/config.yaml`. Downloaded data is cached under `data/` so reruns are
offline and deterministic. The config default deliberately keeps the volatility-ranked variant
even though the return-ranked one scored higher, because silently promoting the better-scoring
variant is the selection bias the deflated Sharpe exists to catch.

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

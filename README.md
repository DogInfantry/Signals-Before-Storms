# Signals-Before-Storms: Macro-Aware Tactical Asset Allocation Engine

Detect hidden market regimes (Bull, Bear, Crisis) with a Hidden Markov Model, then switch
portfolio weights across equities, bonds, and gold using convex optimization. Everything is
validated with a strictly leak-proof expanding walk-forward and charged realistic transaction
costs, then compared against static 60/40 and equal-weight benchmarks.

**Headline result: the regime overlay does not earn its complexity.** On US data it loses to a
two-line volatility rule and to 60/40; on Indian data it lands within noise of equal weight while
trading three times as much. That is the finding, not a bug, and the diagnosis is in
[Results](#results) below.

## Results

### US (robustness universe)

SPY / TLT / GLD / VIX, walk-forward out-of-sample 2016-07-05 to 2023-12-29, n = 1886 trading days,
all books net of 7.5 bps per unit turnover and run through the identical cost engine.

| strategy | ann return | ann vol | Sharpe | max DD | Calmar | turnover/yr |
|---|---|---|---|---|---|---|
| HMM, vol-ranked states | 4.9% | 9.6% | 0.542 | -28.7% | 0.170 | 4.19x |
| HMM, return-ranked states | 5.7% | 9.7% | 0.620 | -28.5% | 0.200 | 3.77x |
| **vol-threshold rule (ablation)** | **9.8%** | 10.3% | **0.958** | **-21.9%** | **0.446** | 3.61x |
| static 60/40 | 7.5% | 11.5% | 0.690 | -27.6% | 0.273 | 0.41x |
| equal weight | 5.9% | 9.6% | 0.650 | -23.0% | 0.258 | 0.42x |

Deflated Sharpe at 4 honest trials: 0.630 / 0.706 / **0.928**. Stationary-bootstrap 95% CI on the
Sharpe: the two HMM variants straddle zero, the rule does not - (0.238, 1.652).

### India (primary universe)

^NSEI / GOLDBEES.NS / ^INDIAVIX, out-of-sample 2016-07-22 to 2023-12-29, n = 1816. No Indian bond
ticker is resolved yet, so the book allocates over equity and gold only and the 60/40 benchmark
renormalizes to 100% equity.

| strategy | ann return | ann vol | Sharpe | max DD | Calmar | turnover/yr |
|---|---|---|---|---|---|---|
| HMM, regime-conditional moments | 12.6% | 10.2% | 1.215 | -22.4% | 0.564 | 1.52x |
| HMM, unconditional moments | 12.1% | 10.1% | 1.176 | -22.5% | 0.537 | 1.02x |
| vol-threshold rule (ablation) | 12.0% | 10.4% | 1.136 | -22.5% | 0.532 | 0.65x |
| 60/40 (= 100% equity here) | 13.3% | 17.0% | 0.817 | -38.4% | 0.345 | 0.14x |
| **equal weight** | 12.3% | 10.2% | **1.185** | -22.5% | 0.546 | 0.43x |

The HMM does come first here, by 0.03 Sharpe over 1/N, for three and a half times the turnover.
That is not a result, it is a rounding error with a transaction-cost bill attached. Every
diversified book lands at 10.2% vol and Sharpe ~1.2 while the all-equity benchmark sits at 17% vol
and 0.82, which says the gold sleeve is doing the work and the regime switching is along for the
ride.

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
  same pipeline re-runs on US assets as an out-of-sample check. India currently has no bond
  ticker resolved, so it allocates over equity and gold only.
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
uv sync --extra dev
uv run pytest -q
uv run python notebooks/real_run.py us
uv run python notebooks/real_run.py india
```

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

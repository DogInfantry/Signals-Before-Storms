# EXPLAINER: how to read this project without a finance background

The [README](README.md) assumes you already know what a backtest is, what a Sharpe ratio measures,
and why anyone would deflate one. This file assumes none of that.

It explains the vocabulary in the order the pipeline actually uses it, and it states no result the
README does not already state. Every number quoted here is copied from a README table.

---

## The one-paragraph version

A **backtest** replays a trading strategy over history, one day at a time, pretending you did not
know what came next. Everything difficult about backtesting lives in that last clause. This project
builds one carefully, applies it to a model that detects hidden market "regimes", and reports that
the model works exactly as designed and still does not make money. The reason is the interesting
part: the regimes it finds describe how *violent* the market is, not which *direction* it is going.

---

## 1. What a backtest is, and how they go wrong

You have a rule ("hold more gold when markets look dangerous"). You want to know whether it would
have worked. So you walk through history day by day, apply the rule using only what you would have
known at the time, and add up the result.

The failure mode has a name: **look-ahead bias**, also called **leakage**. It is any place where
information from the future reaches a decision in the past. It is subtle, it is usually accidental,
and it makes almost any strategy look brilliant.

Five specific leaks, and how this repo blocks each one:

| The leak | The defence here |
|---|---|
| A feature secretly averages future days | Every feature is **causal**: right-aligned rolling windows only |
| You rescale the data using statistics from the whole sample | The scaler is **fit on training rows only**, inside each fold |
| You fit the model once on everything, then "test" on part of it | The model is **refit inside every fold** |
| You infer past states using the whole series, including the end | Regimes are decoded with a **forward filter**, never whole-sequence Viterbi |
| You trade on a signal at the same instant you compute it | A signal seen at the close of day *t* can only move money on day *t+1* |

Each of those is asserted by a unit test rather than promised in prose. That is the difference
between a credible backtest and a marketing one.

**Why the last row matters most.** If you compute a signal from today's closing price and then
assume you bought at today's closing price, you have bought at a price you only learned at the
moment it stopped being available. That single mistake can manufacture an entire fake strategy.

## 2. Walk-forward, and why the window expands

The naive approach fits a model on all of 2015 to 2023 and then scores it on 2015 to 2023. It will
look excellent, because it has already seen the answers.

**Walk-forward** instead does this: fit on the past, score on the next unseen block, roll forward,
repeat. **Expanding** means the training window grows each time (fit on 2015, test 2016; fit on
2015-2016, test 2017; and so on), which mimics a real person who accumulates history rather than
forgetting it.

What comes out is an **out-of-sample** record: 1,814 trading days for India, 1,886 for the US, every
one of them scored by a model that had not seen it.

## 3. Costs, turnover, gross and net

Trading is not free. **Turnover** measures how much of the portfolio you churn; every unit of it
costs money (7.5 basis points here, so 0.075%).

- **Gross** return is before costs.
- **Net** return is after.

A strategy that trades constantly can look good gross and lose money net. That is why the README
publishes both columns side by side.

The important structural detail: this project charges **the benchmarks the same way, through the
same function**. A benchmark costed differently is not a benchmark, it is a strawman.

## 4. The scorecard: four numbers, four different questions

| Metric | Question it answers | Direction |
|---|---|---|
| **Sharpe ratio** | How much return per unit of bumpiness, above cash? | Higher better |
| **Sortino ratio** | Same, but counting only *downward* bumps | Higher better |
| **Max drawdown** | What was the worst peak-to-trough loss? | Closer to zero better |
| **Calmar ratio** | Return divided by that worst loss | Higher better |

**Sharpe** is the industry default and it is blind to shape: a strategy that grinds out steady
losses and one that jumps around can score the same. **Max drawdown** is the number that actually
makes people abandon a strategy, because it is the number they feel.

A note that matters here: Sharpe measures return *above the risk-free rate*. If one book quietly
sits in cash and you forget to subtract what cash paid, you hand it free credit for doing nothing.
This repo derives that rate from the actual cash holding, because an earlier version of these tables
did not, and reported a win that was not there.

## 5. Benchmarks, and the ablation that matters most

A strategy is only "good" compared with something dumb, cheap and available to anyone. This project
uses three:

- **60/40** - 60% equities, 40% bonds or cash. The default portfolio of the entire industry.
- **Equal weight** - split evenly across everything you hold. Embarrassingly hard to beat.
- **The volatility-rule ablation** - a two-line rule with no machine learning at all: when realized
  volatility is high, de-risk.

That third one is the honest test. It asks whether the Hidden Markov Model, the convex optimizer and
the walk-forward machinery beat *two lines of code*. On the US universe, they did not.

An **ablation** in general means: remove one piece of the system and re-measure. If the result does
not change, that piece was decoration.

## 6. Overfitting, and why the Sharpe gets deflated

Try twenty strategies, report the best one, and its Sharpe ratio is inflated by luck alone. This is
not fraud, it is arithmetic: the maximum of twenty noisy numbers is larger than any one of them was
expected to be.

The **deflated Sharpe ratio** corrects for that. You declare how many variants you tried, and it
discounts the winner accordingly. This project declares **7 trials** and applies the discount to
every headline number.

The discipline that goes with it matters more than the formula:

- The config keeps the *worse*-scoring configuration on purpose. A drawdown-feature variant tops the
  India table at 0.877 Sharpe and is deliberately **not** the default, because it failed a criterion
  written down *before* the Sharpe was computed.
- Promoting the better-scoring variant after seeing the score is precisely the bias the deflation
  exists to punish. Doing both would be theatre.

**Pre-registration** is that habit: decide what would count as success before you look.

## 7. Confidence intervals, and the block bootstrap

A Sharpe ratio computed on one history is a single draw from a noisy process. A **confidence
interval** says how much it could have wobbled.

The technique here is a **bootstrap**: resample the observed returns thousands of times and watch
the statistic move. The refinement is that it resamples in **blocks** of consecutive days rather
than individual days, because market returns cluster (calm weeks follow calm weeks). Shuffling
single days would destroy that structure and understate the uncertainty.

If an interval **includes zero**, you cannot claim the result differs from zero.

## 8. The paired difference test, and the mistake it prevents

This is the one that trips up most people, including two of the three reviewers whose feedback
prompted this file.

**Two overlapping confidence intervals do not mean two strategies are equivalent.** Each interval
answers a *separate* question: "is book A better than nothing?" and "is book B better than nothing?"
Neither says anything about the gap between A and B.

To compare them you need the interval of the **difference**, resampled on the *same dates* for both
books. Because both hold similar assets on the same days, most of their movement is the same market
moving; differencing cancels it, and the resulting interval comes out roughly **three times
tighter**.

That tighter test is what let this project make its central claim honestly. Under it, every book on
both universes spans zero against both benchmarks. "Indistinguishable from the benchmarks" is
earned, not assumed.

## 9. Episodes, not days

The most load-bearing idea in the whole repository, and the cheapest to apply anywhere.

The India "Crisis" regime covers **261 days**. That sounds like a lot of evidence. It is not. Those
261 days are **14 separate occurrences**, and one of them (COVID) is enormous. So the effective
sample size is 14, not 261, and arguably closer to 1.

The check: **drop the single largest episode and see whether the finding survives.**

Applied here, it did the opposite of flattering the project. It **retracted the project's own
apparent discovery**. A Jump Model regime reading -17.1% looked like the only directional state
found anywhere in this work; counted properly it was two episodes, one of which was positive, and
removing COVID flipped it to +30.17%. The retraction is documented in the README rather than quietly
dropped.

Before believing any claim about a market regime, anywhere, count the episodes.

## 10. What the model actually found

A **Hidden Markov Model** assumes the market is in one of a few unobservable states, that each state
produces a characteristic pattern of observations, and that states persist and occasionally switch.
You never see the state; you infer it from what the market does.

It works. The states are real and persistent. Here is what they are, measured at the lag the
strategy actually trades:

| Regime label | India next-day return | India volatility |
|---|---|---|
| 0 Bull | +10.2% | 11.2% |
| 1 Bear | +15.0% | 14.9% |
| 2 Crisis | +18.4% | 31.7% |

**Volatility rises perfectly with the label. Return rises backwards.** The same pattern appears on
the US universe.

That single table is the whole result. The model found **volatility states**, and volatility is
symmetric in sign: a crash and a violent rebound both register as high volatility, because both are
large moves. So the "Crisis" label does not mean "prices will fall", it means "prices will move a
lot". De-risking on it sells the rebounds of April 2020 and late 2022 along with the crashes that
preceded them.

A state variable has to predict **direction** before a directional bet on it can pay.

## 11. So what is the result?

- On risk-adjusted return, the overlay never separates from a simple 60/40 or equal-weight
  portfolio. Every paired interval spans zero.
- On **max drawdown** it wins clearly on India: **-6.2%** against 60/40's **-23.7%**.
- The reason is diagnosed rather than guessed, confirmed by a second, structurally different model
  and on a second market two decades apart in structure.

That is a **rigorous negative result**: a claim that did not work, established carefully enough that
the failure itself is informative. Four separate attempts to rescue it are documented, all failed,
all in the same way.

It is published as-is, with its own retraction on record, because a negative result you can trust is
worth more than a positive one you cannot.

---

## Glossary, quick reference

| Term | Meaning |
|---|---|
| **Backtest** | Replaying a strategy over history using only what was known at the time |
| **Look-ahead bias / leakage** | Future information reaching a past decision. The cardinal sin |
| **Causal feature** | A feature computed only from past and present data |
| **Walk-forward** | Fit on the past, test on the next unseen block, roll forward |
| **Out-of-sample** | Scored on data the model was not fitted on |
| **Execution lag** | The delay between seeing a signal and being able to trade it. One day here |
| **Turnover** | How much of the portfolio you churn. Drives cost |
| **Basis point (bp)** | One hundredth of a percent. 7.5 bps = 0.075% |
| **Gross / net** | Before / after transaction costs |
| **Sharpe ratio** | Return per unit of volatility, above the risk-free rate |
| **Sortino ratio** | Sharpe, counting only downside volatility |
| **Max drawdown** | Worst peak-to-trough loss |
| **Calmar ratio** | Return divided by max drawdown |
| **Benchmark** | The dumb cheap alternative you must beat to matter |
| **Ablation** | Removing one component to see whether it was doing anything |
| **Overfitting** | Fitting noise. Looks brilliant in-sample, fails live |
| **Deflated Sharpe** | Sharpe discounted for how many variants you tried |
| **Trial count** | How many variants you tried. Honesty depends on stating it |
| **Pre-registration** | Writing down what counts as success before looking |
| **Bootstrap** | Resampling data repeatedly to measure uncertainty |
| **Block bootstrap** | Resampling in runs of consecutive days, to preserve clustering |
| **Paired difference test** | The interval of the *gap* between two books, resampled on shared dates |
| **Episode** | One continuous occurrence of a regime. The real unit of evidence |
| **Hidden Markov Model (HMM)** | A model of unobservable states inferred from observed behaviour |
| **Viterbi decode** | Most likely state path given the *whole* series. Not causal, overlays only |
| **Forward filter** | State estimate using only data up to now. Causal, safe to trade |
| **Convex optimization** | Solving for portfolio weights with a guaranteed best answer |
| **Min-variance / max-Sharpe** | Two such objectives: lowest wobble, or best return per wobble |
| **Rigorous negative result** | A failure established carefully enough to be informative |

---

## Where to go next

- [README.md](README.md) for the full method, the results tables and the four failed rescues.
- The [live panel](https://signals-before-storms.vercel.app) to toggle books, gross against net,
  and India against the US, and watch the ranking move.
- The [research log](https://signals-before-storms.vercel.app/story) for the long-form version.
- [The Regime Monitor](https://regime-monitor-lyart.vercel.app/) for the same detection pipeline
  running live on eleven markets. Detection only: the part of this research that worked.

Nothing here is investment advice.

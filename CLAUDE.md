# CLAUDE.md - Signals-Before-Storms

## Project
**Signals-Before-Storms**: Macro-Aware Tactical Asset Allocation Engine. Capstone for the Summer
of Quant course. Detect hidden market regimes (Bull, Bear, Crisis) with a Hidden Markov Model,
switch portfolio weights (equity, bond/cash, gold) via convex optimization per regime, validate
leak-proof with an expanding walk-forward, charge transaction costs, benchmark against static
60/40, equal weight and a no-HMM ablation.

**PUBLIC**: https://github.com/DogInfantry/Signals-Before-Storms (Apache-2.0, CI green).

- Repo name decided 2026-07-24. Import package stays `regime_shift` deliberately: renaming would
  churn every import and test for no gain. pyproject distribution name is `signals-before-storms`.
- LICENSE is Apache-2.0, copyright `2026 Anklesh Rawat (DogInfantry)`, with a NOTICE file. Chosen
  over MIT because Section 4 makes attribution an explicit condition and forces derivative works
  to carry NOTICE forward.

Stack: Python 3.11+ (env resolves to 3.13), uv-managed. numpy 2.5.1, pandas 3.0.5, scipy 1.18,
matplotlib, scikit-learn 1.9, hmmlearn 0.3.3, cvxpy 1.9.2, yfinance 1.5.1 (+curl_cffi), keyless
FRED, pydantic, pyyaml. jumpmodels 0.1.1 in the `jump` extra (INSTALLED and working).

## Standing user rules (do not violate)
- NEVER add Claude or any AI as contributor or Co-Authored-By in commits, PRs, or repo. Plain
  commits.
- NO em dashes or en dashes anywhere (code, docs, prose, commits). Use hyphens, commas, parens.
- Do not push or create anything outward-facing without an explicit go-ahead.

## Architecture and key decisions
- Two markets: India PRIMARY (^NSEI, LIQUIDBEES.NS cash, GOLDBEES.NS, ^INDIAVIX) per the graded
  spec; US as out-of-sample robustness (SPY, TLT, GLD, ^VIX).
- Modular `src/` package plus one thin driver notebook (structure over a single mega-notebook).
- Leak-proofing is the whole point: causal features, train-only standardization inside each fold,
  model re-fit per fold, CAUSAL decode of test regimes (never whole-block Viterbi), 1-day
  execution lag. Each is asserted by a unit test, not merely claimed.
- Regime labels: canonical integers 0..n-1, ALWAYS ascending risk (0 = calmest = Bull).
  `REGIME_NAMES_3 = (Bull, Bear, Crisis)`. Stable across per-fold refits via rank ordering.
- ONE cost engine. `backtest.run_book` marks every book, strategy and benchmark alike, so the
  comparison is like-for-like by construction. A benchmark costed differently is not a benchmark.
- Results are deflated. Probabilistic + deflated Sharpe and a stationary bootstrap CI accompany
  every headline number, with the trial count stated honestly.

## File map
- `config/config.yaml`: all knobs (universes, dates, windows, HMM, costs, seed, rebalance,
  rebalance_confirm_days, conditional_moments, conditional_min_obs). `india.bond` is deliberately
  EMPTY, `india.cash: LIQUIDBEES.NS` is the defensive sleeve instead (see data quality below).
- `src/regime_shift/config.py`: typed pydantic loader, `load_config() -> Config`.
- `src/regime_shift/data.py`: `load_prices` (yfinance + pickle cache), `load_macro` (keyless FRED
  CSV), `drop_return_outliers` (vendor-error guard, see landmine), `build_master` (log returns +
  vix + causal 1-day-lagged macro; warns and continues if FRED unreachable). `_ASSET_ROLES =
  (equity, bond, cash, gold)`. Master cols: `equity_ret[/bond_ret][/cash_ret]/gold_ret`, `vix`.
- `src/regime_shift/features.py`: `add_momentum` (rolling SUM of equity_ret = log momentum),
  `add_realized_vol` (rolling std * sqrt252), `build_features(master, cfg, drawdown=False)` ->
  `mom_{5,21,63,126}`, `vol_{5,21,63}`, `vix`, `vix_chg`, optional `dd_peak`, macro passthrough.
  All causal (right-aligned rolling). NO standardization here. Equity only.
- `src/regime_shift/regime.py`: `RegimeModel(engine="hmm"|"jump")`. `fit(X, rank_by, tiebreak)` ->
  canonical labels via `_canonical_order` (sorts raw states by within-state mean rank_by ascending;
  PADS to a full permutation and warns if the fit did not occupy every state). `decode` =
  whole-sequence Viterbi (DESCRIPTIVE OVERLAYS ONLY). `decode_causal` = O(n) log-space forward
  filter (HMM) or `predict_online` (jump), leak-proof by construction. `transition_matrix`, `bic`
  (both HMM-only, raise NotImplementedError for jump); module fns `dwell_times`, `bic_sweep`.
- `src/regime_shift/walkforward.py`: `expanding_walk_forward_splits(n, min_train, test_size, step)`
  -> disjoint expanding. `run_walk_forward(features, cfg, engine, rank_col, rank_sign)`: per fold
  StandardScaler on TRAIN only, model refit on scaled train ranked by `rank_sign*features[rank_col]`
  (default `vol_21`, ascending), causal decode of [train;test] carrying train history, keep test
  labels. Returns int Series over OOS dates. `rank_col`/`rank_sign` DEFINE "ascending risk"; both
  are train-only and leak-free. Execution lag is NOT here (backtest owns it).
- `src/regime_shift/optimize.py`: `ledoit_wolf_cov`, `shrink_mu`, `min_variance_weights`,
  `max_sharpe_weights` (Schaible transform, falls back to min-var if no positive shrunk mean),
  `defensive_weights` (min-var with any column matching "equity" hard-capped), `regime_weights`
  dispatch (0 -> Bull max-Sharpe, n-1 -> Crisis defensive, middle -> Bear min-var). Long-only,
  budget 1, weight_cap. `psd_wrap` on the shrunk cov. NO turnover penalty (backtest owns churn).
- `src/regime_shift/backtest.py`:
  - `asset_cols(returns)` public (benchmarks imports it).
  - `run_book(rets, dates, decide, cfg)` is the SHARED engine. `decide(t) -> (label, target|None)`
    is called at the CLOSE of t and its target earns t+1's return. That is the execution lag, and
    it lives in one place so every strategy inherits it.
  - `_drift` divides by the portfolio value multiplier `1 + w@r`, NOT the grown weight sum, so a
    partially invested book keeps an uninvested residual earning nothing. Identical arithmetic
    when `sum(w) == 1`, which is why generalizing it left every published number untouched.
  - `run_backtest(regimes, returns, cfg, confirm_days, mu_shrink, conditional, target_vol)`.
    Cadence from `cfg.rebalance`: `on_regime_change` (hysteresis: a new label must persist
    `rebalance_confirm_days`) or `monthly`. `conditional` estimates mu/Sigma from PAST SAME-LABEL
    days, falling back to full history below `cfg.conditional_min_obs`. `target_vol` scales the
    whole book toward a constant risk budget, long-only, never levered.
  - Log returns are converted with `expm1` before any portfolio sum (a weighted sum of logs is
    not the log of the portfolio). Non-trade days have EXACTLY zero turnover and zero cost.
  - Output cols: `regime` (Int64), `w_<asset>`, `turnover`, `cost`, `ret_gross`, `ret_net`,
    `equity_gross`, `equity_net`.
- `src/regime_shift/metrics.py`: takes SIMPLE returns. `ann_return` (geometric), `ann_vol`,
  `sharpe(rf)`, `sortino`, `max_drawdown` (negative), `calmar`, `probabilistic_sharpe` (Bailey/
  Lopez de Prado PSR; benchmark arg is ANNUALIZED), `expected_max_sharpe(n_trials, trial_sr_std)`,
  `deflated_sharpe`, `optimal_block_length` (Politis-White 2004; ~2.9 days on real US returns),
  `bootstrap_ci` (Politis-Romano STATIONARY bootstrap, vectorized; `mean_block=None` reads it off
  the data), `summary(book, col, periods, rf)`. **Pass `rf` whenever a cash-like asset exists** or
  defensive books get a free Sharpe for holding cash.
- `src/regime_shift/benchmarks.py`: all routed through `run_book`. `static_book(..., target,
  rebalance="monthly"|"never")`, `equal_weight`, `sixty_forty` (renormalized over columns present,
  so India = 100% equity), `vol_rule_regimes(returns, cfg, window, lookback, quantile)` -> causal
  0/(n-1) labels, the no-HMM ablation. Feed it to `run_backtest` sliced to the HMM OOS index.
- `src/regime_shift/plots.py`: `REGIME_COLORS`, `regime_overlay` (shades each run up to the NEXT
  run's start, else a one-day flicker is a zero-width axvspan and renders as a white stripe),
  `equity_drawdown(books)`, `transition_heatmap(P)`. All take/return an axis; caller saves.
- `src/regime_shift/narrate.py`: STUB. Optional LLM narration, report-only. Never implemented.
- `tests/` (39 total, all green, synthetic/seeded/offline on purpose): `test_smoke` 2,
  `test_features` 2, `test_regime` 5 (causal decode, canonical labels, transition, dwell, jump
  engine via importorskip), `test_walkforward` 2, `test_optimize` 5, `test_backtest` 6 (1-day lag
  by flipping a future label, flat-then-entry, conditional moments + fallback, target_vol,
  zero-turnover-is-free), `test_metrics` 9, `test_benchmarks` 5 (incl. cash sleeve), `test_data` 3.
- `notebooks/real_run.py`: the real-data driver. `uv run python notebooks/real_run.py [us|india]`.
  Builds the master from cache, runs the walk-forward, scores 8 books, prints the
  forward-return-by-label tables, the scorecard, and the deflation table, writes 3 figures to
  `results/`. matplotlib Agg, no display needed.
- `notebooks/driver.ipynb`: 24 cells, executes clean with 3 embedded figures. Same pipeline plus
  the narrative. Regenerate: `uv run papermill notebooks/driver.ipynb notebooks/driver.ipynb
  --kernel python3`.
- `README.md`: leads with the negative result, both universes, why-it-loses, the failed rescues,
  data quality, deflation rationale, attribution terms.
- Build plan: kept outside the repo in the local Claude Code plans dir, deliberately not
  fetchable from a clone. README + this file carry everything needed to resume.

## Current state
- **Everything is committed and pushed. Working tree clean. CI green on main.**
- 39 tests green, ruff clean. `uv sync` alone gives a working dev env; `uv sync --extra jump` adds
  the second regime engine.
- Real data pulled and cached in `data/cache/`. yfinance fine; **FRED is blocked on this network**,
  so the master currently has NO macro columns and degrades gracefully.
  US master 2263x4 (2015-01-02..2023-12-29), India master 2191x4 (equity/cash/gold/vix).
- Figures in `results/` (gitignored): `{us,india}_{regime_overlay,equity_drawdown,transition_heatmap}.png`.
- Phases 0-9 done plus three follow-up extensions. Only `narrate.py` remains a stub (optional).

### Headline numbers (US, OOS 2016-07-05..2023-12-29, n=1886, net of 7.5bps, DSR at 7 trials)
```
vol_rule_ablation  sharpe 0.958  ann 0.098  maxDD -0.219  turn 3.61x  DSR 0.863  CI ( 0.238, 1.652)
60_40              sharpe 0.690  ann 0.075  maxDD -0.276  turn 0.41x  DSR 0.643  CI (-0.023, 1.422)
jump_regime        sharpe 0.682  ann 0.066  maxDD -0.251  turn 1.46x  DSR 0.636  CI (-0.092, 1.399)
equal_weight       sharpe 0.650  ann 0.059  maxDD -0.230  turn 0.42x  DSR 0.602  CI (-0.086, 1.382)
hmm_drawdown_feat  sharpe 0.590  ann 0.054  maxDD -0.280  turn 3.88x  DSR 0.538
hmm_vol_targeted   sharpe 0.562  ann 0.050  maxDD -0.273  turn 4.10x  DSR 0.508
hmm_conditional    sharpe 0.542  ann 0.049  maxDD -0.287  turn 4.19x  DSR 0.486  CI (-0.211, 1.263)
hmm_unconditional  sharpe 0.535  ann 0.048  maxDD -0.274  turn 2.74x  DSR 0.478
```
### India (primary, OOS 2016-07-22..2023-12-29, n=1814, Sharpe vs rf=3.79% that cash actually paid)
```
vol_rule 0.848 | jump 0.839 (turnover 0.25x) | equal_weight 0.815 | drawdown 0.759 |
hmm_unconditional 0.755 | hmm_conditional 0.744 = hmm_vol_targeted 0.744 | 60_40 (=100% eq) 0.594
```
SAME ORDERING AS US. Only the vol rule has a bootstrap CI excluding zero.

## THE CENTRAL FINDING (diagnosis complete, do not re-litigate without new evidence)
HMM states here are VOLATILITY states, and volatility states carry no directional information.
Evidence, all out-of-sample at the traded 1-day lag:
- Next-day equity by vol-ranked label: L0 +10.9% (vol 8.7, VIX 13), L1 +14.7% (15.6, 19),
  L2 +16.1% (32.2, 28). Vol ordering perfectly monotone; RETURN ordering monotone the WRONG WAY.
  De-risking on the crisis label sells the best days: 2020 and 2022 rebounds are as violent as the
  crashes that preceded them.
- The modal label is Bear (841/1886 days) with equity Sharpe 0.96, a perfectly good regime, routed
  by the stance map to min-variance. That, not Crisis, is where most of the damage is.
- BIC falls monotonically (K=2 39821, 3 34354, 4 31349, 5 29458): a fat-tailed continuum being
  fitted, not discrete states. No BIC support for K=3.
- The 2-line vol-threshold ablation DOES separate direction: L0 +19.7% (Sharpe 1.39) vs L2 -9.6%
  (Sharpe -0.16), only 48.9% label agreement with the HMM. It wins on every metric.

**FOUR RESCUE ATTEMPTS, ALL FAILED, ALL THE SAME WAY:**
1. **Re-rank by return** (`rank_col="mom_21", rank_sign=-1`): 0.542 -> 0.620, still under 60/40,
   and label 2 came out IDENTICAL (same 379 days, same +16.1%). Reordering cannot add information
   the state space does not contain.
2. **Jump Model** (the flagship): does exactly what it advertises. Dwell 27d -> 194d, turnover
   4.19x -> 1.46x, Sharpe -> 0.682. Agrees with the HMM only 58.6% of the time, so it is a
   genuinely different partition, and its crisis label STILL has the highest forward return
   (+20.0%, 106 days, vol 46.6%). Two unrelated estimators, low agreement, same broken ordering
   => the fault is the STATE SPACE, not the HMM.
3. **Volatility targeting** (`target_vol=0.10`): 0.542 -> 0.562 US, bit-identical on India. It
   barely binds, because min-var already pins the book at 9.6% (US) / 4.1% (India) vol. The
   strategy is not taking too much risk, it is taking too little and forfeiting return.
4. **Drawdown feature** (`build_features(drawdown=True)`): PRE-REGISTERED criterion was "crisis
   label forward return must turn negative". It went +16.1% -> +17.6%. FAILED on its own terms.
   Sharpe drifted to 0.590; explicitly NOT counted as a win. Do not re-litigate via the Sharpe.

This IS the report's flagship result. A rigorous negative with a diagnosis beats a tuned positive.
Config default deliberately stays `rank_col="vol_21"`; do NOT quietly switch to the variant that
scored 0.08 higher, that is precisely the selection bias the DSR exists to punish.

## DATA-QUALITY LANDMINES (both fixed, read before trusting any number)
1. **GOLDBEES.NS 100x round trip.** Log return -4.6065 on 2019-12-19 and +4.6052 on 2019-12-23.
   Two bad prints in 2193 rows inflated gold's return std from 0.011 to 0.139 and poisoned every
   Indian covariance, regime fit and Sharpe (India "ran" at 44.5% vol). `drop_return_outliers` now
   NaNs any daily |log return| > 0.5 and warns loudly; `tests/test_data.py` pins it, including
   that a -13% crash day is NOT dropped. US was unaffected (verified by re-run).
2. **No usable Indian duration ETF on Yahoo for 2015-2023.** Measured before rejecting:
   SETF10GILT.NS 39.0% ann vol / 21.7% zero-return days, LTGILTBEES.NS 15.7% / 9.1%, and both
   start mid-sample (2016-06, 2018-05) which `build_master`'s `dropna()` would propagate into a
   ~18% shorter OOS window. That is thin-trading noise around NAV, and `drop_return_outliers`
   would NOT catch it because no single print is absurd. LIQUIDBEES.NS (1.1% vol, full history) is
   used instead and is called **cash**, not a bond.
3. **rf matters once cash exists.** `metrics.summary(rf=)` and `real_run.py` derives rf from
   `cash_ret`. An earlier README reported India as an HMM WIN (1.215 vs 1.185); that was an
   artifact of having no cash sleeve AND scoring against rf=0. Do not resurrect those numbers.

## Active task
**Nothing in flight. Clean stopping point.** Repo public, CI green, tree clean, all loose ends
closed. See Next Steps for options if work resumes.

## Next steps
1. **Nothing is required.** The project is complete and internally consistent. Stopping here is a
   legitimate choice; the deliverable is a rigorous negative result with a diagnosis.
2. If more modelling is wanted, the ONLY lead the evidence supports is a **directional state
   variable**: credit spreads (FRED `BAA10Y`, already in the config macro list, but FRED is
   blocked on this network so it needs a different network or a vendor), market breadth, earnings
   revisions, or positioning. Realized vol and VIX are symmetric in sign and provably cannot
   supply direction. NOTE the DSR budget is nearly spent: at 7 trials any new variant needs a
   materially larger raw Sharpe just to hold its ground.
3. `narrate.py` is still a stub, explicitly optional, lowest research value of anything left. It
   demos well if the report needs a flourish.
4. India still has no true duration sleeve. Revisit only if a better vendor than Yahoo appears.
5. Nice-to-have polish: `uv run pre-commit install` (configured but NOT installed, so nbstripout
   never runs and the committed notebook keeps its outputs, which is arguably what you want for a
   portfolio repo).

## How to run
```
uv sync --extra jump          # dev group installs by default
uv run pytest -q              # 39 tests
uv run ruff check .
uv run python -m regime_shift.data                 # data smoke (network)
uv run python notebooks/real_run.py us             # full run + figures
uv run python notebooks/real_run.py india
uv run papermill notebooks/driver.ipynb notebooks/driver.ipynb --kernel python3
```

## Gotchas
- **DEV DEPS LIVE IN ONE PLACE: `[dependency-groups] dev`.** There used to ALSO be a `dev` extra
  under `[project.optional-dependencies]`, and `uv sync --dev` installs the GROUP, so CI got
  ipykernel and no ruff/pytest and failed every push (unable to spawn ruff). Do not re-add a dev
  extra. CI runs `uv sync --extra jump`.
- **`jump_penalty` is SCALE-DEPENDENT.** The RegimeModel default 50.0 suits the 9 real
  standardized features; on a small/low-dim set it collapses the fit to ONE state. That used to
  crash `_to_canonical` with an opaque broadcast error. `_canonical_order` now pads to a full
  permutation and warns. An HMM can leave a state unvisited the same way.
- **GateGuard hook** (`ECC gateguard-fact-force`) DENIES the FIRST Write/Edit of every file per
  session, including edits of existing files. Retry after stating facts (importers via Grep,
  public API, data schema, verbatim user instruction). Disable with `ECC_GATEGUARD=off` or
  `ECC_DISABLED_HOOKS=pre:edit-write:gateguard-fact-force`.
- **PowerShell here-strings eat double quotes** when passed to native commands. A `git commit -m`
  message containing `"` silently became pathspecs and the commit did NOT happen. Always verify
  with `git log` after committing. Same class of bug mangled a `python -c` script into a syntax
  error. Prefer single quotes inside; verify, do not assume.
- `regime.decode_causal` uses hmmlearn's PRIVATE `_compute_log_likelihood` (fine on pinned 0.3.3).
  `decode()` (whole-sequence Viterbi) is NOT causal; NEVER use it for the walk-forward test decode.
- `max_sharpe_weights` needs `psd_wrap(cov)` (LedoitWolf cov can carry tiny negative eigenvalues).
- hmmlearn emits ~500 NumPy-2.5 DeprecationWarnings per run (internal `a_sum.shape = shape`);
  noise, not our code.
- FRED (fred.stlouisfed.org) is blocked on this network; macro degrades gracefully with a warning.
- yfinance 1.x returns MultiIndex columns (field, ticker); `data.py` handles single vs multi.
- `git add -A` once swept in `.claude/` plugin sqlite files; `.claude/` is gitignored now. Watch
  for stray dirs before any commit.

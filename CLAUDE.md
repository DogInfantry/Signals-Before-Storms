# CLAUDE.md - Signals-Before-Storms

## Project
Signals-Before-Storms (repo name DECIDED 2026-07-24; verified free on GitHub, 404 under
DogInfantry and 0 global name hits). Import package stays `regime_shift`, deliberately: renaming
it would churn every import and test for no gain. Distribution name in pyproject is
`signals-before-storms`. LICENSE is Apache-2.0 (copyright 2026 Anklesh Rawat (DogInfantry)) with a
NOTICE file, chosen over MIT because Section 4 makes attribution an explicit condition and forces
derivative works to carry NOTICE forward.
Macro-Aware Tactical Asset Allocation Engine. Capstone for the Summer of Quant
course. Detect hidden market regimes (Bull, Bear, Crisis) with a Hidden Markov Model, switch
portfolio weights (equities, bonds, gold) via convex optimization per regime, validate
leak-proof with an expanding walk-forward, charge transaction costs, benchmark against static
60/40 and equal-weight.

Stack: Python 3.11+ (env resolved to 3.13), uv-managed. numpy 2.5, pandas 3.0, scipy,
matplotlib, scikit-learn 1.9, hmmlearn 0.3.3, cvxpy 1.9.2, yfinance 1.5.1 (+ curl_cffi),
keyless FRED, pydantic, pyyaml. Optional extras: jumpmodels (NOT installed), PyPortfolioOpt,
skfolio, quantstats, arch.

## Standing user rules (do not violate)
- NEVER add Claude or any AI as contributor or Co-Authored-By in commits, PRs, or repo. Plain commits.
- NO em dashes or en dashes anywhere (code, docs, prose, commits). Use hyphens, commas, or parentheses.

## Architecture and key decisions
- Two markets: India PRIMARY (^NSEI equity, GOLDBEES.NS gold, ^INDIAVIX) per graded spec; US as
  out-of-sample robustness (SPY, TLT, GLD, ^VIX).
- Modular src/ package plus one thin driver notebook (structure over single notebook).
- Leak-proofing is the whole point: causal features, train-only standardization inside each
  walk-forward fold, HMM re-fit per fold, CAUSAL decode of test regimes (no whole-block Viterbi),
  1-day execution lag. Asserted by unit tests (done for features/regime/walkforward).
- Regime label convention: canonical integer labels 0..n-1, ALWAYS ascending risk (0 = calmest
  = Bull). REGIME_NAMES_3 = (Bull, Bear, Crisis). Stable across per-fold refits via vol ranking.
- Research-grade differentiators: HMM vs Statistical Jump Model (jumpmodels) comparison on
  persistence, turnover, net-of-cost Sharpe (flagship); FRED macro features; Ledoit-Wolf
  covariance; convex max-Sharpe via Schaible transform; deflated/probabilistic Sharpe plus
  bootstrap CIs; rule-based ablation; optional LLM regime narration (report-only, cannot leak).

## File map
- config/config.yaml: all knobs (universes, dates, windows, HMM, costs, seed, rebalance +
  rebalance_confirm_days). NOTE india.bond is EMPTY (TODO).
- src/regime_shift/config.py: DONE. typed pydantic loader. load_config() returns Config.
- src/regime_shift/data.py: DONE. load_prices (yfinance + pickle cache), load_macro (keyless FRED
  CSV), build_master (log-returns + vix level + causal 1-day-lagged macro; warns and continues if
  FRED unreachable). Master cols: equity_ret[/bond_ret]/gold_ret, vix, optional macro (1-day lagged).
- src/regime_shift/features.py: DONE (phase 2). add_momentum (rolling SUM of equity_ret = log
  momentum, off the return col since master has no price), add_realized_vol (rolling std * sqrt252),
  build_features -> mom_{5,21,63,126}, vol_{5,21,63}, vix, vix_chg, macro passthrough. All causal
  (right-aligned rolling). NO standardization here. Momentum/vol on EQUITY only (ponytail comment).
- src/regime_shift/regime.py: DONE (phase 3). RegimeModel(engine=hmm|jump). fit(X, rank_by, tiebreak)
  -> stable canonical labels via _canonical_order (sort raw states by within-state mean vol asc,
  tiebreak return). decode = whole-seq Viterbi (descriptive overlay ONLY). decode_causal = O(n)
  log-space forward filter off hmmlearn _compute_log_likelihood (leak-proof by construction).
  transition_matrix (remapped), bic; module fns dwell_times, bic_sweep(K=2..5). jump engine is a
  LAZY import (raises clear error, HMM has zero dep on it).
- src/regime_shift/walkforward.py: DONE (phase 4). expanding_walk_forward_splits(n,min_train,
  test_size,step) -> disjoint expanding (train from 0). run_walk_forward(features,cfg,engine,vol_col)
  -> per fold: StandardScaler fit on TRAIN only, transform train+test; RegimeModel refit on scaled
  train ranked by rank_sign*features[rank_col] (default vol_21 ascending); causal decode of
  [train;test] carrying train history, keep test-day labels only. Returns int Series 'regime' over
  OOS dates. Execution lag NOT here (backtest owns it). rank_col/rank_sign DEFINE what "ascending
  risk" means: rank_col="mom_21", rank_sign=-1.0 ranks by trailing return instead of vol. Both are
  train-only and leak-free. NOTE the kwarg was renamed vol_col -> rank_col.
- src/regime_shift/optimize.py: DONE (phase 5). ledoit_wolf_cov, shrink_mu (toward grand mean),
  min_variance_weights, max_sharpe_weights (Schaible: min y'Sy s.t. mu'y=1, y>=0, y<=cap*sum(y);
  w=y/sum(y); falls back to min-var if max(mu)<=0), defensive_weights (min-var + equity hard-capped),
  regime_weights dispatch (0->Bull max-Sharpe, n-1->Crisis defensive, mid->Bear min-var). Long-only,
  budget=1, weight_cap. psd_wrap on shrunk cov. NO turnover penalty (backtest owns churn).
- src/regime_shift/backtest.py: DONE (phase 6, refactored in 7). run_book(rets,dates,decide,cfg) is
  the SHARED engine: decide(t) -> (label, target|None) is called at the close of t and its target
  earns t+1's return; benchmarks.py rides the same engine so costs are identical by construction.
  asset_cols(returns) is public (benchmarks imports it). run_backtest(regimes,returns,cfg,
  confirm_days,mu_shrink) is the regime strategy on top. Sequential loop: weights in force today were decided at YESTERDAY's close
  (regime@close(t) -> weights earn return(t+1)); day 1 is flat by construction. Log returns are
  converted with expm1 before any portfolio sum (weighted sum of logs != log of portfolio).
  Between trades the book DRIFTS (w*(1+r) renormalized), so a non-trade day has exactly 0
  turnover and 0 cost. Trade-day turnover = sum|w_target - w_drifted|, cost = turnover*bps/1e4.
  Cadence from cfg.rebalance: on_regime_change (hysteresis: new label must persist
  rebalance_confirm_days) or monthly. conditional=None -> cfg.conditional_moments: estimate
  mu/Sigma from PAST SAME-LABEL days, falling back to full history below cfg.conditional_min_obs
  (126). conditional=False is the unconditional ablation. Output cols: regime (Int64, traded label), w_<asset>,
  turnover, cost, ret_gross, ret_net, equity_gross, equity_net. mu/Sigma are estimated on ALL
  history up to t (unconditional); the regime picks the OBJECTIVE, not the sample (ponytail note).
- src/regime_shift/metrics.py: DONE (phase 7). Takes SIMPLE returns (book ret_net/ret_gross).
  ann_return (geometric), ann_vol, sharpe(rf annual), sortino(downside dev), max_drawdown (negative),
  calmar, probabilistic_sharpe (Bailey/LdP PSR, per-period SR + skew + kurtosis, benchmark arg is
  ANNUALIZED), expected_max_sharpe(n_trials, trial_sr_std) (Euler-Mascheroni best-of-N under the
  null), deflated_sharpe = PSR vs that threshold, optimal_block_length (Politis-White 2004 automatic
  block: flat-top taper, bandwidth = 2x last significant correlogram lag; ~2.9 days on real US
  strategy returns), bootstrap_ci (Politis-Romano STATIONARY bootstrap, vectorized index
  construction, mean_block=None picks it from the data), summary(book or Series) -> ann_return/ann_vol/
  sharpe/sortino/max_drawdown/calmar/psr (+turnover_ann/cost_drag_ann when given a book).
- src/regime_shift/benchmarks.py: DONE (phase 7). All benchmarks go through backtest.run_book so
  they pay identical costs. static_book(returns,dates,cfg,target,rebalance="monthly"|"never"),
  equal_weight (1/N), sixty_forty (SIXTY_FORTY dict, RENORMALIZED over columns present, so India
  without a bond ticker becomes 100% equity, not 60% invested). vol_rule_regimes(returns,cfg,
  window=21,lookback=252,quantile=0.8) -> causal 0/(n-1) labels from trailing vol vs its own
  trailing quantile: the no-HMM ablation, feed it to run_backtest sliced to the HMM OOS index.
- src/regime_shift/narrate.py: STUB (phase 8). Optional LLM narration (offline-safe, report-only).
- src/regime_shift/plots.py: DONE. REGIME_COLORS (ascending risk), regime_overlay(level, regimes)
  shades each label run up to the NEXT run's start (a one-day flicker would otherwise be a
  zero-width axvspan and render as a white stripe), equity_drawdown(books dict) 2-panel log growth
  + drawdown lines, transition_heatmap(P). All take/return an axis; the caller saves. Descriptive
  only, so a full-sample Viterbi fit is allowed here.
- tests/: test_smoke (2), test_features (2, leak-proof property), test_regime (4, causal+labels+
  transition+dwell), test_walkforward (2, splits+OOS sanity), test_optimize (5, constraints+dispatch),
  test_backtest (3: 1-day lag via flip-the-future-label diff, flat-then-single-entry, zero turnover
  costs nothing + net=gross-cost), test_metrics (8, closed-form ratios + PSR/DSR properties +
  bootstrap brackets, block length tracks persistence), test_benchmarks (4: 1/N, 60/40
  renormalization, monthly trade DATES exact, vol-rule causality via shock-the-future). 33 tests,
  all green. Tests stay synthetic/seeded/offline on purpose; real data lives in the driver run.
- notebooks/real_run.py: the real-data driver. Run from the repo root:
  uv run python notebooks/real_run.py [us|india]. Builds the master from cache, runs the
  walk-forward, scores all five books, prints the table + bootstrap CI + DSR, writes the three
  figures to results/. matplotlib Agg, no display needed.
- notebooks/driver.ipynb: DONE (phase 9). 22 cells, executed clean with 3 embedded figures. Same
  pipeline as real_run.py plus the narrative: data -> causal features -> leak-proof walk-forward ->
  THE label-vs-forward-return diagnostic -> BIC sweep -> books -> deflation -> figures ->
  conclusion. NOTE pre-commit runs nbstripout, so outputs vanish on commit by design; the numbers
  live in README.md and the figures in results/. Regenerate + execute:
  uv run papermill notebooks/driver.ipynb notebooks/driver.ipynb --kernel python3
  (ipykernel was added to the dev extra for this).
- README.md: DONE. Leads with the negative result, both universes' tables, the why-it-loses
  section, the data-quality landmine, and the deflation rationale.
- Full build plan (read this first): C:\Users\Anklesh\.claude\plans\c-users-anklesh-appdata-local-temp-proj-recursive-bentley.md

## Current state
- Phases 0-9 DONE (everything except the optional narrate.py and the optional jumpmodels
  comparison). Phase 0-1 committed (3 commits: b56c652, 72e475d, 999594b). Phases 2-9 IMPLEMENTED
  but NOT COMMITTED (user hold: no commits until the repo name is decided).
- 36 tests green, ruff clean. Env locked (uv.lock, ipykernel added to dev). Nothing pushed.
- Uncommitted working tree:
  - M CLAUDE.md, README.md, pyproject.toml, uv.lock, config/config.yaml,
    src/regime_shift/{config,data,features,optimize,regime,walkforward,backtest,metrics,
    benchmarks,plots}.py
  - ?? tests/test_{features,optimize,regime,walkforward,backtest,metrics,benchmarks,data}.py,
    notebooks/{real_run.py,driver.ipynb}
- REAL DATA IS PULLED AND CACHED (data/cache/, yfinance ok, FRED blocked on this network so the
  master has NO macro cols). US master 2263x4 (equity/bond/gold/vix) 2015-01-02..2023-12-29,
  India 2193x3 (no bond).
- FIRST REAL RESULT (US, walk-forward OOS 2016-07-05..2023-12-29, n=1886, net of 7.5bps):
    hmm_conditional    sharpe 0.542  ann_ret 0.049  maxDD -0.287  turnover 4.19x
    hmm_unconditional  sharpe 0.535  ann_ret 0.048  maxDD -0.274  turnover 2.74x
    vol_rule_ablation  sharpe 0.958  ann_ret 0.098  maxDD -0.219  turnover 3.61x
    60_40              sharpe 0.690  ann_ret 0.075  maxDD -0.276  turnover 0.41x
    equal_weight       sharpe 0.650  ann_ret 0.059  maxDD -0.230  turnover 0.42x
  THE HMM STRATEGY LOSES TO EVERYTHING, including its own no-HMM ablation. Sharpe 95% CI
  (-0.211, 1.263), DSR 0.405 at 10 trials, auto block length 2.9 days. Do not paper over this.
  Root cause is now established: see THE CENTRAL FINDING below. Labels themselves are sane (dwell
  21-27d, transition diagonal 0.96-0.98, overlay nails Feb-2018 / Q4-2018 / COVID / 2022) and the
  book does protect the fast crash (barely dented Mar-2020 while 60/40 took -14%) but fails the
  slow 2022 bear where bonds fell with equities (-0.29, worse than 60/40). Conditional moments buy
  +0.007 Sharpe for +53% turnover: not worth it on this evidence.
- rank_return variant (rank_col=mom_21, rank_sign=-1): sharpe 0.620, ann_ret 0.057, maxDD -0.285,
  turnover 3.77x. Better than rank_vol, still under 60/40.
- Figures written to results/ (gitignored): {us,india}_regime_overlay.png,
  {us,india}_equity_drawdown.png, {us,india}_transition_heatmap.png.
- hmmlearn emits ~500 NumPy-2.5 DeprecationWarnings during fits (internal a_sum.shape=shape); noise,
  not our code, tests still pass.

## DATA-QUALITY LANDMINE (fixed, but read this before trusting any number)
GOLDBEES.NS on Yahoo prints a 100x round trip: log return -4.6065 on 2019-12-19 and +4.6052 on
2019-12-23. Two bad prints in 2193 rows inflated gold's return std from 0.011 to 0.139 and
poisoned every Indian covariance, regime fit and Sharpe. Before the fix India "ran" at 44.5% vol
with sharpe 0.446; after it, 10.2% vol and sharpe 1.215. data.drop_return_outliers now NaNs any
daily |log return| > 0.5 (build_master arg max_abs_return, default 0.5) and warns loudly;
tests/test_data.py pins it, including that a -13% crash day is NOT dropped. US was unaffected
(re-run confirmed identical), so all US numbers below stand.

## THE CENTRAL FINDING (diagnosis complete, do not re-litigate without new evidence)
HMM states here are VOLATILITY states, and volatility states carry no directional information on
US 2016-2023. Evidence, all out-of-sample at the traded 1-day lag:
- Next-day equity by vol-ranked label: L0 +10.9% (vol 8.7, VIX 13), L1 +14.7% (15.6, 19),
  L2 +16.1% (32.2, 28). Vol ordering is perfectly monotone; RETURN ordering is monotone the WRONG
  WAY. De-risking on the crisis label sells the best days, because 2020 and 2022 rebounds are as
  volatile as the crashes.
- The modal label is Bear (841/1886 days) with equity Sharpe 0.96, a perfectly good regime, and
  the stance map routes it to min-variance. That, not Crisis, is where most of the damage is.
- Re-ranking states by trailing return (rank_col="mom_21", rank_sign=-1) barely moves anything:
  sharpe 0.542 -> 0.620, still under 60/40's 0.690, and label 2 is IDENTICAL (same 379 days, same
  +16.1%). Reordering cannot add information the state space does not contain. The state space is
  the problem, not the label map.
- BIC falls monotonically (K=2 39821, 3 34354, 4 31349, 5 29458): the HMM is fitting a fat-tailed
  continuum, not finding discrete states. No BIC support for K=3.
- The 2-line vol-threshold ablation DOES separate direction: L0 +19.7% (Sharpe 1.39) vs L2 -9.6%
  (Sharpe -0.16), only 48.9% label agreement with the HMM. It wins on every metric.
Deflated Sharpe at 4 honest trials: rank_vol 0.630, rank_return 0.706, vol_rule 0.928. Only the
vol rule has a bootstrap CI excluding zero: (0.238, 1.652).
INDIA (primary universe, post data fix, OOS 2016-07-22..2023-12-29 n=1816): hmm_conditional
sharpe 1.215 / hmm_unconditional 1.176 / equal_weight 1.185 / vol_rule 1.136 / 60-40 (=100%
equity, no bond ticker) 0.817. The HMM "wins" by 0.03 sharpe over 1/N for 3.5x the turnover, which
is a rounding error with a cost bill. Every diversified book sits at 10.2% vol and sharpe ~1.2
while all-equity sits at 17% and 0.82: the GOLD SLEEVE is doing the work, not the regime switching.
Sharpe CI (0.446, 1.944), DSR 0.934 at 10 trials.
This IS the report's flagship result. A rigorous negative with a diagnosis beats a tuned positive.
Config default deliberately left at rank_col="vol_21"; do NOT quietly switch it to the variant
that scored 0.08 higher, that is exactly the selection bias the DSR is there to punish.

## Active task
Nothing blocking. Phases 0-9 are done and the story is written up. Open choices, in the order they
matter:
1. DECIDE THE REPO NAME so phases 2-9 can finally be committed (user hold, nothing is committed
   since 999594b).
2. Resolve the India bond ticker (config india.bond is still ""). It is the last real gap in the
   graded universe, and it would let defensive_weights actually defend there.
3. Optional modelling, only with a real hypothesis: give the state space a directional feature
   (drawdown-from-peak, or the sign of mom_126). Momentum features exist but the diag-covariance
   Gaussian latches onto the vol/VIX dimensions. Every new variant increments the trial count in
   deflated_sharpe, and at 4 trials the budget is mostly spent.
4. Optional: jumpmodels (uv add jumpmodels) for the HMM-vs-JM comparison; narrate.py is still a
   stub and is explicitly optional.

## Next steps
1. Repo name, then commit phases 2-9 (ACTIVE, blocked on the user).
2. Resolve India bond proxy (config india.bond empty); pick a Yahoo gilt/bond ETF or duration proxy.
   Now semi-blocking: backtest allocates over whatever *_ret columns exist, so India currently
   runs equity+gold only (defensive_weights has no bond sleeve to hide in). US is the fuller demo.
3. Phase 8 narration (optional); Phase 9 driver notebook + README results.
4. Optional: install jumpmodels (uv add jumpmodels) to light up the flagship HMM-vs-JM comparison.
5. DECIDE REPO NAME, then commit phases 2-7 (user hold on commits until then). Push only on go-ahead.

## How to run
- uv sync --extra dev
- uv run pytest -q ; uv run ruff check .
- Data smoke: uv run python -m regime_shift.data
- Full real run + figures: uv run python notebooks/real_run.py us

## Gotchas
- GateGuard hook (ECC gateguard-fact-force) DENIES the FIRST Write/Edit of a file per session,
  including edits of existing files (not only new-file creation as previously noted). Retry after
  stating facts (importers via Grep, public API, data schema, verbatim instruction). ECC_GATEGUARD=off
  or ECC_DISABLED_HOOKS=pre:edit-write:gateguard-fact-force disables it.
- regime causal decode uses hmmlearn's PRIVATE _compute_log_likelihood (fine on pinned 0.3.3).
  decode() (whole-seq Viterbi) is NOT causal; NEVER use it for the walk-forward test decode.
- max_sharpe needs psd_wrap(cov) (LedoitWolf cov can have tiny negative eigenvalues); Sharpe fallback
  to min-var when no positive shrunk mean.
- jumpmodels NOT installed; engine='jump' raises a clear ImportError. HMM is the graded baseline.
- git add -A once swept in .claude/ plugin sqlite files; .claude/ is now gitignored. Watch stray dirs.
- FRED (fred.stlouisfed.org) may be blocked on some networks; macro degrades gracefully.
- yfinance 1.x returns MultiIndex columns (field, ticker); data.py handles single vs multi ticker.
- India bond ticker empty means India master is equity+gold+vix only until resolved.

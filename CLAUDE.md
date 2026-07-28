# CLAUDE.md - Signals-Before-Storms

## Project
**Signals-Before-Storms**: Macro-Aware Tactical Asset Allocation Engine. Capstone for the Summer
of Quant course. Detect hidden market regimes (Bull, Bear, Crisis) with a Hidden Markov Model,
switch portfolio weights (equity, bond/cash, gold) via convex optimization per regime, validate
leak-proof with an expanding walk-forward, charge transaction costs, benchmark against static
60/40, equal weight and a no-HMM ablation.

**PUBLIC**: https://github.com/DogInfantry/Signals-Before-Storms (Apache-2.0, CI green).
**LIVE SITE**: https://signals-before-storms.vercel.app (Vercel project `signals-before-storms`,
scope `anklesh-s-projects`, GIT-CONNECTED as of 2026-07-26, so **every push to `main` deploys**).
- **`vercel.json` lives at the REPO ROOT, not in `docs/`, and it must stay there.** The project's
  Root Directory is the repo root, so `outputDirectory: "docs"` is the only thing making the site
  serve the right folder. Moving that file back into `docs/` deploys the repository instead, and
  the repo root has no `index.html`, so production becomes a 404.
- **THREE Vercel projects now share this ONE repo, and each reads a DIFFERENT vercel.json. Do not
  consolidate them.** A Vercel project is scoped by its Root Directory and reads the config found
  there, so the three cannot collide and none overwrites another:
  | Project | Root Directory | Framework | Config |
  |---|---|---|---|
  | `signals-before-storms` | repo root | Other (`framework: null`) | `/vercel.json` |
  | `regime-monitor` | `monitor` | Other | `/monitor/vercel.json` |
  | `storm-ledger` | `ledger` | Next.js | `/ledger/vercel.json` |
  Merging these "duplicate" configs into one breaks two of the three deploys. Two guards keep the
  ORIGINAL project safe now that a Next.js app lives in the repo: there is **no `package.json` at
  the repo root**, and the root config pins `"framework": null`. Do not add a root `package.json`.
  Every push to `main` rebuilds ALL THREE projects; that is expected, not a regression.
- Repo topics and homepage URL are set. `docs/data/*.json` revalidates every request, `/img/*`
  caches for a week with revalidation (NOT immutable: two figures changed content without changing
  filename, and immutable meant a returning reader kept the stale one for a year).

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
- **COMPARISONS USE A PAIRED DIFFERENCE TEST, NEVER OVERLAPPING MARGINAL CIs (Phase 11).** Two
  overlapping intervals each say "this book beats zero"; they say NOTHING about the gap between two
  books. `metrics.paired_bootstrap` draws ONE index matrix and applies it to both series, which
  cancels the shared market move and comes out ~3x tighter than the marginals. Result: every book
  on BOTH universes spans zero against both benchmarks, so "indistinguishable from the benchmarks"
  is now earned rather than assumed. On US the vol rule's MARGINAL CI excludes zero but its PAIRED
  CI vs 60/40 is (-0.029, +0.559): it beats zero, it does not beat the benchmark. Do not restate
  the old "only the vol rule excludes zero" as if it were a comparison.
  **LANDMINE: Sharpe is not translation invariant.** Feed `paired_bootstrap` the SAME rf-excess
  series the point estimates use. Passing raw `ret_net` against rf-adjusted point estimates
  produced intervals that did not bracket their own point estimate and gave confident, wrong
  "EXCLUDES 0" verdicts. `tests/test_metrics.py::test_paired_interval_brackets_its_own_point_estimate`
  pins it.
- **EFFECTIVE SAMPLE SIZE (Phase 10, the most load-bearing rigor in the repo). `days` is NOT a
  sample size; `episodes` is.** ALWAYS quote episodes next to days for any regime claim. India
  crisis = 261 days but only **14 episodes**, 3 of them negative, and `ann_ret_ex_largest` (drop
  the longest episode) takes it +18.4% -> **+53.6%**. US crisis = 379 days / **17 episodes**,
  ex-largest +16.1% -> +21.7%, so the backwards return ordering IS robust to episode counting on
  both universes; what did not survive was the jump "directional state" (see the retraction below).
  `regime.label_episodes` is the single run-length implementation (`dwell_times` and
  `plots._blocks` both delegate to it, so there is nothing to drift); `metrics.episode_profile` is
  the table; `plots.episode_bars` the figure.
  Dual CIs are reported per book (return-derived ~2.3d block vs regime-scale ~25d block). They
  differ by only 0.1-0.2 Sharpe and mostly move INWARD, not outward, because longer blocks preserve
  the vol clustering the Sharpe denominator depends on. That was the OPPOSITE of the prediction and
  is documented as measured. Do not "correct" it back to the textbook expectation.

## File map
- `config/config.yaml`: all knobs (universes, dates, windows, HMM, costs, seed, rebalance,
  rebalance_confirm_days, conditional_moments, conditional_min_obs). `india.bond` is deliberately
  EMPTY, `india.cash: LIQUIDBEES.NS` is the defensive sleeve instead (see data quality below).
- `src/regime_shift/config.py`: typed pydantic loader, `load_config() -> Config`.
- `src/regime_shift/data.py`: `load_prices` (yfinance + pickle cache), `load_macro` (keyless FRED
  CSV), `load_credit_proxies` (Yahoo fallback: `-log(credit/duration)` for IG and HY, negated so up
  means wider, plus `y10`; reuses `load_prices`, so it caches the same way),
  `drop_return_outliers` (vendor-error guard, see landmine), `build_master` (log returns +
  vix + causal 1-day-lagged macro; warns and continues if FRED unreachable). **Entry points call
  `build_master` WITHOUT the macro argument on purpose; see Current state.** `_ASSET_ROLES =
  (equity, bond, cash, gold)`. Master cols: `equity_ret[/bond_ret][/cash_ret]/gold_ret`, `vix`.
- `src/regime_shift/features.py`: `add_momentum` (rolling SUM of equity_ret = log momentum),
  `add_realized_vol` (rolling std * sqrt252), `build_features(master, cfg, drawdown=False)` ->
  `mom_{5,21,63,126}`, `vol_{5,21,63}`, `vix`, `vix_chg`, optional `dd_peak`, macro passthrough.
  All causal (right-aligned rolling). NO standardization here. Equity only.
  **`_RETURN_COLS` must name EVERY role in `data._ASSET_ROLES`.** Anything not in it and not `vix`
  is swept up as a macro passthrough, i.e. promoted to a state variable. `cash_ret` was missing
  until 2026-07-24 and silently gave India a 10th feature; see landmine 4.
- `src/regime_shift/regime.py`: `RegimeModel(engine="hmm"|"jump")`. `fit(X, rank_by, tiebreak)` ->
  canonical labels via `_canonical_order` (sorts raw states by within-state mean rank_by ascending;
  PADS to a full permutation and warns if the fit did not occupy every state). `decode` =
  whole-sequence Viterbi (DESCRIPTIVE OVERLAYS ONLY). `decode_causal` = O(n) log-space forward
  filter (HMM) or `predict_online` (jump), leak-proof by construction. `transition_matrix`, `bic`
  (both HMM-only, raise NotImplementedError for jump); module fns `label_episodes` (THE run-length
  implementation, everything else delegates), `dwell_times`, `bic_sweep`.
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
  - `sensitivity_sweep(regimes, returns, cfg, grid)` re-scores ONE knob at a time via
    `cfg.model_copy`, returns a tidy frame with `is_default`. Reports the surface and adopts
    NOTHING, which is what keeps it zero-DSR. Only knobs that leave the labels alone belong here.
  - Log returns are converted with `expm1` before any portfolio sum (a weighted sum of logs is
    not the log of the portfolio). Non-trade days have EXACTLY zero turnover and zero cost.
  - Output cols: `regime` (Int64), `w_<asset>`, `turnover`, `cost`, `ret_gross`, `ret_net`,
    `equity_gross`, `equity_net`.
- `src/regime_shift/metrics.py`: takes SIMPLE returns. `ann_return` (geometric), `ann_vol`,
  `sharpe(rf)`, `sortino`, `max_drawdown` (negative), `calmar`, `probabilistic_sharpe` (Bailey/
  Lopez de Prado PSR; benchmark arg is ANNUALIZED), `expected_max_sharpe(n_trials, trial_sr_std)`,
  `paired_bootstrap` (CI of stat(a)-stat(b) on JOINTLY resampled dates; pass excess returns),
  `subperiod_summary(books, splits)` (scorecard per block, carries `days` because blocks are short),
  `deflated_sharpe`, `optimal_block_length` (Politis-White 2004; ~2.9 days on real US returns),
  `bootstrap_ci` (Politis-Romano STATIONARY bootstrap, vectorized; `mean_block=None` reads it off
  the data), `label_profile(labels, master)` (next-day return/vol/Sharpe/VIX per label, THE central
  diagnostic; lives here so the driver, the notebook and `plots.label_profile_bars` share one
  implementation), `summary(book, col, periods, rf)`. **Pass `rf` whenever a cash-like asset
  exists** or defensive books get a free Sharpe for holding cash.
- `src/regime_shift/benchmarks.py`: all routed through `run_book`. `static_book(..., target,
  rebalance="monthly"|"never")`, `equal_weight`, `sixty_forty_target(cols)` (resolves the 40% leg:
  `bond_ret` if present, else `cash_ret`; call it to LABEL the book honestly), `sixty_forty`,
  `vol_rule_regimes(returns, cfg, window, lookback, quantile)` -> causal 0/(n-1) labels, the no-HMM
  ablation. Feed the ablation to `run_backtest` sliced to the HMM OOS index.
- `src/regime_shift/plots.py`: `REGIME_COLORS`, `STRESS_SPANS` (COVID + 2022, named from memory not
  read off the data, so shading them is a real out-of-model check). Ten helpers: `regime_overlay`
  (shades each run up to the NEXT run's start, else a one-day flicker is a zero-width axvspan and
  renders as a white stripe), `equity_drawdown(books)`, `transition_heatmap(P)`, `return_panel`
  (R2: raw returns + log-count marginals), `feature_sanity` (R6: vol_21/vix with stress shaded),
  `gross_vs_net` (C4 visual), `weight_stack` (regime ribbon ABOVE the stack so it never hides a
  weight), `label_profile_bars`, `bic_curve`, `sharpe_forest`, `episode_bars`, `regime_weight_heatmap`,
  `rolling_sharpe`, `sensitivity_panel`, `paired_forest` (Sharpe DIFFERENCE vs one benchmark with
  its paired interval, zero marked: a different question from `sharpe_forest`, which only asks
  whether a book beats zero), and `story_panel` (the 2x2 composite that is the README hero:
  label profile, episode bars, paired forest, drawdown comparison; returns a FIGURE, not an axis,
  so the caller saves it directly). All the rest take/return an axis (or an array
  of them); caller saves. `real_run.save()` handles either shape.
- `src/regime_shift/style.py`: THE single source of chart style. `use_house_style()` sets rcParams
  and is called at `plots.py` import time, so importing plots is enough. Exports `REGIME_RAMP`,
  `SERIES_A`/`SERIES_B`, ink/surface constants, and helpers `pct_axis`, `callout`, `bar_labels`,
  `subtitle`. **Palettes here were validated by a contrast/CVD script, not chosen by eye**, which
  caught a real defect in the previously shipped palette: the Bear amber `#f9a825` sat at 1.92:1
  contrast (floor 3:1) and green/amber/red separates by only ~3 CVD units where 8 is the floor.
  Regimes now use a LIGHTNESS RAMP because they are ordinal; that encodes the ordering and survives
  colour blindness. `plots.REGIME_COLORS` is an alias of `REGIME_RAMP`, so nothing downstream broke.
  If you add a palette, validate it rather than picking hexes.
- `src/regime_shift/narrate.py`: STUB. Optional LLM narration, report-only. Never implemented.
- `tools/validate_palette.py`: the contrast / CVD / hue validator behind `tests/test_style.py`.
- `tools/export_site_data.py`: `uv run python tools/export_site_data.py [india|us|all]` ->
  `docs/data/<market>.json`. Re-runs the pipeline and serializes curves, drawdowns, run-length
  regime spans, both scorecards, deflation, paired differences, label and episode profiles, the
  transition matrix and mean weights per regime. Curves are strided WEEKLY for payload size; every
  statistic is still computed daily. **Re-run it after anything that moves a number**, or the site
  and the README disagree.
- `tests/` (67 total, all green, synthetic/seeded/offline on purpose): `test_smoke` 2,
  `test_style` (palette floors), `test_features` 3 (the fixture carries ALL FOUR asset roles,
  asserts no `*_ret` reaches the feature matrix, and pins the 9-column model matrix against macro
  widening it), `test_regime` 6 (causal decode, canonical labels, transition, dwell, jump
  engine via importorskip, label_episodes run counting incl. leading/trailing single-day runs), `test_walkforward` 2, `test_optimize` 5, `test_backtest` 7 (1-day lag
  by flipping a future label, flat-then-entry, conditional moments + fallback, target_vol,
  zero-turnover-is-free), `test_metrics` 13 (episode_profile ex-largest, paired pairing + CI brackets its point estimate, subperiod partition), `test_benchmarks` 6 (incl. cash sleeve and the 60/40
  cash-leg fallback), `test_data` 3.
- `notebooks/real_run.py`: the real-data driver. `uv run python notebooks/real_run.py [india|us]`,
  **defaulting to india**. Builds the model master MACRO-FREE, then loads macro separately (FRED
  first, Yahoo proxies on failure) and PRINTS which leg answered, because the module silences
  warnings so a warning alone would be invisible. Scores 8 books, prints the label tables, BOTH
  gross and net scorecards, the deflation table and the two-episode spread comparison; writes 17
  figures to `results/`. matplotlib Agg, no display needed.
- `notebooks/driver.ipynb`: 62 cells, India-primary (`MARKET = "india"` in the config cell),
  executes clean with 0 errors, all figures post-`style.py`, a US robustness section and a
  section 10 macro diagnostic. Threads `rf` into every `summary` call. The `story_panel`
  composite in section 7, the same hero the README leads with; the paired-bootstrap cell collects
  `paired_vs[bench][name] = (d, lo, hi)` so the composite can be built. Regenerate:
  `uv run papermill notebooks/driver.ipynb notebooks/driver.ipynb --kernel python3` (~5 min).
  Generator script is NOT in the repo; durable copy is the memory-dir `make_nb.py` (see Gotchas).
- `README.md`: leads with the split result (volatility states confirmed on both universes; India
  wins maxDD/Calmar, US loses outright), both scorecards gross and net with sortino and calmar,
  why-it-loses, the failed rescues, the figure inventory, data quality, deflation rationale,
  attribution terms.
- `docs/`: the deployed static site, Vercel preset `Other` with Root Directory `docs`.
  `index.html` is the interactive panel (748 words), `story.html` the full research log (2,684),
  `site.js` the hand-built SVG charts, `style.css` the shared visual world, `data/*.json` the
  exported results, `img/` the committed figures. No build step and no external request.
- Build plan: kept outside the repo in the local Claude Code plans dir, deliberately not
  fetchable from a clone. README + this file carry everything needed to resume.

## Current state
- **Spec-adherence pass landed 2026-07-24. Verify `git status` before assuming anything is pushed.**
- 67 tests green, ruff clean. `uv sync` alone gives a working dev env; `uv sync --extra jump` adds
  the second regime engine.
- Real data pulled and cached in `data/cache/`. yfinance fine; **FRED is still blocked from Python
  on this network** (re-probed 2026-07-26: ReadTimeout at 25s from `requests`, even though `curl`
  through a different path gets 200; DBnomics does NOT mirror the FRED provider, measured, so it is
  not a fallback). Macro now lands via `data.load_credit_proxies` (Yahoo LQD/HYG/IEF/^TNX) and both
  entry points print which leg answered.
- **MACRO IS DIAGNOSTIC ONLY AND THE MODEL MASTER IS BUILT MACRO-FREE ON PURPOSE (2026-07-26).**
  `build_features` promotes any column that is not an asset return and not `vix` into a state
  variable, so the old `build_master(..., cfg.macro_fred_series)` calls in both entry points were a
  loaded gun: the day macro landed, every published number would have moved and the DSR trial count
  would have been wrong. Entry points now build the model master WITHOUT macro and load macro
  separately.
  `tests/test_features.py::test_macro_widens_the_matrix_so_the_model_master_must_exclude_it` pins
  both the 9-column matrix and the widening mechanism. Verified by re-running BOTH universes after
  the change: every number matches the published tables below.
  US master 2263x4 (2015-01-02..2023-12-29), India master 2191x4 (equity/cash/gold/vix).
  Feature matrices are 9 columns on BOTH universes now (was 10 on India, see landmine 4).
- 34 figures in `results/` (gitignored): `{india,us}_{story,returns,feature_sanity,label_profile,episode_bars,paired_forest,
  weight_stack,gross_vs_net,sharpe_forest,bic_curve,regime_overlay,equity_drawdown,
  transition_heatmap,regime_weights,rolling_sharpe,sensitivity,macro_spread}.png`. That is 17 per
  universe; `macro_spread` is written only when a macro leg answers.
  Six of them (`story,label_profile,episode_bars,paired_forest,regime_weights,sensitivity`) ALSO
  write an `.svg`, listed in `real_run.SITE_FIGURES`, because those are what `docs/` embeds and
  vector text stays sharp on a phone. `regime_overlay` and `equity_drawdown` are deliberately
  raster-only: several thousand points per series made the SVG 590 kB against a 224 kB PNG.
  So `results/` holds 32 PNG + 12 SVG, and `docs/img/` holds 9 files. The notebook's embedded
  copies are what a reader without the repo sees.
- Phases 0-9 done, three follow-up extensions, plus the spec-adherence pass. Only `narrate.py`
  remains a stub (optional).

### India (PRIMARY, OOS 2016-07-22..2023-12-29, n=1814, Sharpe vs rf=3.79% that cash actually paid)
```
                    net   gross  sortino   maxDD  calmar   turn    DSR  CI
hmm_drawdown_feat  0.877  0.896   1.291   -0.064  1.169   0.99x  0.805  ( 0.096, 1.605)
vol_rule_ablation  0.848  0.863   1.244   -0.065  1.165   0.88x  0.783  ( 0.082, 1.589)
jump_regime        0.829  0.833   1.204   -0.073  1.038   0.24x  0.767  ( 0.033, 1.590)
hmm_conditional    0.824  0.841   1.211   -0.062  1.161   0.87x  0.764  ( 0.050, 1.558)
hmm_vol_targeted   0.824  0.841   1.211   -0.062  1.161   0.87x  0.764  ( 0.050, 1.558)
equal_weight       0.815  0.819   1.167   -0.152  0.625   0.41x  0.752  ( 0.070, 1.558)
hmm_unconditional  0.748  0.758   1.097   -0.062  1.103   0.50x  0.697  ( 0.011, 1.469)
60_40 (eq/cash)    0.604  0.607   0.827   -0.237  0.413   0.36x  0.552  (-0.155, 1.436)
```
### US (robustness, OOS 2016-07-05..2023-12-29, n=1886, rf=0, UNCHANGED by the 2026-07-24 fixes)
```
                    net   gross   maxDD  calmar   turn    DSR  CI
vol_rule_ablation  0.958  0.984  -0.219  0.446   3.61x  0.863  ( 0.238, 1.652)
60_40              0.690  0.693  -0.276  0.273   0.41x  0.643  (-0.023, 1.422)
jump_regime        0.682  0.693  -0.251  0.262   1.46x  0.636  (-0.092, 1.399)
equal_weight       0.650  0.653  -0.230  0.258   0.42x  0.602  (-0.086, 1.382)
hmm_drawdown_feat  0.590  0.620  -0.280  0.191   3.88x  0.538  (-0.128, 1.343)
hmm_vol_targeted   0.562  0.595  -0.273  0.182   4.10x  0.508  (-0.184, 1.266)
hmm_conditional    0.542  0.575  -0.287  0.170   4.19x  0.486  (-0.211, 1.263)
hmm_unconditional  0.535  0.556  -0.274  0.174   2.74x  0.478  (-0.168, 1.252)
```
**THE ORDERINGS DIFFER. Do NOT restate "same ordering as US"; that claim was true only of the
pre-fix contaminated India run and is now false.** On India the HMM books beat both benchmarks
decisively on maxDD (-6.2% vs -15.2% vs -23.7%) and Calmar (1.161 vs 0.625 vs 0.413) while sitting
mid-pack on Sharpe. On US they lose on every metric. Two of the three metrics the brief names
favour the strategy on the graded universe. Every India CI except 60/40 excludes zero; on US only
the vol rule does.

## THE CENTRAL FINDING (diagnosis complete, do not re-litigate without new evidence)
HMM states here are VOLATILITY states, and volatility states carry no directional information.
Evidence, all out-of-sample at the traded 1-day lag:
- Next-day equity by vol-ranked label. US: L0 +10.9% (vol 8.7), L1 +14.7% (15.6), L2 +16.1%
  (32.2). India: L0 +10.2% (11.2), L1 +15.0% (14.9), L2 +18.4% (31.7). Vol ordering perfectly
  monotone on BOTH; RETURN ordering monotone the WRONG WAY on BOTH. De-risking on the crisis label
  sells the best days: 2020 and 2022 rebounds are as violent as the crashes that preceded them.
- The modal label is Bear (US 841/1886 days) with equity Sharpe 0.96, a perfectly good regime,
  routed by the stance map to min-variance. That, not Crisis, is where most of the damage is.
- The weight-stack figure shows equity pinned under 25% and mostly 10-20%. The book is not too
  risky, it is far too de-risked, which is also why target_vol barely binds.
- The 2-line vol-threshold ablation DOES separate direction on US: L0 +19.7% (Sharpe 1.39) vs L2
  -9.6% (Sharpe -0.16), only 48.9% label agreement with the HMM.

**BUT the picture is NOT uniformly negative, and two sub-claims were REVERSED on 2026-07-24 when
the `cash_ret` contamination was fixed. Do not restore the old blanket wording:**
- **BIC now SUPPORTS K=3 on India.** Marginal fit per added state, India: 2->3 6256, 3->4 **392**,
  4->5 3125, a genuine elbow at three. US: 5467 / 3005 / 1891, steady decline, no elbow. The old
  "no BIC support for K=3" is a US-only fact. India BIC {2:38438, 3:32182, 4:31790, 5:28665}.
- **The Jump Model's India crisis label is NOT directional. THIS LEAD IS CLOSED, DO NOT REOPEN.**
  It reads -17.1% ann over 94 days, which looks like the only negative-return state in the project.
  It is **2 EPISODES**: 2020-03-06..2020-06-12 (64d, -10.70%) and 2018-10-11..2018-11-26 (30d,
  **+4.41%**). Ex-COVID the label runs **+30.17%** ann over 40 days, the same broken ordering as
  everything else. n_effective = 1, not 94. Worse, `pd.crosstab(hmm, jump)` shows all 94 of those
  days sit INSIDE the HMM's own crisis label, so the jump partition is a strict SUBSET, not a
  different state space. "Two estimators, same broken ordering" holds on BOTH universes after all.
  This was briefly written up as a live lead on 2026-07-24 and retracted the same day by an episode
  count; the retraction is documented in the README rather than quietly dropped.
- **On India the HMM wins on maxDD and Calmar** (see the headline block). The brief names Sharpe,
  max drawdown AND Calmar; two of the three favour the strategy on the graded universe.

**FOUR RESCUE ATTEMPTS, ALL FAILED, ALL THE SAME WAY:**
1. **Re-rank by return** (`rank_col="mom_21", rank_sign=-1`): 0.542 -> 0.620, still under 60/40,
   and label 2 came out IDENTICAL (same 379 days, same +16.1%). Reordering cannot add information
   the state space does not contain.
2. **Jump Model** (the flagship): does exactly what it advertises. US dwell 27d -> 194d, turnover
   4.19x -> 1.46x, Sharpe -> 0.682. Agrees with the HMM 58.6% (US) / 57.5% (India), so it is a
   genuinely different partition. On US its crisis label STILL has the highest forward return
   (+20.0%, 106 days), which is what points at the STATE SPACE rather than the HMM. On India it
   does NOT: -17.1%, 94 days (see the reversal note above). Scores 0.829 on India regardless.
3. **Volatility targeting** (`target_vol=0.10`): 0.542 -> 0.562 US, bit-identical on India (0.824
   either way). It barely binds, because min-var already pins the book at 9.6% (US) / 3.9% (India)
   vol. The strategy is not taking too much risk, it is taking too little and forfeiting return.
4. **Drawdown feature** (`build_features(drawdown=True)`): PRE-REGISTERED criterion was "crisis
   label forward return must turn negative". US +16.1% -> +17.6%; India +18.4% -> **+29.7%**.
   FAILED on its own terms on BOTH universes. It now TOPS the India Sharpe table at 0.877, and is
   still explicitly NOT counted as a win and NOT adopted as the default. Do not re-litigate via
   the Sharpe: that is exactly the situation the pre-registration exists to handle.

A rigorous negative with a diagnosis beats a tuned positive, and the India drawdown/Calmar win is
reported as what it is: a real effect on two of the three named metrics, on one universe only.
Config default deliberately stays `rank_col="vol_21"` with `drawdown=False`; do NOT quietly switch
to a variant that scored higher, that is precisely the selection bias the DSR exists to punish.

## DATA-QUALITY LANDMINES (all fixed, read before trusting any number)
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
4. **`cash_ret` was silently a FEATURE on India until 2026-07-24.** `features._RETURN_COLS` listed
   only equity/bond/gold, and anything not in that tuple and not `vix` is swept up as a macro
   passthrough. India therefore fitted 10 features where the US fitted 9. Not a leak (`cash_ret[t]`
   is known at the close of t) but it broke the like-for-like claim AND depressed every Indian HMM
   score: fixing it moved hmm_conditional 0.744 -> 0.824 and hmm_drawdown 0.759 -> 0.877. Any new
   asset role added to `data._ASSET_ROLES` MUST also be added to `_RETURN_COLS`;
   `tests/test_features.py` now asserts no `*_ret` column can reach the feature matrix.
5. **India's 60/40 was 100% NIFTY until 2026-07-24.** `SIXTY_FORTY` names `bond_ret`, India has
   none, and `_fixed_vector` renormalized [0.6,0,0] to [1,0,0]. The strategy was being judged
   against a pure-equity book at 17.0% vol and -38.4% maxDD. `benchmarks.sixty_forty_target` now
   routes the 40% to `cash_ret` when there is no bond sleeve (10.0% vol, -23.7% maxDD). This is a
   benchmark change, NOT a searched variant, so the DSR trial count stays at 7.

## Active task
**Nothing in flight.** The visual-integrity pass, the macro leg and the interactive site are all
committed on `main`. The worktree branch `claude/sleepy-villani-42671c` was fast-forward merged
into `main` on 2026-07-26 and its worktree removed (the directory could not be deleted, permission
denied, but git no longer tracks it: `git worktree list` shows only the main checkout).
**NOTHING IS PUSHED.** `main` is many commits ahead of `origin/main` and needs an explicit
go-ahead, as do the repo topics.

Landed 2026-07-26:
- `cef41cb` macro leg: `load_credit_proxies`, macro-free model master, the widening-guard test.
- `3df73b9` interactive site: `tools/export_site_data.py`, `docs/data/*.json`, `docs/site.js`,
  rebuilt `docs/index.html`, narrative moved to `docs/story.html`, CSS palette synced to the
  validated ramp.

Earlier, on the now-merged branch:
- `b022350` Phase 1: corrected claims the repo's own tables contradict.
- `3bdd4f8` recorded the pass state here.
- `54e4daa` Phase 2: `tools/validate_palette.py` + `tests/test_style.py`. See the palette section
  below, which is now the load-bearing part.
- `7bbbdda` Phase 3: countable `episode_bars`, `DISPLAY_NAMES`, horizontal drawdown quadrant,
  standalone `paired_forest`, SVG output for site figures.
- `e892f81` Phase 4: page rebuilt, three sections cut, rescues reframed, SVG plates, mobile stack.

**THE PALETTE IS NOW TESTED, AND THE TEST CORRECTED TWO CLAIMS THIS REPO WAS MAKING.**
`tools/validate_palette.py` enforces three floors over `style.PALETTES`, which now carries an
ENCODING CHANNEL per group (`hue` or `lightness`) because that decides which floor applies:
contrast >= 3:1 vs SURFACE (every colour), CIE76 dE >= 8 after protan/deutan simulation (every
pair), hue separation >= 90 degrees (pairs in a `hue` palette only).
1. **The shipped Bull gold `#e8b84b` measured 1.80:1, WORSE than the 1.92:1 amber the docstring
   condemned.** Ramp is now `#b8860b/#9e4310/#6b1210` at 3.17 / 6.27 / 11.90:1, worst pair dE 23.4.
2. **The "~3 CVD units" claim in `style.py` AND `README.md` DOES NOT REPRODUCE. Do not restore it.**
   The old green/amber/red triad measures worst pair **17.2 dE**, comfortably clear, because those
   colours differ in LIGHTNESS. The real defect is invisible to dE: after simulation the triad
   collapses to ONE HUE, pairs **0.6 / 1.1 / 1.4 degrees** apart. Hence the hue floor. Sign is now
   blue vs orange (**166.6 deg**) instead of green vs red (**1.1 deg**).
`GOOD`/`BAD` are DELETED, so there is no exemption list. `plots.py` has zero hardcoded colours.

**HARD CONSTRAINT HELD: no published number moved.** Verified by A/B, stashing the changes and
re-running: identical output. NOTE this also revealed that CLAUDE.md's India table lists
hmm_unconditional CI `( 0.011, 1.469)` / DSR 0.697 while the code produces `( 0.007, 1.469)` /
DSR 0.698, **on the pre-change code too**. That is pre-existing doc staleness, not a regression.

**Notebook re-rendered against the new figures** (58 cells, 0 errors, 15 embedded figures,
verified by parsing the ipynb JSON). Nothing is in flight, tree clean, 7 commits ahead of `main`
and UNPUSHED.

## THE SITE, and the defect that was fixed on 2026-07-26

**DONE. `docs/index.html` was 2,826 words (12.8 min) against `PRODUCT.md`'s "under a minute, often
on a phone" brief, a ~13x overshoot. It is now 748 words, 177 of them before the first live
chart.** The fix was NOT deletion and NOT `<details>`: the prose moved intact to `docs/story.html`
and the landing page was rebuilt as an INSTRUMENT PANEL over real exported results.

- `tools/export_site_data.py` -> `docs/data/{india,us}.json` (74 kB / 78 kB), weekly-strided curves
  but DAILY statistics, written by the SAME functions that print the scorecard, so the page cannot
  drift from the README. Re-run it after any change that moves a number.
- `docs/site.js` draws hand-built SVG: equity curves with regime bands and a hover readout,
  drawdowns, label-profile bars, a paired forest, and a sortable scorecard. Toggles for 8 books,
  gross/net, India/US, and which benchmark the paired test runs against. No framework, no build
  step, no external request, so the Vercel preset stays `Other` with root `docs`.
- Series colours reuse the two VALIDATED hues plus two neutrals, each solid and dashed. Do not add
  a categorical palette for this without running `tools/validate_palette.py`.
- `docs/style.css` carried the OLD FAILED ramp (`#e8b84b/#d2691e/#8f1d14`) until now; it is synced
  to `#b8860b/#9e4310/#6b1210`. `--good`/`--bad` are aliases of the validated pair, kept only
  because `story.html` marks up sign in several places.
- **`fetch` does not work on `file://`.** Serve it: `python -m http.server --directory docs`.
  `.claude/launch.json` has a `site` config on port 4321 (gitignored, does not ship).
- Verified at 375px and desktop, light and dark: no horizontal overflow, contrast 4.25:1 and up in
  dark, every interaction re-renders, and the four hero tiles match the published India table
  (-6.2%, 1.16, 0.82, +0.22 spanning zero).

To re-measure the word count, do not eyeball it:

```
uv run python -c "import re,pathlib; s=pathlib.Path('docs/index.html').read_text(encoding='utf-8'); b=s[s.index('<body'):]; t=re.sub(r'<[^>]+>',' ',re.sub(r'<script.*?</script>|<style.*?</style>','',b,flags=re.S)); w=len(re.sub(r'\s+',' ',t).split()); print(w,'words,',round(w/220,1),'min')"
```

This is the SAME defect class as everything else this repo has been fixing: a claim the artifact
disproves. PRODUCT.md declares a sub-minute reader; index.html serves an essay. The user has now
said so twice, in their words: the deploy "should be beautiful, elegant, great and not just direct
pasting of pngs and jpegs", and the output is "too texty and text heavy".

Phase 4 (`e892f81`) genuinely improved the page (cut 3 sections, killed the raw-PNG links, SVG
plates, mobile stack, reframed the rescue stamps) but it TRIMMED a longform log rather than
rethinking the form. 283 words per image across 9 sections, 6 tables and 10 images. The structure
is still "read my essay", and that is what has to change.

**The rigor was NOT deleted to hit the word count.** The retraction, the pre-registered criteria,
the paired test and the episode counting ARE the deliverable and are what make this hireable. They
all still exist, in `story.html`, linked from the masthead and from the body. If a future session
trims further, trim `story.html` last.

## Next steps
1. **DONE 2026-07-26: the notebook is regenerated against the macro section and the figures.**
   Kept here as the regeneration recipe, not as an open task. Two commands, the first only if the
   generator changed:
   ```
   uv run python "C:/Users/Anklesh/.claude/projects/C--Users-Anklesh-Documents-Claude-Code-Summer-Quant/memory/make_nb.py"
   uv run papermill notebooks/driver.ipynb notebooks/driver.ipynb --kernel python3
   ```
   Verify 0 errors by parsing the ipynb JSON, not by eye. The generator gained a section 10 (the
   macro leg) on 2026-07-26, and its data cell no longer passes macro to `build_master`.
   **LANDMINE: the notebook has no `plt` in scope.** End a plotting cell with the axis, not
   `plt.show()`; that cost one full papermill run.
   **The generator is NOT in the repo by design; the durable copy is the memory-dir path above.**
2. **GitHub repo topics are still empty**, which is the largest remaining discoverability gap.
   Outward-facing, so it needs an explicit go-ahead:
   ```
   gh repo edit DogInfantry/Signals-Before-Storms --add-topic quantitative-finance,hidden-markov-model,regime-detection,asset-allocation,backtesting,python,cvxpy,hmmlearn,walk-forward-validation,portfolio-optimization
   ```
3. **The research is finished and stopping there is legitimate**: the deliverable is a rigorous
   negative result, diagnosed, with its own retraction documented. Phases 0-11 plus the four-phase
   visual pass are done. What remains is presentation (step 0) and outward-facing publication.
4. Phase 11 flagged ONE caveat worth remembering: `weight_cap=0.6` and `rebalance_confirm_days=3`
   are each at or near a local Sharpe optimum in the sweep. Both were fixed before any result was
   computed and neither was re-chosen, and the README says so plainly rather than hiding it. If a
   future session ever changes a default, it owes a DSR trial.
5. Phase 10 is DONE. Its lesson generalizes: before believing any regime result, count episodes
   and drop the largest. That check retracted this project's own apparent discovery.
6. Beyond that the evidence still points at a **directional state variable**, and as of 2026-07-26
   the data for one is CACHED AND PLOTTED, just not fitted. `load_credit_proxies` gives a signed
   credit spread that separates the COVID crash (+0.284) from the 2022 rates selloff (-0.025, the
   other way) where realized volatility rises in both. Making it a feature is trial 8 and it would
   move every published number, so it needs an explicit decision, not a drive-by. Market breadth,
   earnings revisions and positioning are the other candidates. NOTE the DSR budget is nearly
   spent: at 7 trials any new variant needs a materially larger raw Sharpe just to hold its ground.
7. **CONSIDERED AND DECLINED on 2026-07-24. Not novel, do not propose as new.** Both were weighed
   against the DSR budget (7 trials spent) and the user chose rigor-only:
   - *Stance-map test*: if states predict variance and not direction, the correct use is SIZING,
     not DE-RISKING. Replace the discrete Bull/Bear/Crisis map with inverse-variance scaling of a
     fixed strategic portfolio. This is the strongest remaining hypothesis, because India label 1
     carries the highest Sharpe of any label (1.01, 731 days) and is routed to min-var. Would be
     trial 8.
   - *Signed-feature test*: semivariance ratio and rolling realized skew, which unlike volatility
     are asymmetric in sign, so they can in principle tell a crash from a rebound. Derivable from
     cached data, needs no FRED. Would be trial 9.
8. `narrate.py` is still a stub, explicitly optional, lowest research value of anything left.
9. India still has no true duration sleeve. Revisit only if a better vendor than Yahoo appears.
10. Nice-to-have polish: `uv run pre-commit install` (configured but NOT installed, so nbstripout
   never runs and the committed notebook keeps its outputs, which is what you want for a portfolio
   repo, since `results/` is gitignored and the embedded figures are all a reader gets).

## How to run
```
uv sync --extra jump          # dev group installs by default
uv run pytest -q              # 67 tests
uv run ruff check .
uv run python -m regime_shift.data                 # data smoke (network)
uv run python notebooks/real_run.py india          # PRIMARY: full run + 16 figures
uv run python notebooks/real_run.py us             # robustness; must stay bit-identical
uv run papermill notebooks/driver.ipynb notebooks/driver.ipynb --kernel python3
```

## Gotchas
- **YOU MAY BE IN A WORKTREE, NOT THE MAIN CHECKOUT.** As of 2026-07-25 the live work is in
  `.claude/worktrees/sleepy-villani-42671c` on branch `claude/sleepy-villani-42671c`. Edits made
  there do NOT appear in `C:\Users\Anklesh\Documents\Claude_Code\Summer_Quant\README.md` until the
  branch is merged. Run `git branch --show-current` before assuming which copy you are editing.
- **A FIGURE IS A CLAIM. Look at the PNG before believing what the code says about it.** Both
  defects found on 2026-07-25 were invisible in the source and obvious in the image: `episode_bars`
  asserts "14 episodes" in its own subtitle while rendering about 10 countable bars, and three
  figures encode sign green-vs-red in a project whose style module documents that exact pair as
  colour-blind-hostile. Reading `plots.py` would never have caught either. The Read tool renders
  PNGs; use it.
- **The same defect class keeps recurring: a confident claim the repo's own artifacts disprove.**
  Three instances so far. The README said "loses on every metric" above a table showing otherwise.
  The README said "does not beat on Sharpe" above a table showing 0.824 against 0.815. `style.py`
  advertises a validated palette while shipping the pair it warns about. When writing any
  superlative here, open the table or the image it summarises.
- **`notebooks/driver.ipynb` is GENERATED, and the generator is not in the repo.** Durable copy:
  `~/.claude/projects/C--Users-Anklesh-Documents-Claude-Code-Summer-Quant/memory/make_nb.py`. It was
  originally written to a SESSION-scoped scratchpad, which a new session cannot reach, so it was
  copied to the memory dir on 2026-07-25. Edit the notebook in place with NotebookEdit for prose
  (that preserves embedded figures), or regenerate from the script and re-run papermill (that wipes
  and rebuilds every output, ~5 min). Editing the notebook without also editing the generator means
  the next regeneration silently reverts your change.
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
- FRED (fred.stlouisfed.org) is blocked from Python on this network: `requests` times out at 25s
  while `curl` through a different path returns 200, so do not trust a curl probe as evidence that
  `load_macro` will work. DBnomics does NOT carry the FRED provider (`Could not find storage
  directory for provider 'FRED'`), so it is not a mirror. Both entry points fall back to
  `load_credit_proxies` on Yahoo and print which leg answered.
- yfinance 1.x returns MultiIndex columns (field, ticker); `data.py` handles single vs multi.
- `git add -A` once swept in `.claude/` plugin sqlite files; `.claude/` is gitignored now. Watch
  for stray dirs before any commit.

# CLAUDE.md - Regime-Shift

## Project
Regime-Shift: Macro-Aware Tactical Asset Allocation Engine. Capstone for the Summer of Quant
course. Detect hidden market regimes (Bull, Bear, Crisis) with a Hidden Markov Model, switch
portfolio weights (equities, bonds, gold) via convex optimization per regime, validate
leak-proof with an expanding walk-forward, charge transaction costs, benchmark against static
60/40 and equal-weight.

Stack: Python 3.11+ (env resolved to 3.13), uv-managed. numpy 2.5, pandas 3.0, scipy,
matplotlib, scikit-learn 1.9, hmmlearn 0.3.3, cvxpy 1.9.2, yfinance 1.5.1 (+ curl_cffi),
keyless FRED, pydantic, pyyaml. Optional extras: jumpmodels, PyPortfolioOpt, skfolio,
quantstats, arch.

## Standing user rules (do not violate)
- NEVER add Claude or any AI as contributor or Co-Authored-By in commits, PRs, or repo. Plain commits.
- NO em dashes or en dashes anywhere (code, docs, prose, commits). Use hyphens, commas, or parentheses.

## Architecture and key decisions
- Two markets: India PRIMARY (^NSEI equity, GOLDBEES.NS gold, ^INDIAVIX) per graded spec; US as
  out-of-sample robustness (SPY, TLT, GLD, ^VIX).
- Modular src/ package plus one thin driver notebook (structure over single notebook).
- Leak-proofing is the whole point: causal features, train-only standardization inside each
  walk-forward fold, HMM re-fit per fold, CAUSAL decode of test regimes (no whole-block Viterbi),
  1-day execution lag. To be asserted by unit tests.
- Research-grade differentiators: HMM vs Statistical Jump Model (jumpmodels) comparison on
  persistence, turnover, net-of-cost Sharpe (flagship); FRED macro features; Ledoit-Wolf
  covariance; convex max-Sharpe via Schaible transform; deflated/probabilistic Sharpe plus
  bootstrap CIs; rule-based ablation; optional LLM regime narration (report-only, cannot leak).

## File map
- config/config.yaml: all knobs (universes, dates, windows, HMM, costs, seed). NOTE india.bond is EMPTY (TODO).
- src/regime_shift/config.py: typed pydantic loader. load_config() returns Config.
- src/regime_shift/data.py: DONE. load_prices (yfinance + pickle cache), load_macro (keyless FRED
  CSV), build_master (log-returns + vix level + causal 1-day-lagged macro; warns and continues if
  FRED is unreachable).
- src/regime_shift/features.py: STUB (phase 2). Momentum, realized vol, VIX, macro; all causal.
- src/regime_shift/regime.py: STUB (phase 3). GaussianHMM + jumpmodels behind one fit/decode
  interface; stable label map (sort by vol, tie-break return, or Hungarian); causal decode; BIC/dwell.
- src/regime_shift/walkforward.py: STUB (phase 4). Expanding splits, train-only scaling, orchestration.
- src/regime_shift/optimize.py: STUB (phase 5). cvxpy per-regime, Ledoit-Wolf, constraints, turnover.
- src/regime_shift/backtest.py: STUB (phase 6). Weight lag, turnover, costs, equity curve.
- src/regime_shift/metrics.py: STUB (phase 7). Sharpe/Sortino/MaxDD/Calmar/turnover + deflated Sharpe + bootstrap CI.
- src/regime_shift/benchmarks.py: STUB (phase 7). 60/40, equal-weight, rule-based ablation.
- src/regime_shift/narrate.py: STUB (phase 8). Optional LLM narration (offline-safe, report-only).
- src/regime_shift/plots.py: STUB. Regime overlay, equity+drawdown, transition heatmap.
- tests/test_smoke.py: DONE. Package import + config validation (2 tests pass).
- notebooks/: empty (driver notebook is phase 9).
- Full build plan (read this first): C:\Users\Anklesh\.claude\plans\c-users-anklesh-appdata-local-temp-proj-recursive-bentley.md

## Current state
- Phase 0 (scaffold) and Phase 1 (data pipeline) DONE, committed, verified. Env locked (uv.lock).
  2 tests green, ruff clean. 2 commits, not pushed.
- Live-verified: US master 2263x4 (equity_ret, bond_ret, gold_ret, vix); India master 2193x3
  (equity_ret, gold_ret, vix). ^INDIAVIX full 2015-2023, 0% NaN.
- FRED was unreachable from the build sandbox (network); code is correct and degrades gracefully.

## Active task
Phase 2: implement src/regime_shift/features.py (edit the stub). Momentum (5/21/63/126d
pct_change), realized vol (rolling std * sqrt(252) at 5/21/63d), VIX level + change, macro
passthrough. All causal. NO standardization here (that happens per fold in walk-forward). Add a
leak-proof property test: a feature at time t must be identical whether or not future rows exist.

## Next steps
1. Resolve India bond proxy (config india.bond empty); pick a Yahoo gilt/bond ETF or duration proxy.
2. Phase 2 features.py + leak-proof property test.
3. Phase 3 regime.py (HMM + jumpmodels, stable labels, causal decode, BIC/dwell) + plots overlay.
4. Phase 4 walkforward.py (expanding splits, train-only scaling).
5. Phases 5-7 optimize, backtest, metrics, benchmarks.
6. Phase 8 narration (optional); Phase 9 driver notebook + README results.
7. Push to GitHub only on user go-ahead (gh repo create, public).

## How to run
- uv sync --extra dev
- uv run pytest -q ; uv run ruff check .
- Data smoke: uv run python -m regime_shift.data

## Gotchas
- GateGuard hook (ECC gateguard-fact-force) DENIES every first-file-creation Write; retry after
  stating facts (importers, API, schema, verbatim instruction). Editing an existing file bypasses it.
  ECC_GATEGUARD=off disables the gate.
- git add -A once swept in .claude/ plugin sqlite files; .claude/ is now gitignored. Watch stray dirs.
- FRED (fred.stlouisfed.org) may be blocked on some networks; macro degrades gracefully.
- yfinance 1.x returns MultiIndex columns (field, ticker); data.py handles single vs multi ticker.
- India bond ticker empty means India master is equity+gold+vix only until resolved.
- The tooling research verify pass never ran (session token limit); core versions were later
  confirmed by uv, but sanity-check any remaining currency claim before relying on it.

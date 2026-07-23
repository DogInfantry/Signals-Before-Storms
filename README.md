# Regime-Shift: Macro-Aware Tactical Asset Allocation Engine

Detect hidden market regimes (Bull, Bear, Crisis) with a Hidden Markov Model, then switch
portfolio weights across equities, bonds, and gold using convex optimization. Everything is
validated with a strictly leak-proof expanding walk-forward and charged realistic transaction
costs, then compared against static 60/40 and equal-weight benchmarks.

Status: work in progress (Phase 0 scaffold). See the build plan for the full roadmap.

## Why the key decisions

- **3 regimes (Bull / Bear / Crisis):** matches the economic states we allocate against; the
  count is justified with a BIC sweep, not assumed.
- **These features:** multi-window momentum (direction), realized volatility (stress), VIX
  level, and a small set of FRED macro series (yield-curve slope, credit spread, financial
  conditions) to make the engine genuinely macro-aware.
- **India primary, US robustness:** the graded universe is Indian (NIFTY, gold, India VIX);
  the same pipeline is re-run on US assets (SPY, TLT, GLD, VIX) as an out-of-sample check.
- **Leak-proof by construction:** features are causal, standardization uses train-only stats,
  the regime model is re-fit inside every fold, and test regimes are decoded causally. This is
  asserted by unit tests, not just claimed.

## Layout

```
src/regime_shift/   core package (data, features, regime, walkforward, optimize, backtest, metrics, ...)
config/config.yaml  all knobs: universe, dates, windows, costs, seed
notebooks/          EDA plus one top-to-bottom driver
tests/              leak-proofing and metric checks
```

## Quickstart

```
uv sync
uv run pytest
```

Then run the driver notebook in `notebooks/`.

## Reproducibility

Seeds are fixed in `config/config.yaml`. Downloaded data is cached under `data/` so reruns are
offline and deterministic.

## License

MIT. See `LICENSE`.

"""Regime model: HMM (and a Jump Model second engine), causal decode, stable labels. Phase 3.

Key responsibilities the naive approach omits:
  - stable label mapping so state indices map to Bull/Bear/Crisis consistently across refits
  - causal decoding so a test-day label never uses future observations within the block
  - diagnostics: transition matrix, dwell times, BIC vs number of states
"""

from __future__ import annotations

# TODO(phase-3): GaussianHMM wrapper + jumpmodels engine behind one fit/decode interface.

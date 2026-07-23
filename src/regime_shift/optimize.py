"""Per-regime convex optimization in cvxpy: shrinkage covariance, constraints. Phase 5.

Bull: max Sharpe (convex reformulation). Bear: min variance. Crisis: defensive.
Inputs (mu, Sigma) are estimated train-only with Ledoit-Wolf shrinkage.
"""

from __future__ import annotations

# TODO(phase-5): regime objective builders + Ledoit-Wolf estimation + weight caps/turnover.

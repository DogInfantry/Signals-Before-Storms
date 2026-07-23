"""Optional LLM regime narration: plain-English commentary per detected regime. Phase 8.

Strictly a post-hoc, report-only layer. It consumes already-computed regime statistics and
never feeds back into features or weights, so it cannot leak. Offline-safe: skips cleanly
when no API key is present, and caches responses.
"""

from __future__ import annotations

# TODO(phase-8): narrate_regime(stats) -> str, guarded and cached; optional FinBERT feature.

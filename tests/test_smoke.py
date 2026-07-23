"""Phase 0 smoke tests: package imports and config loads and validates."""

from regime_shift import __version__
from regime_shift.config import load_config


def test_version():
    assert __version__


def test_config_loads():
    cfg = load_config()
    assert cfg.hmm.n_states == 3
    assert cfg.walkforward.min_train >= cfg.walkforward.test_size
    assert 0 < cfg.weight_cap <= 1
    assert "us" in cfg.universes and "india" in cfg.universes

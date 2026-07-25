"""Typed configuration loaded from config/config.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class WalkForward(BaseModel):
    min_train: int
    test_size: int
    step: int


class HMMCfg(BaseModel):
    n_states: int
    covariance_type: str
    n_iter: int
    tol: float


class Config(BaseModel):
    seed: int
    universes: dict
    dates: dict
    features: dict
    macro_fred_series: list[str]
    macro_yahoo_proxies: dict[str, str] = {}
    walkforward: WalkForward
    hmm: HMMCfg
    costs_bps: float
    weight_cap: float
    rebalance: str
    rebalance_confirm_days: int = 3
    conditional_moments: bool = True
    conditional_min_obs: int = 126


def _default_path() -> Path:
    # src/regime_shift/config.py -> repo root is parents[2]
    return Path(__file__).resolve().parents[2] / "config" / "config.yaml"


def load_config(path: str | Path | None = None) -> Config:
    """Load and validate the project config."""
    p = Path(path) if path is not None else _default_path()
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return Config(**data)

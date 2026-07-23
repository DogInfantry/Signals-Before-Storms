"""Data loading: yfinance prices plus FRED macro, aligned and cached. Plan phase 1."""

from __future__ import annotations

import pandas as pd


def load_prices(universe: dict, start: str, end: str) -> pd.DataFrame:
    """Adjusted close prices for one universe (equity/bond/gold/vix). Cached under data/."""
    raise NotImplementedError("phase 1")


def load_macro(series: list[str], start: str, end: str) -> pd.DataFrame:
    """FRED macro series, business-day aligned and point-in-time aware."""
    raise NotImplementedError("phase 1")


def build_master(universe: dict, start: str, end: str, macro: list[str]) -> pd.DataFrame:
    """Inner-join asset log-returns, VIX level, and macro into one aligned frame."""
    raise NotImplementedError("phase 1")

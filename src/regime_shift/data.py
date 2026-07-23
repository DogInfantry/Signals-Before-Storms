"""Data loading: yfinance prices plus FRED macro, aligned and cached. Plan phase 1.

yfinance 1.x handles Yahoo impersonation internally (curl_cffi), so no session is passed.
FRED is pulled keyless via the public fredgraph.csv endpoint (no API key required).
Every raw pull is cached as a pickle under data/cache/ so reruns are offline and deterministic.
"""

from __future__ import annotations

import io
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
_ASSET_ROLES = ("equity", "bond", "gold")


def _cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = key.replace("^", "").replace("/", "_").replace(" ", "").replace(":", "")
    return CACHE_DIR / f"{safe}.pkl"


def load_prices(universe: dict, start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
    """Adjusted close prices for one universe.

    Columns are the logical roles present (equity/bond/gold/vix); empty tickers are skipped.
    """
    roles = {role: tkr for role, tkr in universe.items() if tkr}
    if not roles:
        raise ValueError("universe has no non-empty tickers")
    tickers = list(roles.values())
    cache = _cache_path(f"prices_{'_'.join(tickers)}_{start}_{end}")
    if use_cache and cache.exists():
        return pd.read_pickle(cache)

    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
    else:  # single ticker: flat columns of fields
        close = raw[["Close"]].rename(columns={"Close": tickers[0]})

    tkr_to_role = {tkr: role for role, tkr in roles.items()}
    close = close.rename(columns=tkr_to_role)
    close = close[[r for r in roles if r in close.columns]]
    close = close.dropna(how="all").sort_index()
    close.to_pickle(cache)
    return close


def load_macro(series: list[str], start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
    """FRED macro series pulled keyless from fredgraph.csv, one column per series id."""
    frames = []
    for sid in series:
        cache = _cache_path(f"fred_{sid}_{start}_{end}")
        if use_cache and cache.exists():
            s = pd.read_pickle(cache)
        else:
            url = (
                "https://fred.stlouisfed.org/graph/fredgraph.csv"
                f"?id={sid}&cosd={start}&coed={end}"
            )
            resp = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
            date_col = df.columns[0]  # 'observation_date' on current FRED, 'DATE' historically
            df[date_col] = pd.to_datetime(df[date_col])
            s = (
                pd.to_numeric(df.set_index(date_col).iloc[:, 0], errors="coerce")
                .rename(sid)
                .sort_index()
            )
            s.to_pickle(cache)
        frames.append(s)
    return pd.concat(frames, axis=1)


def drop_return_outliers(returns: pd.DataFrame, max_abs: float) -> pd.DataFrame:
    """NaN out log returns too large to be a market move, and say so.

    A daily |log return| above ~0.5 (a 65% move) in a broad index or a liquid ETF is a vendor
    error, not a market event. GOLDBEES.NS on Yahoo is the live example: it prints -4.61 on
    2019-12-19 and +4.61 on 2019-12-23, a 100x round trip that inflates the series standard
    deviation more than tenfold and quietly poisons every covariance, regime fit and Sharpe
    downstream. Callers drop the flagged rows via the usual dropna.
    """
    bad = returns.abs() > max_abs
    if bad.to_numpy().any():
        for col in returns.columns[bad.any()]:
            dates = returns.index[bad[col]]
            warnings.warn(
                f"{col}: {len(dates)} implausible log returns dropped "
                f"(|r| > {max_abs}), e.g. {dates[0].date()}",
                stacklevel=2,
            )
        returns = returns.mask(bad)
    return returns


def build_master(
    universe: dict,
    start: str,
    end: str,
    macro: list[str] | None = None,
    max_abs_return: float = 0.5,
) -> pd.DataFrame:
    """Aligned frame of asset log-returns, VIX level, and (optionally) macro features.

    Macro is forward-filled onto the business-day grid and lagged one day, so a given row
    only ever uses macro values that were already published by the prior close. This is a
    pragmatic causal guard; true point-in-time vintages (ALFRED) would be stricter.

    Returns beyond max_abs_return are treated as vendor errors and dropped; see
    drop_return_outliers for why that guard is not optional.
    """
    prices = load_prices(universe, start, end)
    asset_cols = [c for c in _ASSET_ROLES if c in prices.columns]
    out = np.log(prices[asset_cols]).diff().add_suffix("_ret")
    out = drop_return_outliers(out, max_abs_return)
    if "vix" in prices.columns:
        out["vix"] = prices["vix"]

    if macro:
        try:
            m = load_macro(macro, start, end)
            grid = pd.bdate_range(out.index.min(), out.index.max())
            m = m.reindex(grid).ffill().shift(1)
            out = out.join(m.reindex(out.index))
        except Exception as exc:  # noqa: BLE001
            warnings.warn(
                f"macro fetch failed ({type(exc).__name__}); continuing without macro features",
                stacklevel=2,
            )

    return out.dropna()


if __name__ == "__main__":  # manual network smoke check (not a unit test)
    from regime_shift.config import load_config

    cfg = load_config()
    for name in ("us", "india"):
        try:
            df = build_master(
                cfg.universes[name], cfg.dates["start"], cfg.dates["end"], cfg.macro_fred_series
            )
            print(f"[{name}] master shape={df.shape} cols={list(df.columns)}")
            print(df.tail(2))
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] FAILED: {type(exc).__name__}: {exc}")

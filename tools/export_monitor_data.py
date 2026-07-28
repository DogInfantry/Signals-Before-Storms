"""Export the client-facing regime monitor: monitor/data/monitor.json.

    uv run python tools/export_monitor_data.py [TICKER ...]

Detection only. No optimizer, no backtest, no benchmark, no bootstrap. This ships the part of the
research that WORKED -- the HMM separates volatility regimes, cleanly and out of sample -- and
deliberately does not ship the part that did not, which is the regime->weights stance map that
loses outright on US.

Three properties this file exists to preserve:

  1. It NEVER touches docs/data/{india,us}.json. Those are pinned to cfg.dates (2015-2024); this
     runs to today out of cfg.monitor. Different window, different output path, different price
     cache keys. `git diff --stat docs/data/` after a run must be empty.

  2. Every asset is fitted INDEPENDENTLY: its own master, its own per-fold scaler, its own HMM.
     Eleven exchange calendars must never be inner-joined (build_master's dropna would delete
     Diwali from SPY and Thanksgiving from NIFTY), and canonical labels are ranked by each
     asset's OWN trailing vol, so "Crisis" means crisis for that asset rather than one global
     regime pasted across eleven rows.

  3. Running the same FROZEN pipeline on new tickers is out-of-sample generalization, not a knob
     search. Every asset is reported, none is adopted, nothing is re-chosen. The deflated-Sharpe
     trial count stays at 7.
"""

from __future__ import annotations

import json
import pathlib
import sys
import warnings

import numpy as np
import pandas as pd

from regime_shift.config import load_config
from regime_shift.data import build_master, load_prices
from regime_shift.features import build_features
from regime_shift.metrics import label_profile
from regime_shift.regime import REGIME_NAMES_3, dwell_times, label_episodes
from regime_shift.walkforward import run_walk_forward

# tools/ is not a package, so the sibling import needs this directory on the path. It runs under
# the documented invocation `uv run python tools/export_monitor_data.py` and only there.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

# The four JSON formatters are reused verbatim rather than re-typed, so the two payloads round
# and null identically. NOTE this import also executes export_site_data's module-level
# warnings.filterwarnings("ignore"), which is exactly why every build_master call below runs
# inside catch_warnings(record=True): otherwise the outlier guard's warning is silenced and a
# dropped vendor print becomes invisible.
from export_site_data import _frame, _round, _runs, _series  # noqa: E402

OUT = pathlib.Path("monitor/data/monitor.json")
# The Storm Ledger reads the SAME payload. Mirrored rather than exported twice so there stays
# exactly one exporter and one source of truth: a mirror cannot drift, a second export could.
MIRRORS = (pathlib.Path("ledger/public/data/monitor.json"),)
PLOT_STRIDE = 5  # weekly, as the research site. Statistics are still computed on DAILY data.

POSITION_BASIS = (
    "target volatility divided by the realized volatility measured in that regime, capped at "
    "1.0. Arithmetic on a measured quantity, shown so a risk budget can be read off the regime. "
    "It is not a backtested strategy, not a traded position, and not advice."
)


def _today() -> str:
    return str(pd.Timestamp.today().date())


def _feature_frame(ticker: str, cfg):
    """One asset's master and 7-column feature matrix, plus the data-quality facts about it."""
    mon = cfg.monitor
    universe = {"equity": ticker}

    # Nonpositive prices die SILENTLY: log() of a negative close is NaN and the row vanishes at
    # build_master's dropna with no warning at all. CL=F really settled at -$37.63 on 2020-04-20,
    # so this is measured, not hypothetical.
    raw = load_prices(universe, mon["start"], _today())
    nonpositive = int((raw["equity"] <= 0).sum())

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        master = build_master(universe, mon["start"], _today())
    notes = [str(w.message) for w in caught if "implausible" in str(w.message).lower()]
    if nonpositive:
        notes.append(
            f"{nonpositive} nonpositive close(s) in the vendor series; a log return is undefined "
            "there, so those rows are absent from every statistic below."
        )

    # yfinance hands back an in-progress candle during market hours. A half session would feed
    # mom_5, vol_5 and the headline posterior, so the newest bar is always a completed one.
    master = master[master.index < pd.Timestamp.today().normalize()]

    feats = build_features(master, cfg)
    # The 10th-feature bug (landmine 4), asserted per asset: anything that is not a known asset
    # return and not `vix` is silently promoted to a state variable. A single-role {equity: ...}
    # universe cannot trip it, and this is what proves that stayed true.
    assert len(feats.columns) == 7, (ticker, list(feats.columns))

    quality = {
        "bars": int(len(raw)),
        "rows_dropped": int(len(raw) - 1 - len(master)),
        "nonpositive_prices": nonpositive,
        "feature_cols": int(len(feats.columns)),
        "notes": notes,
        "last_price": _round(float(raw["equity"].dropna().iloc[-1]), 2),
    }
    return master, feats, quality


def _empirical_transition(labels: pd.Series, n_states: int) -> np.ndarray:
    """Row-stochastic transition COUNTED off the realized causal out-of-sample label path.

    Deliberately NOT RegimeModel.transition_matrix(), and the reason is measured rather than
    stylistic. `transmat_` is the HMM's own fitted parameter for its smoothed latent process;
    the labels this page draws come from causal forward filtering across ~40 separate refits.
    They are different quantities, and on real data they disagree badly:

        asset   diagonal implied by measured dwell   diagonal of transmat_
        ^NSEI          0.722 0.630 0.967                0.985 0.980 0.987
        QQQ            0.737 0.804 0.975                0.014 0.028 0.981
        TLT            0.839 0.865 0.964                0.025 0.074 0.975
        GC=F           0.848 0.744 0.983                0.033 0.004 0.973

    transmat_ implies 50-80 session dwells against a realized 3-6 everywhere, and on QQQ, TLT
    and GC=F hmmlearn settled into a near-deterministic 2-cycle on the final fold, which reads
    as "98.6% chance of switching tomorrow" beside a chart showing regimes that last weeks.

    A panel captioned "given today's regime, where tomorrow lands" has to describe the path it
    is drawing. This matrix is consistent by construction with the regime bands, the dwell means
    and the episode counts, because all four are counted off the same label series.

    An unobserved state has no transitions to count; its row falls back to staying put, which is
    the least-informative persistent assumption and cannot manufacture crisis probability.
    """
    v = labels.to_numpy()
    counts = np.zeros((n_states, n_states), dtype=float)
    np.add.at(counts, (v[:-1], v[1:]), 1.0)
    totals = counts.sum(axis=1, keepdims=True)
    out = np.divide(counts, totals, out=np.zeros_like(counts), where=totals > 0)
    for k in range(n_states):
        if totals[k, 0] == 0:
            out[k] = 0.0
            out[k, k] = 1.0
    return out


def _hitting_probability(transition: np.ndarray, p_now: np.ndarray, crisis: int, horizon: int):
    """P(the chain ENTERS `crisis` at least once within `horizon` steps), from `p_now`.

    Make the crisis row absorbing and propagate: mass that reaches crisis stays there, so the
    crisis component after `horizon` steps is the probability of ever having arrived.

    This is NOT `p_now @ P**horizon`, which is the MARGINAL probability of sitting in crisis on
    that one future day -- a smaller and different number. Labelling a marginal "within the next
    21 sessions" would be a wrong probability under a confident caption, which is the exact
    defect class this project keeps catching in itself.
    """
    absorbing = transition.copy()
    absorbing[crisis, :] = 0.0
    absorbing[crisis, crisis] = 1.0
    return float((p_now @ np.linalg.matrix_power(absorbing, horizon))[crisis])


def _orderings(profile: pd.DataFrame, min_episodes: int, crisis: int) -> dict:
    """Does this asset reproduce the project's central finding?

    vol_monotone: realized volatility rises with the label. That is what the HMM is FOR, and it
    held on both published universes.

    ret_ordering: 'backwards' means forward return ALSO rises with the label, i.e. the calmest
    state pays least and the most violent pays most -- the finding that killed the strategy.

    Gated on crisis EPISODES, not days, and returns 'n/e' below the threshold. This is Phase 10's
    lesson applied before the fact rather than after it: a 94-day crisis label spanning 2 episodes
    is n=2, and reading it as n=94 is precisely how this project's own jump-model "discovery" got
    retracted. An ungated table would re-commit that mistake eleven times over.
    """
    labels = sorted(profile.index)
    vol = [profile.loc[k, "eq_ann_vol"] for k in labels]
    ret = [profile.loc[k, "eq_ann_ret"] for k in labels]
    episodes = int(profile.loc[crisis, "episodes"]) if crisis in profile.index else 0

    monotone = all(b > a for a, b in zip(vol, vol[1:], strict=False))
    if len(labels) < 2 or episodes < min_episodes:
        ordering = "n/e"
    elif all(b > a for a, b in zip(ret, ret[1:], strict=False)):
        ordering = "backwards"
    elif all(b < a for a, b in zip(ret, ret[1:], strict=False)):
        ordering = "ascending"
    else:
        ordering = "mixed"
    return {
        "vol_monotone": bool(monotone),
        "ret_ordering": ordering,
        "crisis_episodes": episodes,
    }


def _asset_payload(spec: dict, cfg):
    mon = cfg.monitor
    ticker = spec["ticker"]
    crisis = cfg.hmm.n_states - 1

    master, feats, quality = _feature_frame(ticker, cfg)
    if len(feats) < mon["min_feature_rows"]:
        print(f"  SKIP {ticker:9s} {len(feats)} feature rows < {mon['min_feature_rows']}")
        return None

    # `_model` is the live fit. It is unpacked and unused on purpose: its transmat_ is NOT what
    # this page reports (see _empirical_transition), but filtered_proba below is the reason the
    # walk-forward hands the model back at all.
    labels, _model, proba = run_walk_forward(feats, cfg, return_model=True)

    # The posterior and the labels must come from the SAME fit, or the confidence on the card
    # describes a model nobody decoded with. Checked over the WHOLE final block, not just today.
    block = labels.to_numpy()[-len(proba) :]
    assert np.array_equal(proba.to_numpy().argmax(axis=1), block), ticker
    assert abs(proba.to_numpy()[-1].sum() - 1.0) < 1e-9, ticker

    profile = label_profile(labels, master)
    transition = _empirical_transition(labels, cfg.hmm.n_states)
    current_run = label_episodes(labels).iloc[-1]
    current_label = int(labels.iloc[-1])

    # Already in Crisis? Then "will it enter Crisis" is trivially ~1 and says nothing. Ship null
    # and let the card show typical crisis persistence instead.
    p_crisis = (
        None
        if current_label == crisis
        else _round(
            _hitting_probability(transition, proba.to_numpy()[-1], crisis, mon["crisis_horizon"]),
            3,
        )
    )

    position = {}
    for label in profile.index:
        vol = float(profile.loc[label, "eq_ann_vol"])
        position[str(int(label))] = (
            _round(min(1.0, mon["target_vol"] / vol), 3) if vol > 0 else None
        )

    chart_from = pd.Timestamp.today().normalize() - pd.DateOffset(years=mon["chart_years"])
    level = np.exp(master["equity_ret"].cumsum())
    level = level[level.index >= chart_from]
    level = level / level.iloc[0]
    shown = level.iloc[::PLOT_STRIDE]

    # Runs are filtered to those OVERLAPPING the window but keep their TRUE start date, so a
    # regime that began before the window reports when it really began and the chart clips it.
    runs = [r for r in _runs(labels) if pd.Timestamp(r["to"]) >= chart_from]

    return {
        "ticker": ticker,
        "name": spec["name"],
        "asset_class": spec["asset_class"],
        "currency": spec["currency"],
        "as_of": str(master.index[-1].date()),
        **quality,
        "oos": {
            "start": str(labels.index[0].date()),
            "end": str(labels.index[-1].date()),
            "n": int(len(labels)),
        },
        "current": {
            "label": current_label,
            "proba": [_round(v, 3) for v in proba.to_numpy()[-1]],
            "sessions_in_run": int(current_run.days),
            "since": str(pd.Timestamp(current_run.start).date()),
        },
        "transition": [[_round(v, 3) for v in row] for row in transition],
        "dwell": {str(int(k)): _round(v, 1) for k, v in dwell_times(labels).items()},
        "label_profile": _frame(profile),
        "position": position,
        "p_crisis_21": p_crisis,
        **_orderings(profile, mon["min_episodes"], crisis),
        "runs": runs,
        "dates": [str(d.date()) for d in shown.index],
        "prices": _series(shown),
    }


def export(only: list[str] | None = None) -> pathlib.Path:
    cfg = load_config()
    mon = cfg.monitor
    specs = [a for a in mon["assets"] if not only or a["ticker"] in only]

    previous = {}
    if OUT.exists():
        for a in json.loads(OUT.read_text(encoding="utf-8")).get("assets", []):
            previous[a["ticker"]] = a.get("bars")

    print(f"{len(specs)} assets, {mon['start']} -> today\n")
    assets = []
    for spec in specs:
        payload = _asset_payload(spec, cfg)
        if payload is None:
            continue
        assets.append(payload)

        # A vendor backfilling a historical bar shifts every row, changes fold membership and
        # moves HISTORICAL labels, with nothing raising. The bar-count delta is the tell.
        was = previous.get(spec["ticker"])
        delta = "" if was is None else f"  bars {payload['bars'] - was:+d} vs last run"
        print(
            f"  {payload['ticker']:9s} {payload['bars']:5d} bars  {payload['as_of']}  "
            f"oos {payload['oos']['n']:5d}  drop {payload['rows_dropped']}  "
            f"now L{payload['current']['label']} ({payload['current']['sessions_in_run']}d)  "
            f"vol_mono {str(payload['vol_monotone']):5s}  ret {payload['ret_ordering']:10s} "
            f"crisis_eps {payload['crisis_episodes']:3d}{delta}"
        )
        for note in payload["notes"]:
            print(f"      note: {note}")

    cutoff = pd.Timestamp.today() - pd.Timedelta(days=9)
    stale = [a["ticker"] for a in assets if pd.Timestamp(a["as_of"]) < cutoff]
    if stale:
        print(f"\n  WARNING stale (>5 sessions behind), check the ticker: {stale}")

    judged = [a for a in assets if a["ret_ordering"] != "n/e"]
    payload = {
        "generated": _today(),
        "window": {
            "start": mon["start"],
            "chart_from": str(
                (pd.Timestamp.today().normalize() - pd.DateOffset(years=mon["chart_years"])).date()
            ),
        },
        "stride": PLOT_STRIDE,
        "n_states": cfg.hmm.n_states,
        "regime_names": list(REGIME_NAMES_3),
        "target_vol": mon["target_vol"],
        "crisis_horizon": mon["crisis_horizon"],
        "min_episodes": mon["min_episodes"],
        "position_basis": POSITION_BASIS,
        "replication": {
            "vol_monotone": sum(a["vol_monotone"] for a in assets),
            "backwards": sum(a["ret_ordering"] == "backwards" for a in judged),
            "judged": len(judged),
            "total": len(assets),
        },
        "assets": assets,
    }

    blob = json.dumps(payload, separators=(",", ":"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(blob, encoding="utf-8")
    for mirror in MIRRORS:
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror.write_text(blob, encoding="utf-8")
    rep = payload["replication"]
    print(
        f"\nvol ordering monotone on {rep['vol_monotone']}/{rep['total']}; "
        f"return ordering backwards on {rep['backwards']}/{rep['judged']} with "
        f">= {mon['min_episodes']} crisis episodes to judge"
    )
    print(f"{OUT} ({OUT.stat().st_size // 1024} kB)")
    for mirror in MIRRORS:
        print(f"{mirror} (mirror)")
    return OUT


if __name__ == "__main__":
    export(sys.argv[1:] or None)

"""Export one JSON per universe so the landing page can draw real series, not screenshots.

The page was a stack of static plates, which is the wrong medium for a result whose whole
argument is a comparison: a reader cannot toggle a book on a PNG, or read a value off it. This
writes the same numbers `notebooks/real_run.py` prints into `docs/data/<market>.json`, and the
page renders them client side with no build step and no framework.

Nothing here re-derives anything. Every number comes from the same functions the printed
scorecard uses, so the page and the README cannot drift apart.

    uv run python tools/export_site_data.py [india|us|all]
"""

from __future__ import annotations

import json
import pathlib
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from regime_shift.backtest import run_backtest
from regime_shift.benchmarks import equal_weight, sixty_forty, vol_rule_regimes
from regime_shift.config import load_config
from regime_shift.data import build_master
from regime_shift.features import build_features
from regime_shift.metrics import (
    bootstrap_ci,
    deflated_sharpe,
    episode_profile,
    label_profile,
    paired_bootstrap,
    sharpe,
    summary,
)
from regime_shift.regime import RegimeModel, dwell_times, label_episodes
from regime_shift.walkforward import run_walk_forward

warnings.filterwarnings("ignore")

OUT_DIR = pathlib.Path("docs/data")
TRIALS = 7  # the same honest count the run prints; see README
BENCHES = ("60_40", "equal_weight")

# Weekly is the right resolution for an 1,800-day equity curve on a phone: the shape is
# identical and the payload is a fifth the size. Every quoted statistic is still computed on
# DAILY data, so nothing in the scorecard depends on this.
PLOT_STRIDE = 5


def _round(x, nd: int = 4):
    """JSON-safe rounding. NaN is not valid JSON, so it goes out as null."""
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return round(float(x), nd)


def _series(s: pd.Series, nd: int = 4) -> list:
    return [_round(v, nd) for v in s.to_numpy()]


def _runs(labels: pd.Series) -> list[dict]:
    """The regime path as run-length spans: what a chart wants, and far smaller than per-day.

    Delegates to regime.label_episodes, the project's single run-length implementation, so the
    spans the site shades cannot disagree with the episode counts the results report.
    """
    eps = label_episodes(labels.dropna().astype(int))
    return [
        {
            "label": int(r.label),
            "from": str(pd.Timestamp(r.start).date()),
            "to": str(pd.Timestamp(r.end).date()),
        }
        for r in eps.itertuples()
    ]


def _frame(df: pd.DataFrame) -> dict:
    """A DataFrame as {columns, index, rows}, with non-finite values nulled out."""
    return {
        "columns": [str(c) for c in df.columns],
        "index": [str(i) for i in df.index],
        "rows": [[_round(v) for v in row] for row in df.to_numpy()],
    }


def export(market: str) -> pathlib.Path:
    cfg = load_config()
    # Macro-free by construction, exactly as real_run.py builds it. A macro column here would
    # become a state variable and every number below would stop matching the published tables.
    master = build_master(cfg.universes[market], cfg.dates["start"], cfg.dates["end"])
    feats = build_features(master, cfg)
    regimes = run_walk_forward(feats, cfg)
    oos = regimes.index

    books = {
        "hmm_conditional": run_backtest(regimes, master, cfg, conditional=True),
        "hmm_unconditional": run_backtest(regimes, master, cfg, conditional=False),
        "vol_rule_ablation": run_backtest(vol_rule_regimes(master, cfg).loc[oos], master, cfg),
        "60_40": sixty_forty(master, oos, cfg),
        "equal_weight": equal_weight(master, oos, cfg),
        "hmm_vol_targeted": run_backtest(regimes, master, cfg, target_vol=0.10),
    }
    dd_regimes = run_walk_forward(build_features(master, cfg, drawdown=True), cfg)
    books["hmm_drawdown_feat"] = run_backtest(dd_regimes.loc[oos], master, cfg)
    try:
        jump = run_walk_forward(feats, cfg, engine="jump").loc[oos]
        books["jump_regime"] = run_backtest(jump, master, cfg)
    except ImportError:
        pass

    # A cash sleeve means rf is not zero, and scoring against zero would hand every defensive
    # book a free Sharpe for holding cash. Same derivation the printed scorecard uses.
    rf = 0.0
    if "cash_ret" in master.columns:
        cash = np.expm1(master["cash_ret"].loc[oos])
        rf = float((1 + cash).prod() ** (252 / len(cash)) - 1)

    excess = {k: v["ret_net"] - rf / 252.0 for k, v in books.items()}
    sharpes = {k: sharpe(v) for k, v in excess.items()}

    deflation = {
        name: {
            "sharpe": _round(sharpes[name]),
            "dsr": _round(deflated_sharpe(e, TRIALS, 0.4)),
            "ci": [_round(x) for x in bootstrap_ci(e, n_boot=2000)],
        }
        for name, e in excess.items()
    }

    # Overlapping marginal intervals say nothing about a difference. These books hold the same
    # assets on the same days, so the paired difference is the test the comparison rests on.
    paired = {
        bench: {
            name: {
                "d": _round(sharpes[name] - sharpes[bench]),
                "ci": [
                    _round(x) for x in paired_bootstrap(excess[name], excess[bench], n_boot=2000)
                ],
            }
            for name in books
            if name != bench
        }
        for bench in BENCHES
    }

    plot_idx = books["hmm_conditional"].index[::PLOT_STRIDE]
    curves = {
        name: {
            kind: _series(
                book[f"equity_{kind}"].reindex(plot_idx) / book[f"equity_{kind}"].iloc[0], 4
            )
            for kind in ("net", "gross")
        }
        for name, book in books.items()
    }
    drawdowns = {
        name: _series((book["equity_net"] / book["equity_net"].cummax() - 1).reindex(plot_idx), 4)
        for name, book in books.items()
    }

    level = np.exp(master["equity_ret"].cumsum()).loc[oos]
    model = RegimeModel(
        n_states=cfg.hmm.n_states,
        covariance_type=cfg.hmm.covariance_type,
        n_iter=cfg.hmm.n_iter,
        tol=cfg.hmm.tol,
        random_state=cfg.seed,
    ).fit(
        StandardScaler().fit_transform(feats.to_numpy(dtype=float)),
        rank_by=feats["vol_21"].to_numpy(),
    )

    weight_cols = [c for c in books["hmm_conditional"].columns if c.startswith("w_")]
    payload = {
        "market": market,
        "oos": {"start": str(oos[0].date()), "end": str(oos[-1].date()), "n": int(len(oos))},
        "rf": _round(rf),
        "costs_bps": cfg.costs_bps,
        "trials": TRIALS,
        "dates": [str(d.date()) for d in plot_idx],
        "curves": curves,
        "drawdowns": drawdowns,
        "equity_level": _series(level.reindex(plot_idx) / level.iloc[0], 4),
        "regime_runs": _runs(regimes),
        "regime_counts": {str(k): int(v) for k, v in regimes.value_counts().sort_index().items()},
        "dwell": {str(k): _round(v, 1) for k, v in dwell_times(regimes.to_numpy()).items()},
        "label_profile": _frame(label_profile(regimes, master)),
        "episode_profile": _frame(episode_profile(regimes, master)),
        "scorecard_gross": _frame(
            pd.DataFrame({k: summary(v, col="ret_gross", rf=rf) for k, v in books.items()}).T
        ),
        "scorecard_net": _frame(
            pd.DataFrame({k: summary(v, col="ret_net", rf=rf) for k, v in books.items()}).T
        ),
        "deflation": deflation,
        "paired": paired,
        "transition": [[_round(v, 3) for v in row] for row in model.transition_matrix()],
        "mean_weights": _frame(
            books["hmm_conditional"].groupby("regime", observed=True)[weight_cols].mean()
        ),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{market}.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return path


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name in ["india", "us"] if which == "all" else [which]:
        p = export(name)
        print(f"{name}: {p} ({p.stat().st_size / 1024:.0f} kB)")

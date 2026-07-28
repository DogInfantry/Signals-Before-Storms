"""Diff two monitor payloads and report the markets whose regime label changed.

    uv run python tools/regime_alert.py OLD.json NEW.json

Prints Markdown to stdout and exits 0 whether or not anything moved. The scheduled workflow pipes
it into `$GITHUB_STEP_SUMMARY`, so the report renders on the run page and GitHub's own
notifications carry it. **No third-party service and no secret**: there is nothing to configure,
nothing to leak and nothing to keep alive.

Detection only, by construction. This reports a STATE and its probability and never a weight,
a target or an allocation, because the stance map is the part of this research that failed and
`tools/export_monitor_data.py` deliberately ships the part that worked. A regime report that
suggested a trade would be shipping the failure.

One property worth keeping: a market missing from the OLD payload is reported as newly tracked
rather than silently dropped. Silence would be indistinguishable from "nothing changed", which is
exactly the failure mode a report like this exists to prevent.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


def _by_ticker(payload: dict) -> dict[str, dict]:
    return {a["ticker"]: a for a in payload.get("assets", [])}


def _name(names: list[str], label: int | None) -> str:
    if label is None or not (0 <= label < len(names)):
        return "unknown"
    return names[label]


def changes(old: dict, new: dict) -> list[dict]:
    """Markets whose current label differs, plus any market new to the payload.

    `from_label` is None for a newly tracked market, which is what distinguishes it from a
    transition and is why the caller must not treat these as interchangeable.
    """
    before, after = _by_ticker(old), _by_ticker(new)
    names = new.get("regime_names") or []
    out = []
    for ticker, asset in after.items():
        to_label = asset.get("current", {}).get("label")
        prior = before.get(ticker)
        from_label = prior.get("current", {}).get("label") if prior else None
        if prior is not None and from_label == to_label:
            continue
        out.append(
            {
                "ticker": ticker,
                "name": asset.get("name", ticker),
                "from_label": from_label,
                "to_label": to_label,
                "from_name": _name(names, from_label) if prior else None,
                "to_name": _name(names, to_label),
                "p_crisis_21": asset.get("p_crisis_21"),
                "as_of": asset.get("as_of"),
            }
        )
    return out


def render(changed: list[dict], generated: str | None = None) -> str:
    """One line per market. Empty string when nothing moved, so the caller can report or not."""
    if not changed:
        return ""
    head = f"Regime change, {generated}" if generated else "Regime change"
    lines = [f"**{head}**", ""]
    for c in changed:
        p = c["p_crisis_21"]
        # null means the market is already in Crisis, where "probability of reaching Crisis
        # within 21 sessions" is trivially one and quoting a number would mislead.
        tail = "already in Crisis" if p is None else f"p(Crisis within 21 sessions) {p:.2f}"
        if c["from_name"] is None:
            lines.append(f"- {c['name']} ({c['ticker']}): now tracked, {c['to_name']}, {tail}")
        else:
            lines.append(
                f"- {c['name']} ({c['ticker']}): {c['from_name']} -> {c['to_name']}, {tail}"
            )
    lines += ["", "Detection only. No position is implied."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("old", type=pathlib.Path)
    ap.add_argument("new", type=pathlib.Path)
    args = ap.parse_args(argv)

    new = json.loads(args.new.read_text(encoding="utf-8"))
    # A missing OLD file is a first run, not an error: every market then reads as newly tracked.
    old = json.loads(args.old.read_text(encoding="utf-8")) if args.old.exists() else {}

    print(render(changes(old, new), new.get("generated")) or "No regime change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

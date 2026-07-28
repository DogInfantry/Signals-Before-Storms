"""Refuse a monitor payload that lost markets or lost a label.

    uv run python tools/check_monitor_payload.py PUBLISHED.json FRESH.json

The scheduled workflow is the only thing in this repo that writes to main unattended, so the
question it has to answer before committing is not "did the exporter run" but "is this WORSE than
what is already live". Two ways it can be, both silent:

  1. Fewer markets than the published payload. A vendor that stops answering for a ticker does not
     raise; the market simply vanishes from the page.
  2. A market with no current label. The site would render a row with an empty state.

Lives in a file rather than inline in the YAML so it is linted and can be exercised offline.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


def problems(published: dict, fresh: dict) -> list[str]:
    """Reasons not to publish `fresh`. Empty list means it is safe to commit."""
    found = []
    assets = fresh.get("assets", [])
    n_old = len(published.get("assets", []))
    if len(assets) < n_old:
        found.append(f"Lost markets: {n_old} published, {len(assets)} exported.")
    unlabelled = [
        a.get("ticker", "?") for a in assets if (a.get("current") or {}).get("label") is None
    ]
    if unlabelled:
        found.append(f"Markets with no current label: {unlabelled}")
    if not assets:
        found.append("No markets in the payload.")
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("published", type=pathlib.Path)
    ap.add_argument("fresh", type=pathlib.Path)
    args = ap.parse_args(argv)

    fresh = json.loads(args.fresh.read_text(encoding="utf-8"))
    published = (
        json.loads(args.published.read_text(encoding="utf-8")) if args.published.exists() else {}
    )

    found = problems(published, fresh)
    for line in found:
        print(line, file=sys.stderr)
    if found:
        return 1
    print(f"Payload sane: {len(fresh['assets'])} markets, generated {fresh.get('generated')}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

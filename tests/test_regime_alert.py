"""The scheduled monitor's two guards, as tests: what it says when a market moves, and what it
refuses to publish.

Synthetic payloads only, and no network at all: the reporter prints Markdown and nothing else, so
there is no delivery path to stub. Two of these are load-bearing. A report that quietly dropped a
market it had not seen before would be indistinguishable from a quiet week, which is the one
failure a report like this cannot be allowed to have; and the publish guard is the only thing
standing between a vendor outage and a live page that silently lost a market.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from check_monitor_payload import problems  # noqa: E402
from regime_alert import changes, render  # noqa: E402

_NAMES = ["Bull", "Bear", "Crisis"]


def _payload(*assets: dict, generated: str = "2026-01-15") -> dict:
    return {"generated": generated, "regime_names": _NAMES, "assets": list(assets)}


def _asset(ticker: str, label: int, p: float | None = 0.2, name: str | None = None) -> dict:
    return {
        "ticker": ticker,
        "name": name or ticker,
        "as_of": "2026-01-15",
        "current": {"label": label, "proba": [0.0, 0.0, 0.0], "sessions_in_run": 3},
        "p_crisis_21": p,
    }


def test_unchanged_labels_produce_no_message():
    old = _payload(_asset("AAA", 0), _asset("BBB", 1))
    new = _payload(_asset("AAA", 0), _asset("BBB", 1))
    assert changes(old, new) == []
    assert render(changes(old, new), new["generated"]) == ""


def test_transition_is_reported_with_both_state_names():
    old = _payload(_asset("AAA", 0), _asset("BBB", 1))
    new = _payload(_asset("AAA", 2, p=None), _asset("BBB", 1))
    (moved,) = changes(old, new)
    assert (moved["ticker"], moved["from_label"], moved["to_label"]) == ("AAA", 0, 2)
    msg = render(changes(old, new), new["generated"])
    assert "Bull -> Crisis" in msg
    # p_crisis_21 is null once a market IS in Crisis; quoting a probability there would mislead.
    assert "already in Crisis" in msg
    assert "BBB" not in msg


def test_probability_is_quoted_when_the_market_is_not_yet_in_crisis():
    old = _payload(_asset("AAA", 0))
    new = _payload(_asset("AAA", 1, p=0.4321))
    assert "p(Crisis within 21 sessions) 0.43" in render(changes(old, new))


def test_message_never_implies_a_position():
    """The monitor ships detection because the stance map is what failed. Guard the wording."""
    old = _payload(_asset("AAA", 0))
    new = _payload(_asset("AAA", 2, p=None))
    msg = render(changes(old, new), new["generated"]).lower()
    assert "no position is implied" in msg
    body = msg.replace("no position is implied", "")
    for banned in ("weight", "allocat", "buy", "sell", "target vol"):
        assert banned not in body


def test_a_market_absent_from_the_old_payload_is_reported_not_dropped():
    old = _payload(_asset("AAA", 0))
    new = _payload(_asset("AAA", 0), _asset("CCC", 2, p=None, name="New Market"))
    (added,) = changes(old, new)
    assert added["ticker"] == "CCC"
    assert added["from_label"] is None
    assert "now tracked" in render(changes(old, new), new["generated"])


def test_a_healthy_payload_publishes():
    published = _payload(_asset("AAA", 0), _asset("BBB", 1))
    assert problems(published, _payload(_asset("AAA", 2), _asset("BBB", 1))) == []


def test_a_payload_that_lost_a_market_is_refused():
    """A vendor that stops answering does not raise; the market just vanishes from the page."""
    published = _payload(_asset("AAA", 0), _asset("BBB", 1))
    (why,) = problems(published, _payload(_asset("AAA", 0)))
    assert "Lost markets" in why


def test_a_market_with_no_current_label_is_refused():
    blank = _asset("BBB", 1)
    blank["current"] = {}
    (why,) = problems(_payload(_asset("AAA", 0)), _payload(_asset("AAA", 0), blank))
    assert "BBB" in why


def test_an_empty_payload_is_refused_even_on_a_first_run():
    assert problems({}, _payload()) != []


def test_a_payload_older_than_the_published_one_is_refused():
    """The defect the first runner execution actually shipped (run 30394100175, 2026-07-28).

    The published payload reached 2026-07-28 and the run replaced it with one reaching only
    2026-07-27, rolling the live site a day backwards. Every market was present and labelled, so
    nothing else in this module objected. Fetch a few minutes before a close, or catch a vendor
    mid-update, and a stale answer is indistinguishable from a quiet day without this check.
    """
    old, new = _asset("AAA", 0), _asset("AAA", 0)
    old["as_of"], new["as_of"] = "2026-07-28", "2026-07-27"
    (why,) = problems(_payload(old), _payload(new))
    assert "backwards" in why and "2026-07-28" in why


def test_re_exporting_the_same_session_is_not_backwards():
    """A quiet day re-exports identical dates. That must publish, not fail."""
    same = _asset("AAA", 0)
    assert problems(_payload(same), _payload(dict(same))) == []

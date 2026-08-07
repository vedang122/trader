"""News digest freshness: the 40-item cap must be spent on today's tape.

A feed serving 2024 archives is functionally dead, but its rows arrive looking
exactly like this morning's. Python filters them out — the agent reading the
digest must not have to date-check every line by hand.
"""
from datetime import timedelta

import pytest

from engine import common, news


def _rfc822(dt):
    """RSS pubDate format, tz offset included — what the real feeds emit."""
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def _wire(monkeypatch, feeds: dict):
    """Point digest() at canned feeds; no network, no key-gated API sources."""
    monkeypatch.setattr(news, "FEEDS", {n: f"http://test/{n}" for n in feeds})
    monkeypatch.setattr(news, "api_sources", lambda: {})
    monkeypatch.setattr(news, "fetch_feed",
                        lambda url, timeout=15: feeds[url.rsplit("/", 1)[1]])


def _item(title, dt):
    return {"t": title, "date": _rfc822(dt)}


def test_stale_headlines_dropped_before_the_cap(desk, monkeypatch):
    """Observed 2026-08-06: 7 of 40 slots held 2024 moneycontrol rows while
    fresh single-name stories were silently displaced."""
    now = common.now_ist()
    fresh = [_item(f"Nifty holds gains as FII flows steady {i}", now - timedelta(hours=1))
             for i in range(45)]
    stale = [_item(f"Sensex, Nifty gain for third day in a row {i}",
                   now - timedelta(days=835)) for i in range(7)]
    # dead feed polls first, so its archive lands inside the cap — the observed case
    _wire(monkeypatch, {"dead-feed": stale, "live-feed": fresh})

    out = news.digest()

    assert len(out["headlines"]) == news.MAX_HEADLINES
    assert all("third day in a row" not in r["t"] for r in out["headlines"])


def test_headlines_carry_parsed_age_not_just_a_date_string(desk, monkeypatch):
    """Consumers filter on a number, not on free-text RFC-822."""
    now = common.now_ist()
    _wire(monkeypatch, {"live-feed": [_item("RBI holds repo rate", now - timedelta(hours=5))]})

    row = news.digest()["headlines"][0]

    assert 4.5 < row["age_hours"] < 5.5
    # ISO-8601 sorts lexically; the raw pubDate string does not.
    assert row["published"].startswith(now.strftime("%Y-%m-%d"))


def test_dead_feed_is_named_in_the_digest_header(desk, monkeypatch):
    """A feed whose newest item predates the window is down, not quiet —
    the desk must be able to see it next to feeds_ok / feeds_failed."""
    now = common.now_ist()
    _wire(monkeypatch, {
        "live-feed": [_item("Rupee firms against dollar", now - timedelta(hours=2))],
        "dead-feed": [_item("Sensex ends higher on earnings optimism",
                            now - timedelta(days=835))]})

    out = news.digest()

    assert out["feeds_stale"] == ["dead-feed"]
    assert any(f.startswith("live-feed") for f in out["feeds_ok"])


def test_undated_headlines_survive(desk, monkeypatch):
    """An unparseable date is unknown age, not proven stale — dropping those
    would blind the desk to any feed that omits pubDate."""
    _wire(monkeypatch, {"live-feed": [{"t": "Nifty snaps three-day losing streak",
                                       "date": ""}]})

    row = news.digest()["headlines"][0]

    assert row["age_hours"] is None
    assert row["published"] is None


@pytest.mark.parametrize("weekday,expected", [(2, 48), (5, 72)])
def test_weekend_window_stretches_to_cover_fridays_tape(weekday, expected):
    """Saturday's freshest possible news is Friday's — a 48h window would
    empty the digest every weekend."""
    day = common.now_ist().replace(hour=9) + timedelta(
        days=(weekday - common.now_ist().weekday()) % 7)
    assert day.weekday() == weekday
    assert news.max_age_hours(day) == expected


def test_freshest_headlines_win_the_cap(desk, monkeypatch):
    """Within the window the budget still goes to the newest news first."""
    now = common.now_ist()
    old = [_item(f"Nifty range-bound in thin trade {i}", now - timedelta(hours=40))
           for i in range(news.MAX_HEADLINES)]
    new = [_item("Nifty jumps on RBI rate cut", now - timedelta(minutes=20))]
    _wire(monkeypatch, {"a-old": old, "b-new": new})

    out = news.digest()

    assert out["headlines"][0]["t"] == "Nifty jumps on RBI rate cut"

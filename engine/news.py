"""Indian financial news digest — deterministic context-diet layer.
Python fetches RSS headlines (titles only), keyword-filters against the
watchlist + macro terms, dedupes, and emits a capped digest. Agents read the
digest, never raw feeds. The news-analyst publishes sentiment back through
`sentiment --set`, which validates and journals it.
Usage:
    python3 -m engine.news digest            # fetch, filter, save, print top 25
    python3 -m engine.news sentiment --set '<json>'
    python3 -m engine.news sentiment         # show current
"""
import email.utils as eut
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

from engine import common

FEEDS = {
    "et-markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "moneycontrol-markets": "https://www.moneycontrol.com/rss/marketreports.xml",
    "moneycontrol-business": "https://www.moneycontrol.com/rss/business.xml",
    "livemint-markets": "https://www.livemint.com/rss/markets",
    "business-standard": "https://www.business-standard.com/rss/markets-106.rss",
}

# symbol → name fragments to match in headlines (lowercase)
NAMES = {
    "RELIANCE": ["reliance", "ril"], "HDFCBANK": ["hdfc bank"],
    "ICICIBANK": ["icici"], "SBIN": ["sbi", "state bank"],
    "INFY": ["infosys"], "TCS": ["tcs", "tata consultancy"],
    "LT": ["larsen", "l&t"], "ITC": ["itc"], "HINDUNILVR": ["hindustan unilever", "hul"],
    "M&M": ["mahindra"], "MARUTI": ["maruti"], "TATASTEEL": ["tata steel"],
    "BHARTIARTL": ["airtel", "bharti"], "SUNPHARMA": ["sun pharma"], "TITAN": ["titan"],
}
MACRO = ["nifty", "sensex", "rbi", "fed ", "federal reserve", "crude", "brent", "opec",
         "rupee", "inflation", "cpi", "gdp", "fii", "dii", "budget", "gst", "tariff",
         "iran", "geopolit", "monsoon", "sebi", "earnings", "results", "downgrade",
         "upgrade", "rate cut", "rate hike", "war", "sanction"]

MAX_HEADLINES = 40
MAX_AGE_HOURS = 48          # weekday freshness window
MAX_AGE_HOURS_WEEKEND = 72  # Sat/Sun: Friday's tape is still the latest tape


def max_age_hours(dt: datetime | None = None) -> int:
    return MAX_AGE_HOURS_WEEKEND if (dt or common.now_ist()).weekday() >= 5 else MAX_AGE_HOURS


def parse_published(raw: str) -> datetime | None:
    """RSS RFC-822 or news-API ISO-8601 → IST datetime. None if unparseable —
    unknown age, which is not the same claim as fresh or stale."""
    raw = (raw or "").strip()
    if not raw:
        return None
    dt = None
    try:
        dt = eut.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt is None:
        return None
    if dt.tzinfo is None:  # a feed that omits the offset means its own wall clock
        dt = dt.replace(tzinfo=common.IST)
    return dt.astimezone(common.IST)


def fetch_feed(url: str, timeout: int = 15) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (kautilya-desk)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        tree = ET.fromstring(r.read())
    out = []
    for item in tree.iter("item"):
        title = (item.findtext("title") or "").strip()
        if title:
            # the full pubDate, not a prefix: truncating it severs the tz offset
            out.append({"t": re.sub(r"\s+", " ", title)[:160],
                        "date": (item.findtext("pubDate") or "").strip()[:40]})
    return out


def tag(title: str) -> list[str]:
    low = title.lower()
    tags = [sym for sym, frags in NAMES.items() if any(f in low for f in frags)]
    if any(k in low for k in MACRO):
        tags.append("MACRO")
    return tags


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (kautilya-desk)"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def api_sources() -> dict:
    """Optional key-gated APIs (export in ~/.zshrc). RSS needs no keys and is
    always on; these deepen coverage when present."""
    out = {}
    if os.environ.get("NEWSAPI_KEY"):  # newsapi.org — free dev tier
        out["newsapi"] = lambda: [
            {"t": a["title"][:160], "date": (a.get("publishedAt") or "")[:25]}
            for a in _fetch_json(
                "https://newsapi.org/v2/top-headlines?country=in&category=business"
                f"&pageSize=50&apiKey={os.environ['NEWSAPI_KEY']}").get("articles", [])
            if a.get("title")]
    if os.environ.get("GNEWS_API_KEY"):  # gnews.io — free tier
        out["gnews"] = lambda: [
            {"t": a["title"][:160], "date": (a.get("publishedAt") or "")[:25]}
            for a in _fetch_json(
                "https://gnews.io/api/v4/top-headlines?category=business&country=in"
                f"&lang=en&max=25&apikey={os.environ['GNEWS_API_KEY']}").get("articles", [])
            if a.get("title")]
    return out


def digest() -> dict:
    ok, failed, stale_feeds, rows, seen = [], [], [], [], set()
    now = common.now_ist()
    max_age = max_age_hours(now)
    dropped = 0
    sources = {**{n: (lambda u=u: fetch_feed(u)) for n, u in FEEDS.items()},
               **api_sources()}
    for name, fetcher in sources.items():
        try:
            items = fetcher()
            ok.append(f"{name}({len(items)})")
        except Exception as e:
            failed.append(f"{name}: {type(e).__name__}")
            continue
        ages = []
        for it in items:
            pub = parse_published(it.get("date", ""))
            age = None if pub is None else (now - pub).total_seconds() / 3600
            if age is not None:
                ages.append(age)
            key = it["t"].lower()[:80]
            if key in seen:
                continue
            seen.add(key)
            if age is not None and age > max_age:
                dropped += 1  # spend the cap on today's tape, not an archive
                continue
            tags = tag(it["t"])
            if tags:  # only watchlist-relevant or macro headlines survive
                rows.append({**it, "src": name, "tags": tags,
                             "published": None if pub is None else pub.isoformat(timespec="seconds"),
                             "age_hours": None if age is None else round(age, 1)})
        # a feed whose freshest item predates the window is dead, not quiet
        if ages and min(ages) > max_age:
            stale_feeds.append(name)
    # macro-only lines yield to single-name news; within each group, newest first
    rows.sort(key=lambda r: (("MACRO" in r["tags"]) and len(r["tags"]) == 1,
                             r["age_hours"] if r["age_hours"] is not None else max_age))
    rows = rows[:MAX_HEADLINES]
    out = {"ts": now.isoformat(timespec="seconds"),
           "feeds_ok": ok, "feeds_failed": failed, "feeds_stale": stale_feeds,
           "max_age_hours": max_age, "dropped_stale": dropped, "headlines": rows}
    common.save_json(common.STATE / "news" / "latest.json", out)
    return out


SENTIMENT_TONES = {"bullish", "neutral", "bearish"}


def set_sentiment(payload: str) -> dict:
    s = json.loads(payload)
    assert s.get("tone") in SENTIMENT_TONES, f"tone must be one of {SENTIMENT_TONES}"
    assert isinstance(s.get("per_symbol", {}), dict)
    for sym, v in s.get("per_symbol", {}).items():
        assert v in SENTIMENT_TONES, f"per_symbol[{sym}] must be one of {SENTIMENT_TONES}"
    assert isinstance(s.get("top_risks", []), list) and len(s.get("top_risks", [])) <= 3
    s["as_of"] = common.now_ist().isoformat(timespec="seconds")
    common.save_json(common.STATE / "sentiment.json", s)
    common.journal({"type": "sentiment_update", **s})
    return s


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "digest"
    if cmd == "digest":
        d = digest()
        print(f"feeds ok: {', '.join(d['feeds_ok']) or 'NONE'}"
              + (f" | failed: {', '.join(d['feeds_failed'])}" if d['feeds_failed'] else "")
              + (f" | STALE: {', '.join(d['feeds_stale'])}" if d['feeds_stale'] else "")
              + (f" | dropped {d['dropped_stale']} older than {d['max_age_hours']}h"
                 if d['dropped_stale'] else ""))
        for r in d["headlines"][:25]:
            print(f"[{'/'.join(r['tags'])}] {r['t']}")
        if not d["headlines"]:
            print("NO HEADLINES — treat news layer as down this cycle")
    elif cmd == "sentiment" and "--set" in sys.argv:
        print(json.dumps(set_sentiment(sys.argv[sys.argv.index("--set") + 1]), indent=2))
    elif cmd == "sentiment":
        print(json.dumps(common.load_json(common.STATE / "sentiment.json",
                                          {"tone": "neutral", "note": "never set"}), indent=2))

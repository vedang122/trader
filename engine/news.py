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
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

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


def fetch_feed(url: str, timeout: int = 15) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (kautilya-desk)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        tree = ET.fromstring(r.read())
    out = []
    for item in tree.iter("item"):
        title = (item.findtext("title") or "").strip()
        if title:
            out.append({"t": re.sub(r"\s+", " ", title)[:160],
                        "date": (item.findtext("pubDate") or "")[:22]})
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
            {"t": a["title"][:160], "date": (a.get("publishedAt") or "")[:16]}
            for a in _fetch_json(
                "https://newsapi.org/v2/top-headlines?country=in&category=business"
                f"&pageSize=50&apiKey={os.environ['NEWSAPI_KEY']}").get("articles", [])
            if a.get("title")]
    if os.environ.get("GNEWS_API_KEY"):  # gnews.io — free tier
        out["gnews"] = lambda: [
            {"t": a["title"][:160], "date": (a.get("publishedAt") or "")[:16]}
            for a in _fetch_json(
                "https://gnews.io/api/v4/top-headlines?category=business&country=in"
                f"&lang=en&max=25&apikey={os.environ['GNEWS_API_KEY']}").get("articles", [])
            if a.get("title")]
    return out


def digest() -> dict:
    ok, failed, rows, seen = [], [], [], set()
    sources = {**{n: (lambda u=u: fetch_feed(u)) for n, u in FEEDS.items()},
               **api_sources()}
    for name, fetcher in sources.items():
        try:
            items = fetcher()
            ok.append(f"{name}({len(items)})")
        except Exception as e:
            failed.append(f"{name}: {type(e).__name__}")
            continue
        for it in items:
            key = it["t"].lower()[:80]
            if key in seen:
                continue
            seen.add(key)
            tags = tag(it["t"])
            if tags:  # only watchlist-relevant or macro headlines survive
                rows.append({**it, "src": name, "tags": tags})
    rows.sort(key=lambda r: (("MACRO" in r["tags"]) and len(r["tags"]) == 1, ), )
    rows = rows[:MAX_HEADLINES]
    out = {"ts": common.now_ist().isoformat(timespec="seconds"),
           "feeds_ok": ok, "feeds_failed": failed, "headlines": rows}
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
              + (f" | failed: {', '.join(d['feeds_failed'])}" if d['feeds_failed'] else ""))
        for r in d["headlines"][:25]:
            print(f"[{'/'.join(r['tags'])}] {r['t']}")
        if not d["headlines"]:
            print("NO HEADLINES — treat news layer as down this cycle")
    elif cmd == "sentiment" and "--set" in sys.argv:
        print(json.dumps(set_sentiment(sys.argv[sys.argv.index("--set") + 1]), indent=2))
    elif cmd == "sentiment":
        print(json.dumps(common.load_json(common.STATE / "sentiment.json",
                                          {"tone": "neutral", "note": "never set"}), indent=2))

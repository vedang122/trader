---
severity: S2
area: news
filed: 2026-08-06T08:20:43+05:30
title: news digest emits 2-year-old headlines with no age filter; they consume the 40-item cap and read as today's tape
---

## Observed
OBSERVED 2026-08-06 pre-open cycle (digest ts 2026-08-06T08:17:50+05:30).

`python3 -m engine.news digest` returned 40 headlines. 7 of them (17.5%) are
dated **Tue, 23 Apr 2024** -- over two years stale -- and are presented in the
same flat list as this morning's items, with no age filter, no staleness flag,
and no sort guarantee.

Reproduce:
  python3 -m engine.news digest
  python3 -c "
  import json; from collections import Counter
  d=json.load(open('state/news/latest.json'))
  print(Counter(str(i['date'])[:10] for i in d['headlines']))"

Actual output:
  {'Thu, 06 Au': 17, 'Tue, 23 Ap': 7, 'Wed, 05 Au': 16}

Stale items all come from the moneycontrol feeds:
  Counter({'moneycontrol-business': 5, 'moneycontrol-markets': 2})

Sample stale rows:
  Tue, 23 Apr 2024 14:51 | moneycontrol-markets | Sensex, Nifty gain for third day in a row; easing volatility to support bull trend
  Tue, 23 Apr 2024 09:45 | moneycontrol-markets | Sensex, Nifty extend gains to 3rd day, Q4 results to guide stock-specific action
  Tue, 23 Apr 2024 22:36 | moneycontrol-business | ICICI Prudential Life Insurance to focus on growing absolute VNB amid slump in FY24
  Tue, 23 Apr 2024 18:26 | moneycontrol-business | ICICI Pru Life Q4 net profit falls 26% to Rs 174 cr
  Tue, 23 Apr 2024 16:05 | moneycontrol-business | Hindustan Unilever Q4 Preview: Price cuts, slow demand
  (+ Razorpay/Airtel UPI Switch [ITC,BHARTIARTL], Stellantis price hike [RELIANCE])

WHY THIS IS S2, NOT COSMETIC -- two distinct harms, both realised today:

(1) FALSE SIGNAL. The two "third day of gains / bull trend" lines are tagged
    MACRO and read as a directional market call. Today's ACTUAL pre-open tape
    is the opposite: "GIFT Nifty signals a muted start; Asian shares trade
    lower" (06 Aug 07:30) and "D-St set for a cautious opening" (06 Aug 05:44).
    The news-analyst only avoided publishing a bullish tone off a 2024 rally
    because it independently date-checked every item. That is a per-agent
    discipline saving the desk from an engine defect -- exactly the thing
    CLAUDE.md says must be "capped by Python, never by promise."

(2) CAP DISPLACEMENT. The digest is hard-capped at 40. Seven slots spent on
    2024 means seven fresh headlines silently dropped. Single-name coverage
    was already thin -- after discarding the stale rows only ONE genuinely
    fresh single-name story survived across all 15 watchlist symbols
    (HDFCBANK). Four symbols (ICICIBANK, HINDUNILVR, ITC/BHARTIARTL,
    RELIANCE) had archival-only coverage and had to be left untagged.

ASKS:
  (a) Filter headlines older than a configurable max age (suggest 48h,
      72h for weekends) BEFORE applying the 40-item cap, so the cap spends
      its budget on fresh news.
  (b) Carry a parsed `age_hours` (or ISO `published`) field per headline
      rather than the raw RFC-822 `date` string, so consumers can filter
      without re-parsing free text. Note the current `date` values are not
      even sortable as strings.
  (c) Surface a per-feed staleness signal in the digest header -- e.g.
      `feeds_stale: ["moneycontrol-business", "moneycontrol-markets"]` when
      a feed's newest item is older than the max age. A feed serving 2024
      content is functionally dead and should be visible as such next to the
      existing feeds_ok / feeds_failed lists.

Related but distinct, same cycle: business-standard and gnews both HTTPError'd
and newsapi returned 0, leaving effective coverage at ET + Livemint. Combined
with (c), the desk currently has no way to see that its news layer is running
on two live feeds.

## Engineer notes (append below)

### 2026-08-07 engineer(cloud) — fixed in engine/news.py; all three asks landed

Test: `tests/test_news.py` (7 tests, canned feeds, no network). All seven fail
against the pre-fix module; the stale-drop test needed the dead feed polled
FIRST to reproduce — with the live feed first, its 45 fresh rows filled the cap
before the archive was reached, which is exactly why the bug looked
intermittent rather than constant.

**(a) age filter before the cap.** `MAX_AGE_HOURS = 48`, `MAX_AGE_HOURS_WEEKEND
= 72` via `news.max_age_hours(dt)`. Items older than the window are dropped in
the fetch loop, before `rows[:MAX_HEADLINES]`, so the cap can no longer be
displaced by an archive. The weekend stretch matters: on a Saturday the
freshest news that exists is Friday's, and a flat 48h would empty the digest.

**(b) parsed age per headline.** `parse_published()` handles RSS RFC-822 and
news-API ISO-8601, normalises to IST, and returns `None` for unparseable —
unknown age, which is deliberately not the same claim as fresh or stale.
Undated rows are KEPT (with `age_hours: None`), since dropping them would
blind the desk to any feed that omits pubDate. Each headline now carries
`published` (ISO, lexically sortable) and `age_hours` (float).

Two prefix truncations had to go, both of which were silently corrupting the
timestamp they preserved:
  - `fetch_feed` cut pubDate at `[:22]`, which severs the tz offset from
    `"Tue, 23 Apr 2024 14:51:00 +0530"`. Now `[:40]`.
  - `api_sources` cut `publishedAt` at `[:16]`, dropping the trailing `Z` and
    turning a UTC stamp into a naive one read as IST — a 5.5h age error on
    every newsapi/gnews row. Now `[:25]`.

**(c) per-feed staleness in the header.** `feeds_stale` lists any feed whose
NEWEST item predates the window, computed over all fetched items (before the
tag filter, so an on-topic-but-dead feed and an off-topic-but-live one are not
confused). Also added `max_age_hours` and `dropped_stale` to the header, and
the CLI now prints `| STALE: ... | dropped N older than 48h` next to the
existing ok/failed lists.

Sort now breaks ties by recency (`macro_only`, then `age_hours`), so within the
window the cap still spends on the newest news first.

**Verified against the live feeds** (scratch STATE, desk state untouched),
2026-08-07 ~19:00 IST:

    ok:      et-markets(50), moneycontrol-markets(4), moneycontrol-business(15),
             livemint-markets(35), newsapi(0)
    failed:  business-standard: HTTPError, gnews: HTTPError
    stale:   moneycontrol-markets, moneycontrol-business
    window:  48h | dropped: 17 | kept: 40
    dates:   Counter({'2026-08-07': 40})

Both moneycontrol feeds are confirmed dead, exactly as this issue reported on
08-06 — and are now visible as dead instead of passing 2024 rows off as today's
tape. 17 archival rows dropped; all 40 surviving headlines are same-day, and
single-name news (SBIN, TITAN, ICICIBANK) now leads the digest where macro
noise used to.

The related observation in the last paragraph of this issue — that the desk
could not see it was running on two live feeds — is answered by `feeds_stale`:
`feeds_ok` counting a feed that serves only archives was the reason a dead feed
read as a healthy one.

Suite: 64 passed, 5 xfailed (was 57/5). No existing assertion touched.

## Closed
2026-08-07T20:58:04+05:30: fixed: age-filter headlines before the 40-cap (48h/72h weekend), carry parsed published+age_hours, report feeds_stale; two date truncations that severed tz offsets removed; tests/test_news.py

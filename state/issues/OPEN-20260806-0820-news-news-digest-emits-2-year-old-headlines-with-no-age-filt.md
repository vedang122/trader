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

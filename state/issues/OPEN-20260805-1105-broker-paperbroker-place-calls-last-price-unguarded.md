---
severity: S2
area: broker
filed: 2026-08-05T11:05:54+05:30
title: PaperBroker.place calls last_price unguarded
---

## Observed
engine/broker.py:20 — PaperBroker.place() calls data.last_price(sym) outside try/except. execute.py now pre-checks the quote path, but a quote source dying between execute's check and place() still crashes mid-order instead of returning a clean failure. Protected path (broker.py) — needs human-reviewed fix. Evidence: 2026-08-04 execution-blindness incident, journal 11:50 IST entry.

## Engineer notes (append below)

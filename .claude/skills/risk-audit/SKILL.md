---
name: risk-audit
description: On-demand portfolio risk audit — book vs limits, correlation clusters, VaR estimate, bias scan of open theses. Use when the user asks "how risky is the book", before enabling live mode, or after fast market moves.
---

# Risk audit

1. Launch the `risk-officer` agent with instructions to audit the BOOK (not a
   trade): run `python3 -m engine.status`, then per its Module 9 playbook:
   - exposure vs every limit in `state/risk_limits.yaml`, with headroom numbers
   - correlation clusters (sector concentration from `state/watchlist.yaml`)
   - a simple 1-day VaR estimate per the playbook's procedure (position sizes ×
     ATR-derived daily vol from `python3 -m engine.data snapshot <sym>`)
   - re-read each open position's journaled thesis; flag any that is stale,
     unfalsifiable, or shows a bias signature
2. Relay the audit verbatim, then add your own one-paragraph verdict: is the
   desk positioned the way its stated regime and limits say it should be?
3. If any position violates current limits (e.g. limits were tightened after
   entry), present options (trim/exit/explicit waiver) — the user decides.

---
name: go-live
description: Checklist to graduate the desk from paper to live Groww order placement (real money). Use ONLY when the user explicitly asks to go live or set up real-money trading.
---

# Going live — paper → Groww Trade API

This is a human decision with real-money consequences. Walk the user through it;
never fill in credentials or the acknowledgement on their behalf.
Integration reference: `knowledge/groww-api.md`.

## Graduation criteria (check honestly, report failures)
1. ≥ 20 closed paper trades in the journal AND ≥ 4 weeks of operation
   (`python3 -m engine.stats`).
2. Latest `/debrief`: positive expectancy_R after charges, no discipline flags
   (no stop-less fills, no widened stops, no revenge-trade signatures).
3. A `/risk-audit` within the last week with no violations.
The user MAY override these for a small-capital live pilot (it is their money
and their call) — if they do, record an `override` journal entry quoting them,
and recommend `risk_per_trade_pct` at 0.5 for the first two weeks.

## Setup steps (user performs; you guide)
1. `pip install growwapi pyotp`
2. Groww app → activate Trade API subscription, generate API key + secret
   (TOTP variant recommended).
3. Credentials live in `~/.zshrc` as environment variables — NEVER in repo files:
   ```
   export GROWW_API_KEY="..."
   export GROWW_API_SECRET="..."     # TOTP seed or approval secret per knowledge/groww-api.md
   ```
   The adapter reads them from the environment at call time.
4. User edits `state/broker.yaml`: `mode: live`, `provider: groww`, and types
   the acknowledgement line VERBATIM themselves:
   `live_acknowledgement: "I accept real-money order placement"`
5. Verify wiring with a dry check: `python3 -m engine.execute <ticket> --check`
   then ONE minimum-size live order while the user watches, confirmed in the
   Groww app before autonomy resumes.

## Hard rules that survive going live
- The engine rejects live orders outside market hours (09:15–15:30 IST).
- All risk limits, the charges viability gate, the guardian, and the circuit
  breaker apply identically — nothing loosens at go-live.
- Access-token failure or any auth error → the desk stands down for the day and
  says so. It never retries auth in a loop.
- Server-side stop-loss: per `knowledge/groww-api.md`, if Groww supports GTT/SL
  orders, every entry SHOULD be followed by placing the stop server-side; until
  that is implemented, stops are enforced by the trade-cycle (Phase 1) and the
  desk must not run /loop slower than 30min during market hours with open
  positions.

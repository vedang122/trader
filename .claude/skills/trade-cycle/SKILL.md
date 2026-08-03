---
name: trade-cycle
description: Run one full wake cycle of the autonomous trading desk — clock check, position management, scan, analyst committee, risk gate, execution, journal. This is the /loop entrypoint ("/loop /trade-cycle"). Use whenever the desk should wake up and trade, or when the user says "run a cycle", "wake the desk", "check the market".
---

# One wake cycle of the trading desk

You are the desk head. You orchestrate; specialists judge; the engine enforces.
Read `CLAUDE.md` if you haven't this session. Run the phases IN ORDER. Exits
before entries, always. Log one journal note at the end via a `decision` entry.

## Phase 0 — Clock, book & guardian
`python3 -m engine.status && python3 -m engine.amend guardian && python3 -m engine.ops preflight`
(status includes the clock and sentiment age; guardian auto-tightens on
drawdown and applies any ripe limit amendment — report its actions to the user
if non-empty). Preflight verdicts bind you:
- **STAND_DOWN** → no new entries this cycle, period. If the reason is stale
  state (behind origin/main), `git pull --rebase` and re-run preflight once; if
  still stale, do nothing but report. Defend existing positions only if a live
  quote is obtainable (feed ok/degraded).
- **DEGRADED** (cache/Groww fallback) → position defense and exits allowed on
  live LTP; new entries only if the candidate's snapshot has `source: "yf"` —
  never initiate on patched or stale data. Snapshots carry a `source` field;
  `vol_ratio_20d: null` means volume is unverifiable — volume-gated setups
  cannot confirm.
- Stray `claude/*` branches in the preflight = the state auto-merge workflow
  is broken; flag it to the user in your final message every cycle until clean.
If broker mode is LIVE and this is the first cycle of the day:
`python3 -m engine.broker sync` — reconcile local book vs Groww holdings and
report any drift. On live auth failure, the desk stands down for the day. Branch:
- **Market open** → continue to Phase 1.
- **Pre-open (before 09:15 IST)** → run Phase 5 (regime + news) only, prep a
  shortlist from yesterday's scan, journal a `premarket_plan` note, end cycle.
- **Closed/weekend** → do off-hours duty instead: if last cycle today was during
  the session, run a mini-debrief note; refresh the scan for tomorrow; end cycle.
  If it's been >5 trading days since the last `/debrief`, tell the user one is due.
- Also sanity-check: if today is an NSE holiday you know of, treat as closed.

## Phase 1 — Defend the book (exits first)
For every alert in `status.alerts` (stop breached, target reached) and every
open position whose thesis looks invalidated:
- Stop breached → IMMEDIATE exit: launch `execution-trader` with a SELL
  instruction citing the stop breach. No committee needed; stops are contracts.
- Target reached or thesis stale → quick re-read: launch `technical-analyst`
  on that symbol; exit or trail per its opinion (trailing = raising the stop in
  the position state via a new journal note, never lowering it).

## Phase 2 — Circuit-breaker & capacity gate
From status: if the daily-loss breaker is tripped, or open positions are at max,
or cash < 5% of capital — skip to Phase 6. Do not window-shop setups the desk
cannot take; that breeds impatience in the journal.

## Phase 3 — Scan & committee
1. `python3 -m engine.scan --top 5` → pick the 1-2 MOST interesting candidates
   not already held (score is triage, not signal — read the snapshots yourself).
   Cross-check `state/sentiment.json`: a candidate with today's sentiment
   `bearish` needs the technical case to be exceptional, and say so in the brief.
2. For each candidate, launch IN PARALLEL (single message, run_in_background
   false): `technical-analyst` (always) + `fundamental-analyst` (only if the name
   wasn't graded in the last 30 days — check `state/journal.jsonl`) +
   `derivatives-strategist` (only if technical conviction is likely high and you
   want the structure question answered). Include in each brief: the candidate's
   sentiment tag, any relevant headline from `state/news/latest.json`, and its
   dossier path (`state/dossiers/<SYM>.md`) if the file exists.
3. Synthesize: if the technical opinion is neutral/low-confidence (<55) or the
   fundamental grade is C or veto_flag — drop the candidate here. Record why in
   one line each.

## Phase 4 — Risk gate
For each surviving candidate, launch `risk-officer` with the full package:
thesis, entry/stop/target, requested qty (from `python3 -m engine.risk size
<entry> <stop>`), analyst opinions verbatim, current conviction 0-100.
- VETO → journal a `veto_accepted` entry with the ruling. Never re-argue in the
  same cycle. A veto is data, not an obstacle.
- APPROVE → Phase 5 execution with the officer's qty and conditions.

## Phase 5 — Execute & regime upkeep
- Approved trades → launch `execution-trader` with the approval package.
  Report the engine result verbatim to the user.
- Once per trading day (first cycle of the day, or after a shock headline):
  launch `news-analyst` (publishes sentiment) and then `macro-sentinel`
  (refreshes the regime — it reads the published sentiment). Not every cycle —
  regimes don't change hourly. If sentiment in status is >24h old on a trading
  day, that's your cue.

## Phase 6 — Close the loop
1. Journal the cycle: append via a small heredoc `python3 - <<'EOF'` calling
   `engine.common.journal({"type": "cycle_summary", ...})` — phase outcomes,
   candidates considered/dropped/traded, one-line market read.
2. Desk minutes — capture the REASONING, not just the outcome. Only for cycles
   where the committee convened, the risk gate ruled, or a position decision
   was made (never for no-op ticks): write `state/minutes/<YYYY-MM-DD-HHMM>.md`
   (≤80 lines) with (a) each analyst's verdict compressed to 3-5 lines — bias,
   levels, confidence, their strongest argument AND the strongest
   counter-argument they acknowledged; (b) your synthesis — why each candidate
   advanced or dropped and what you weighed most; (c) the risk-officer's
   grounds and bias flags if consulted; (d) one falsifiable self-prediction
   ("this read is wrong if X happens by <date>"). The coach reads these at
   /debrief to score the desk's arguments, not just its P&L. Do not paste raw
   agent reports — compress; the cap is the point.
3. Tell the user (this is your final message): book state, P&L, actions taken
   with reasons, actions REJECTED with reasons, next thing you're watching.
4. If running under /loop dynamic scheduling, choose the next wake: market open
   → 1800s; pre-open → time until 09:20 IST (cap 3600s); closed → 3600s.

## Non-negotiables (repeat offenders get the desk shut down)
- Never call `engine.execute` yourself — only execution-trader does.
- Never propose an entry without a stop. Never lower a stop, ever.
- One cycle = at most 2 new entries. Boredom is not a signal.
- If data looks wrong (stale quotes, scan errors on >3 symbols), trade nothing
  and say so. No data ≥ bad data.

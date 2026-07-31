# KAUTILYA — an autonomous trading desk

A multi-agent trading firm in miniature, built on the Zerodha Varsity curriculum
(modules distilled into `knowledge/`). Judgment lives in LLM agents; enforcement
lives in deterministic Python. The two never swap roles.

## Architecture

```
                         /loop  →  /trade-cycle  (the heartbeat)
                                       │
                              ┌────── desk head (orchestrator) ──────┐
                              │                                      │
        ┌──────────┬──────────┼──────────────┐                       │
   technical-  fundamental-  derivatives-  macro-                    │
    analyst      analyst      strategist   sentinel                  │
     (M2)         (M3)         (M4,5,6)     (M8) ──► regime.json     │
        └──────────┴─────┬────┴──────────────┘                       │
                         ▼ opinions                                  ▼
                   risk-officer (M9) ── VETO ──► journal        trade-coach (M9)
                         │ APPROVE + size                        /debrief lessons
                         ▼
                  execution-trader ──► engine/execute.py ──► broker (paper|kite)
                                            │
                              deterministic risk gate (engine/risk.py)
                              re-checks EVERY order vs state/risk_limits.yaml
```

Two-brain rule: agents reason, `engine/` enforces. No order reaches a broker
except through `engine/execute.py`, which re-validates every limit no matter
which agent asks. The risk-officer's veto is final at the judgment layer; the
engine's REJECT is final at the enforcement layer.

## Map
- `knowledge/` — distilled playbooks (rebuild: `/distill-modules`).
- `.claude/agents/` — 8 specialists: technical-analyst, fundamental-analyst,
  derivatives-strategist, macro-sentinel, news-analyst, risk-officer,
  execution-trader, trade-coach.
- `.claude/skills/` — trade-cycle (heartbeat), debrief, risk-audit, go-live,
  distill-modules.
- `engine/` — data.py (yfinance, `.NS`), scan.py, risk.py (incl. cost-viability
  gate), charges.py (transaction-cost model, state/charges.yaml), portfolio.py,
  broker.py (paper default; Groww live adapter, Kite legacy — live creds come
  from env vars GROWW_API_KEY/GROWW_API_SECRET, never files), execute.py (the
  only market door), status.py (also tracks the equity curve), regime.py,
  news.py (RSS digest + sentiment; optional NEWSAPI_KEY/GNEWS_API_KEY env
  enhancers), stats.py (journal → scorecard), amend.py (limit amendments +
  drawdown guardian), common.py (journal lives here).
- `state/` — risk_bounds.yaml (HUMAN-OWNED outer envelope), risk_limits.yaml
  (desk-tuned via engine.amend only), watchlist.yaml, portfolio.json,
  regime.json, sentiment.json, broker.yaml, journal.jsonl (append-only audit
  trail), equity.jsonl, lessons/ (capped per-agent memory), amendments/,
  tickets/, scans/, news/, debriefs/, stats.json.

## Memory tiers (context discipline — why the desk doesn't rot)
- T0 `raw/` PDFs: never in any trading context (Read-denied in settings);
  distillation only.
- T1 `knowledge/` playbooks: each agent reads ONLY its own (~400 lines).
- T2 live state: engine-generated compact JSON (status, scan, digest,
  sentiment, scorecard) — always capped by Python, never by promise.
- T3 `journal.jsonl` + `equity.jsonl`: write-only for agents; queried through
  `engine.stats` or targeted grep/tail, never bulk-loaded.
- T4 curated memory, coach-gardened at /debrief — the only self-written tier:
  `state/lessons/` (12 lessons/agent hard cap, trial→validated→retired
  lifecycle) and `state/dossiers/` (per-symbol entity pages, 80-line cap,
  claims validated by subsequent P&L, not by corroboration — see
  state/dossiers/README.md).

## Evolution loop
fills+vetoes → journal → `engine.stats` scorecard → trade-coach attribution at
/debrief → per-agent lessons (capped) + strategy-tag edge table → limit
amendments via `engine.amend` (tighten instant; loosen evidence-gated: ≥20
closed trades, expectancy_R ≥ 0.1, ≤25% step, 24h cooling with human veto,
≥14 days apart) → agents read their lessons next session. The drawdown
guardian (`engine.amend guardian`, run every cycle) auto-tightens: −5% equity
from peak halves per-trade risk, −10% floors it and forces risk_off.

## News & sentiment layer
`engine.news digest` fetches Indian financial RSS (ET, Livemint, Moneycontrol,
Business Standard), keyword-filters to watchlist+macro, caps at 40 headlines —
agents never touch raw feeds. Once per trading day the news-analyst compresses
the digest into `state/sentiment.json` (tone + per-symbol tags + ≤3 risks, via
`engine.news sentiment --set`, journaled); macro-sentinel and the committee
consume that one small object, not the news itself.

## Running the desk
- One cycle now: `/trade-cycle`
- Autonomous: `/loop /trade-cycle` (self-paced: ~30min while market open,
  hourly otherwise; NSE hours 09:15–15:30 IST Mon–Fri)
- Weekly: `/debrief` · Anytime: `/risk-audit` · Real money: `/go-live` (gated)

## Non-negotiables (for every session in this repo)
1. `state/risk_bounds.yaml` is HUMAN-OWNED — no agent touches it, ever.
   `state/risk_limits.yaml` changes ONLY through `engine.amend` (never a direct
   edit): tightening is instant, loosening is evidence-gated + cooled with
   human veto. The desk tunes itself inside the envelope; the envelope is law.
2. Every entry has a stop at ticket time. Stops never move down.
3. Only execution-trader calls `engine.execute`; it only acts on risk-officer
   approvals or stop/target exits.
4. A veto is journaled and accepted — no re-arguing within the cycle.
5. Max 2 new entries per cycle. No data ≥ bad data: on stale/failed quotes,
   stand down and say so.
6. Paper mode is the default existence. Live mode only via /go-live with the
   human typing the acknowledgement themselves.
7. Every trade carries a falsifiable thesis + conviction 0-100 in the journal —
   the coach scores calibration against it later; unfalsifiable theses are vetoable.

## Honest scope
This desk swing-trades NSE equities on daily bars with REAL capital of ₹10,000
(Groww). It is not HFT, does not see level-2 data, and its yfinance quotes can
be delayed — it makes no claims that depend on intraday speed. At this capital,
transaction costs are the first adversary: every paper fill pays the full
Groww charge model, and the risk gate rejects trades whose round-trip costs
exceed 25% of the expected gain. Its edge, if any, is discipline: multi-lens
analysis, adversarial review, deterministic risk math after costs, and a
journal it cannot dodge.

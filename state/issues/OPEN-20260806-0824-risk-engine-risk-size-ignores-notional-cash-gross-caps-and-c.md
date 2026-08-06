---
severity: S3
area: risk
filed: 2026-08-06T08:24:55+05:30
title: engine.risk size ignores notional/cash/gross caps and can suggest a 4x-oversized qty into the risk-officer package
---

## Observed
OBSERVED 2026-08-06 pre-open cycle, during shortlist sizing prep.

TWO DEFECTS ON THE SAME SURFACE (engine/risk.py sizing), both S3 -- deterministic
enforcement in validate() is INTACT, so neither is a safety hole. Filing because
both feed wrong numbers into the committee, where an LLM has to catch them.

--------------------------------------------------------------------
(1) `engine.risk size` is blind to every cap except per-trade risk
--------------------------------------------------------------------
suggest_qty() (engine/risk.py:18-23) is purely:
    int((capital * risk_pct / 100) // abs(entry - stop))

It never consults max_position_notional_pct, available cash, max_gross_exposure_pct,
or the regime multiplier -- all of which validate() (engine/risk.py:79-90) *does*
enforce moments later.

Reproduce (TATAPOWER, last 383.0, ATR14 ~3, so a sub-1-ATR stop is plausible):
  $ python3 -m engine.risk size 383 381
  {"suggested_qty": 37, "risk_amount": 74.0}

37 x 383 = Rs 14,171 notional. That is:
  - 4.0x the max_position_notional_pct cap (35% = Rs 3,500)
  - 1.4x total available cash (Rs 9,991.98)
  - 2.0x the regime-scaled gross cap (Rs 7,000 at neutral/0.7)

The risk_amount it reports (Rs 74) is truthful about stop-loss risk and silent
about the fact that the position cannot be opened at all.

WHY IT MATTERS: .claude/skills/trade-cycle/SKILL.md Phase 4 instructs the desk
head to launch the risk-officer with "requested qty (from `python3 -m engine.risk
size <entry> <stop>`)". So this number is, by protocol, the qty that enters the
risk-officer's package. The officer must independently notice it is 4x oversized.
That inverts the two-brain rule: deterministic Python should hand the judgment
layer a number that is already legal, and let judgment argue about whether to
take it. Today it hands over an illegal one and relies on an agent to catch it.

The tighter the stop, the worse the overshoot -- i.e. it misfires hardest on
precisely the low-ATR, well-defined-risk setups the desk should like most.

ASK: have suggest_qty take the portfolio + limits + regime and return
min(risk_qty, notional_qty, cash_qty, gross_qty). When a non-risk cap binds,
say which one, e.g.:
  {"suggested_qty": 9, "risk_amount": 18.0,
   "binding_constraint": "max_position_notional_pct (Rs 3,500)",
   "risk_uncapped_qty": 37}
Keeping the uncapped figure visible preserves the current diagnostic value
without shipping an unusable number as the headline.

--------------------------------------------------------------------
(2) state/risk_limits.yaml comment states the wrong rupee risk budget
--------------------------------------------------------------------
Line reads:
    risk_per_trade_pct: 0.75        # Rs 100 max loss to stop per trade (Module 9)

But 0.75% of capital_base 10,000 = **Rs 75**, not Rs 100. Confirmed against the
engine's own arithmetic:
  $ python3 -c "print(10000*0.75/100)"   ->  75.0
  $ python3 -m engine.risk size 1055 1020   ->  {"suggested_qty": 2, "risk_amount": 70.0}
     (2 x 35 = 70, i.e. capped by the Rs 75 budget -- 3 shares would be 105)

A 33% overstatement of the per-trade risk budget, sitting in the file agents read
to understand their own constraints. The number was presumably correct under an
earlier risk_per_trade_pct of 1.0 and did not follow the value down.

ASK: correct the comment to Rs 75, and ideally derive it rather than hardcode it
(a literal that must be hand-synced to a value on the same line will drift again
the next time engine.amend tightens risk_per_trade_pct -- which the drawdown
guardian does automatically, without touching comments).

NOTE ON SCOPE: state/risk_limits.yaml is amendable only via engine/amend.py.
Whether a comment-only correction can or should route through the amend path is
a judgment for the engineer; flagging it, not prescribing the mechanism.

## Engineer notes (append below)

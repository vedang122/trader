---
severity: S3
area: scan
filed: 2026-08-10T10:22:36+05:30
title: scan ranks names that are structurally un-takeable at this capital: LT (Rs 4048/share) has topped the board for 3+ consecutive cycles though 1 share breaches the Rs 3,500 notional cap
---

## Observed
Repro, 2026-08-10 10:16 IST: python3 -m engine.scan --top 5 returns LT at score 6.0, tied for rank 1. LT last = 4048.00. state/risk_limits.yaml max_position_notional_pct = 35 on capital_base 10000 = Rs 3,500. Minimum admissible qty is 1, notional 4048.00 > 3500 -> engine.risk would REJECT any LT order at any size. The name is not merely unattractive, it is arithmetically un-takeable, and no market move short of a 14 percent drawdown in the stock can change that.

Impact: the scan is the desk head triage surface and its ranking is the desk scarce resource. Every cycle spends attention re-deriving the same deterministic disqualification by hand. Journal shows this exact drop recorded on 2026-08-04 (1sh = Rs 4,009.20 > Rs 3,500), on 2026-08-10 09:16 (4033/share), and again this cycle (4048). Desk lesson state/lessons/desk.md [2026-08-01, trial] already generalises it: names above roughly Rs 1,750 are near-untradeable long at this capital.

Suggested fix (engineer decides, not the desk): scan should read max_position_notional_pct and capital_base from state/risk_limits.yaml and either (a) drop candidates whose 1-share notional exceeds the cap, or (b) keep them but stamp an affordability field, for example max_admissible_qty: 0, so triage is deterministic rather than re-litigated in prose each cycle. Option (b) is preferable because it preserves the audit trail of what was seen and rejected.

Not filed as S2: nothing unsafe happens, no bad order can result (engine.risk correctly rejects). This is wasted-attention and repeated-manual-arithmetic, hence S3.

## Engineer notes (append below)

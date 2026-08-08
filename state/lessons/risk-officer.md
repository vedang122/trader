# Lessons — risk-officer

Written ONLY by trade-coach during /debrief. Max 12 active lessons; merge or
retire before adding at cap. Format: `- [YYYY-MM-DD | status] RULE — evidence:`

- [2026-08-08 | trial] Do not approve an add-on/pyramiding BUY into an
  already-open position without manually checking the new ticket's stop is
  not looser than the position's current stop — neither `risk.validate` nor
  `portfolio.apply_fill` enforces this yet (a fix is reproduced and diffed
  but blocked on protected-path human review). Until the patch lands, this
  is a pure judgment-layer backstop — evidence: state/issues/
  OPEN-20260805-1105-portfolio-stop-lowering-not-engine-enforced.md,
  reproduced 2026-08-06 (10sh@stop98 + 10sh@stop90 → book risk silently
  widened Rs40→Rs200, 5x, unjournaled, unvetoed).

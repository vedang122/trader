---
name: distill-modules
description: (Re)build the desk's knowledge base from the Varsity PDF modules in raw/ — extract text, fan out one distiller agent per module, verify outputs. Use when PDFs are added/updated in raw/ or a knowledge file is missing/corrupt.
---

# Rebuilding the knowledge base

This pipeline is SOURCE-AGNOSTIC: Varsity was the founding curriculum, not the
ceiling. Any approved PDF/book/paper dropped in `raw/` (e.g. after the coach
flags a doctrine gap at /debrief) distills through the same steps — same
playbook format, same Opinion-protocol ending, same per-agent routing.

1. Extract text: run the pypdf extraction over `raw/*.pdf` into `raw/text/`
   (see git history of this skill or re-derive: PdfReader → page.extract_text →
   collapse blank runs → `raw/text/<kebab-name>.txt`).
2. For each module, launch ONE background distiller agent (all in a single
   message, model sonnet) with this contract:
   - Read the ENTIRE text file in chunks (offset/limit).
   - Write `knowledge/<topic>.md` as a decision-oriented PLAYBOOK: rules,
     thresholds, formulas, tables, checklists — no narrative, no history.
   - Preserve every numeric heuristic the module states.
   - End with an "## Opinion protocol" (analyst modules) or the veto/sizing
     protocols (risk module) defining the agent's output contract.
   - Target 250-450 lines.
   Existing mapping: module-2→technical-analysis, 3→fundamental-analysis,
   4→futures-trading, 5→options-theory, 6→option-strategies,
   8→currency-commodity, 9→risk-and-psychology.
3. When all agents complete, verify each file exists, is 200+ lines, and ends
   with its protocol section. Spot-read one table per file for sanity.
4. `knowledge/lessons.md` is NOT generated from PDFs — never overwrite it; it
   is the trade-coach's accumulated memory.

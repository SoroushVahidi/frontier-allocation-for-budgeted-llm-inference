# Canonical external baseline fairness checklist summary

Generated UTC timestamp: `20260423T021422Z`

## Presence audit
- `zhai_constrained_budget_selector`: `not_present`.
- `dipa_difficulty_proxy_allocator`: `already_present_partial` (official discuss-only record + MODE A adapter lane).
- `compute_optimal_tts`: `already_present_blocked`.
- `bilal_adaptive_ttc`: `already_present_partial` (docs-only comparator note).

## Placement conclusions
- Zhai: cleanest **main-table candidate** once contract+runner are added.
- DIPA: **main-table only conditionally** under per-attempt/verifiable-task matched contract; else appendix.
- compute_optimal_tts: **appendix-only** unless re-instantiated under same mechanism family/accounting and provenance is verified.
- Bilal: **adjacent-only** unless PRM/tool/search infrastructure is genuinely shared and counted.

## Guardrail
No benchmark results are fabricated in this package; this is integration/fairness scaffolding only.

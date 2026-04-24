# Manuscript support dashboard

Compact collaborator view of the current manuscript-facing state.

## Current manuscript-facing claim surface

- Core setting: fixed-budget adaptive test-time compute allocation with branch-level allocation.
- Manuscript-facing internal method on the matched surface: `strict_f3`.
- Broader operational default on a separate surface: `strict_gate1_cap_k6`.
- The two surfaces are intentionally separate and must not be collapsed.

Primary decision authority:
- `INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
- `MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`

## Canonical evidence to cite first

1. `PAPER_SOURCE_OF_TRUTH.md`
2. `PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
3. `PAPER_ARTIFACT_MAP.md`
4. `MATCHED_SURFACE_MULTI_SEED_MAIN_COMPARISON_20260423T235900Z.md`
5. `FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`
6. `MAIN_TABLE_EXTERNAL_BASELINE_FAIRNESS_AUDIT_20260423T205134Z.md`
7. `PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md`
8. `EXTERNAL_BASELINE_PAPER_READINESS_DECISION_PACKAGE.md`

## Resolved outcomes (current)

- **Internal manuscript method:** `strict_f3` remains the manuscript-facing internal winner on the canonical matched surface.
- **Conditional-risk investigation:** completed; remains supportive/appendix-level and does not replace `strict_f3`.
- **Matched-surface stability:** strengthened by multi-seed rerun evidence package.
- **Main-table external fairness:** audited with no material issue found for current near-direct main-table policy.

## What is supportive vs canonical

### Canonical for manuscript claims
- Canonical decision docs listed above.
- Canonical paper artifact families in `PAPER_SOURCE_OF_TRUTH.md` and `outputs/README.md`.

### Supportive / appendix-level
- Conditional-risk cap promotion investigation outputs and notes.
- Component ablations and bounded mechanism diagnostics unless explicitly promoted.
- Adjacent baselines (appendix-only policy lanes).
- Real-model ours-vs-external canonical package scaffolding and dry-run manifests (`REAL_MODEL_OURS_VS_EXTERNAL_VALIDATION_20260424T002900Z.md`, `outputs/real_model_ours_vs_external_validation_20260424T002900Z/`) pending full API-backed completion.
- Real-model token/accounting appendix package scaffold added (`scripts/run_real_model_token_accounting_validation.py`) to report accuracy plus token/latency/cost diagnostics on the manuscript-facing GSM8K/MATH-500/AIME budgets 4/6/8 surface; keep appendix-only framing unless materially larger API-backed evidence arrives.
- Cross-provider appendix validation (OpenAI + Cohere) now runs through the same token-accounting script and outputs unified provider/method summaries; maintain appendix-only framing unless larger-sample evidence materially strengthens robustness.
- A new small OpenAI appendix accounting result package is available (`REAL_MODEL_TOKEN_ACCOUNTING_VALIDATION_20260424T170000Z_SMALL_APPENDIX.md`), explicitly maintained as appendix-only and non-headline.

### Historical / provenance
- Legacy dated status notes and superseded summaries retained for traceability.
- Historical materials should not be used as default claim authority.

## Fast path for a new collaborator

1. `../README.md`
2. `CANONICAL_START_HERE.md`
3. `PAPER_SOURCE_OF_TRUTH.md`
4. `INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
5. `MAIN_TABLE_EXTERNAL_BASELINE_FAIRNESS_AUDIT_20260423T205134Z.md`
6. `../scripts/CANONICAL_START_HERE.md`

## Guardrails

- Do not promote exploratory artifacts to headline manuscript evidence without a canonical decision-doc update.
- Keep the method-surface distinction explicit in docs, figures, and tables.
- Preserve historical provenance; demote with labels instead of deleting context.

# Manuscript support dashboard

Compact collaborator view of the current manuscript-facing state.

## Current manuscript-facing claim surface

- Core setting: fixed-budget adaptive test-time compute allocation with branch-level allocation.
- Matched-surface internal top cluster: `strict_f3` and `strict_gate1_cap_k6` are statistically close; `strict_f3` is used as representative for continuity.
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

- **Internal manuscript positioning:** leading frontier-allocation variants form a close matched-surface top cluster; avoid decisive winner phrasing for `strict_f3` vs `strict_gate1_cap_k6`.
- **Conditional-risk investigation:** completed; remains supportive/appendix-level and does not replace `strict_f3`.
- **Matched-surface stability:** strengthened by multi-seed rerun evidence package.
- **Main-table external fairness:** audited with no material issue found for current near-direct main-table policy.

## What is supportive vs canonical

### Canonical for manuscript claims
- Canonical decision docs listed above.
- Canonical paper artifact families in `PAPER_SOURCE_OF_TRUTH.md` and `outputs/README.md`.

### Supportive / appendix-level (not headline-evidence by default)
- Conditional-risk cap promotion investigation outputs and notes.
- Component ablations and bounded mechanism diagnostics unless explicitly promoted.
- Adjacent baselines (appendix-only policy lanes).
- Real-model ours-vs-external canonical package scaffolding and dry-run manifests (`REAL_MODEL_OURS_VS_EXTERNAL_VALIDATION_20260424T002900Z.md`, `outputs/real_model_ours_vs_external_validation_20260424T002900Z/`) pending full API-backed completion.
- Real-model token/accounting appendix package scaffold added (`scripts/run_real_model_token_accounting_validation.py`) to report accuracy plus token/latency/cost diagnostics on the manuscript-facing GSM8K/MATH-500/AIME budgets 4/6/8 surface; keep appendix-only framing unless materially larger API-backed evidence arrives.
- Cross-provider appendix validation (OpenAI + Cohere) now runs through the same token-accounting script and outputs unified provider/method summaries; maintain appendix-only framing unless larger-sample evidence materially strengthens robustness.
- A new small OpenAI appendix accounting result package is available (`REAL_MODEL_TOKEN_ACCOUNTING_VALIDATION_20260424T170000Z_SMALL_APPENDIX.md`), explicitly maintained as appendix-only and non-headline.
- OpenAI main-run artifact audit now exists (`OPENAI_REAL_MODEL_MAIN_RUN_AUDIT_20260424T160513Z.md`; outputs in `outputs/openai_real_model_main_run_audit_20260424T160513Z/`): `strict_f3` > `strict_gate1_cap_k6`, but no OpenAI evidence of frontier-allocation dominance over `external_l1_max`; maintain appendix-only/non-headline usage.
- Cohere main-run artifact audit now exists (`COHERE_REAL_MODEL_MAIN_RUN_AUDIT_20260424T163700Z.md`; outputs in `outputs/cohere_real_model_main_run_audit_20260424T163700Z/`): `strict_f3` > `strict_gate1_cap_k6`, but no Cohere evidence of frontier-allocation dominance over `external_l1_max`; keep appendix-only framing.
- Cross-provider audit now exists (`CROSS_PROVIDER_REAL_MODEL_MAIN_RUN_AUDIT_20260424T163701Z.md`; outputs in `outputs/cross_provider_real_model_main_run_audit_20260424T163701Z/`): OpenAI and Cohere agree on appendix-only status (competitive and diagnostically informative, not universally dominant).
- Operational method-specification audit now exists (`OPERATIONAL_CONTROLLER_SPECIFICATION_FOR_MANUSCRIPT_20260424T164500Z.md`; outputs in `outputs/operational_controller_specification_20260424T164500Z/`): this materially improves implementation transparency, but unresolved gaps (no single closed-form objective; heuristic gates) remain and should stay explicit.
- Unified offline claim-safety statistical audit now exists (`UNIFIED_CLAIM_SAFETY_STATISTICAL_AUDIT_20260424T200000Z.md`; outputs in `outputs/unified_claim_safety_statistical_audit_20260424T200000Z/`): strict_f3 vs strict_gate1_cap_k6 remains fragile/surface-sensitive and frontier-allocation vs `external_l1_max` remains mixed/non-dominant; preserve bounded/appendix framing for real-model claims.
- Held-out surface generalization + claim-safety runner is now added (`scripts/run_held_out_surface_generalization_claim_safety.py`) with dry-run package (`outputs/held_out_surface_generalization_claim_safety_20260424T231500Z_DRY/`) and conservative report (`HELD_OUT_SURFACE_GENERALIZATION_CLAIM_SAFETY_20260424T231500Z_DRY.md`); this currently reinforces mixed/non-dominant framing, not SOTA/dominance framing.
- Real-model decision package now exists (`REAL_MODEL_DECISION_PACKAGE_20260425T025417Z.md`; artifacts in `outputs/real_model_decision_package_20260425T025417Z/`): Cohere Stage-1 is unfavorable for dominance claims (`strict_f3`=0.5333 vs `external_l1_max`=0.8000; paired delta=-0.2667, bootstrap 95% CI [-0.4667, -0.0667], budget deltas b4=-0.3/b6=-0.3/b8=-0.2, seed deltas s11=-0.2/s23=-0.3333, and cost-normalized diagnostics favor `external_l1_max`); maintain appendix-only/diagnostic usage and do not use this as main-paper superiority evidence.

### Historical/provenance-only notes
- Historical status snapshots and interim decision notes are retained for traceability.
- When in conflict with canonical decision docs, treat historical notes as provenance-only.

### Historical / provenance
- Legacy dated status notes and superseded summaries retained for traceability.
- Historical materials should not be used as default claim authority.

## Fast path for a new collaborator

1. `../README.md`
2. `CANONICAL_START_HERE.md`
3. `PAPER_SOURCE_OF_TRUTH.md`
4. `INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
5. `REAL_MODEL_DECISION_PACKAGE_20260425T025417Z.md` (claim-boundary guardrail; appendix-only real-model usage)
6. `MAIN_TABLE_EXTERNAL_BASELINE_FAIRNESS_AUDIT_20260423T205134Z.md`
7. `../scripts/CANONICAL_START_HERE.md`

## Guardrails

- Do not promote exploratory artifacts to headline manuscript evidence without a canonical decision-doc update.
- Keep the method-surface distinction explicit in docs, figures, and tables.
- For real-model wording, treat `REAL_MODEL_DECISION_PACKAGE_20260425T025417Z.md` as a hard guardrail: no claims of real-model dominance/superiority over `external_l1_max` are manuscript-safe from current Cohere Stage-1 evidence.
- Preserve historical provenance; demote with labels instead of deleting context.

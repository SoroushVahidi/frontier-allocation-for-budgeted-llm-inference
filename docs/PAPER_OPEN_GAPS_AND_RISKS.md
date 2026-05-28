# PAPER_OPEN_GAPS_AND_RISKS

> **STATUS NOTE (2026-05-27):** This document is stale (pre-FTA era). It references `strict_f3`, DR-v2 outcome-verifier rerank, and Slurm job numbers from a prior research phase that is no longer manuscript-facing. For current open gaps and risks relevant to the FTA Applied Intelligence submission, see [`docs/CURRENT_CANONICAL_STATE_20260527.md`](CURRENT_CANONICAL_STATE_20260527.md). Historical content below is preserved for provenance.

Live list of missing pieces before submission-quality evidence closure.

## High-priority open gaps

1. **Broader independent confirmation breadth**
   - Current evidence is strong but still concentrated in current finalized passes.
   - Need broader independent confirmations without scope drift.

2. **External baseline closure limits**
   - Only a subset is currently `main_table_ready`.
   - Adjacent/import-validated methods remain mostly appendix-only.

3. **Real-model breadth and stability**
   - Current real-model confirmation is useful but bounded.
   - Need wider-condition confirmation for stronger generalization claims.
   - New canonical wrapper/package scaffold now exists (`scripts/run_real_model_ours_vs_external_validation.py`, dry-run package: `outputs/real_model_ours_vs_external_validation_20260424T002900Z/`), but full API-backed completion is still open.
   - OpenAI real-model smoke run now completed (`outputs/real_model_ours_vs_external_validation_20260424T_OPENAI_REAL_SMOKE/`), with nonzero evaluated rows but small-sample/openai-only status; still not headline-safe and still requires larger follow-up.
   - OpenAI real-model main-run artifact audit completed (`outputs/openai_real_model_main_run_audit_20260424T160513Z/`, `docs/OPENAI_REAL_MODEL_MAIN_RUN_AUDIT_20260424T160513Z.md`): `strict_f3` beats `strict_gate1_cap_k6`, but frontier-allocation does **not** dominate `external_l1_max`; keep appendix-only framing and avoid dominance overclaims.
   - Cohere real-model main-run artifact audit completed (`outputs/cohere_real_model_main_run_audit_20260424T163700Z/`, `docs/COHERE_REAL_MODEL_MAIN_RUN_AUDIT_20260424T163700Z.md`): same directional outcome as OpenAI (`strict_f3` > `strict_gate1_cap_k6`, no frontier-over-`external_l1_max` dominance), so still appendix-only.
   - Cross-provider audit completed (`outputs/cross_provider_real_model_main_run_audit_20260424T163701Z/`, `docs/CROSS_PROVIDER_REAL_MODEL_MAIN_RUN_AUDIT_20260424T163701Z.md`) and currently consistent across providers on appendix-only interpretation.
   - Contract-gap remediation jobs were generated/submitted for missing or incomplete slices (`jobs/run_missing_openai_real_model_main_slices_20260424T163922Z.sbatch`, `jobs/run_missing_cohere_real_model_main_slices_20260424T163922Z.sbatch`); until they finish, broad real-model dominance claims remain open.
   - Operational controller specification audit completed (`outputs/operational_controller_specification_20260424T164500Z/`, `docs/OPERATIONAL_CONTROLLER_SPECIFICATION_FOR_MANUSCRIPT_20260424T164500Z.md`), reducing “too conceptual” risk by mapping symbols to code and explicit hyperparameters.
   - Remaining method-specification risk is reduced but not zero: unresolved gaps still include lack of single closed-form objective and heuristic/state-dependent gates; manuscript text should acknowledge this and point to appendix operational definitions.
   - Unified offline claim-safety audit completed (`outputs/unified_claim_safety_statistical_audit_20260424T200000Z/`, `docs/UNIFIED_CLAIM_SAFETY_STATISTICAL_AUDIT_20260424T200000Z.md`): current safest position remains formulation + diagnostics + bounded artifacts, not dominance/SOTA.
   - Held-out-surface experiment scaffold is now implemented and dry-run validated (`scripts/run_held_out_surface_generalization_claim_safety.py`, `outputs/held_out_surface_generalization_claim_safety_20260424T231500Z_DRY/`), including dataset-loading status and claim-safety tables. Full HPC run remains open in environments with Slurm (`jobs/run_held_out_surface_generalization_claim_safety_20260424T231500Z.sbatch`).

   - Appendix reviewer-risk-reduction token/accounting validation scaffold now added (`scripts/run_real_model_token_accounting_validation.py`) with dry-run-safe packaging and resumable per-case artifacts (`outputs/real_model_token_accounting_validation_<timestamp>/`).
   - This closes packaging/diagnostic visibility risk, but does **not** by itself close broader real-model breadth risk without larger API-backed runs.
   - Cross-provider extension (OpenAI+Cohere) is now supported in the same runner and can emit a unified appendix package (`outputs/cross_provider_real_model_token_accounting_validation_<timestamp>/`) to reduce provider-robustness risk without changing the primary action-budget manuscript contract.
   - A small OpenAI appendix accounting run now exists (`outputs/real_model_token_accounting_validation_20260424T170000Z_SMALLAPPX_S1/`; note `docs/REAL_MODEL_TOKEN_ACCOUNTING_VALIDATION_20260424T170000Z_SMALL_APPENDIX.md`). This closes a minimal real-accounting check but remains non-headline and small-sample.

   - **DR-v2 outcome-verifier rerank** (`direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`): live-runnable with mock default and optional Cohere verifier backend. **Claim-safe paired 100-case evaluation** for the **Cohere-backed** configuration remains **open until** the designated timestamp run completes and is summarized under repo claim-safety rules. Mock-backed timestamps are provenance only for verifier-backend conclusions (`docs/OUTPUTS_ARTIFACT_INDEX.md`).

4. **Manuscript consolidation debt**
   - Surface-specific claims (`strict_gate1_cap_k6` vs `strict_f3`) must remain explicitly separated across all sections.

5. **Fresh paired-selector evidence gap**
   - In this checkout, true fresh zero-overlap package `cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T_FRESH_GSM8K_SCORER_VALIDATION` is not present.
   - Available `20260426T151700Z` package overlaps with first slice and must be treated as overlap diagnostic, not fresh-generalization evidence.

## Risks to avoid

- Accidentally presenting supportive-only artifacts as canonical headline evidence.
- Re-centering narrative on old binary revise-routing framing.
- Treating adjacent baseline adapters as fully equivalent direct baselines without caveats.
- Overstating finality of current real-model confirmations.

## Recommended mitigations

- Keep `PAPER_SOURCE_OF_TRUTH.md` and `PAPER_CLAIMS_AND_EVIDENCE_MAP.md` synchronized with draft text.
- Require every table/figure row to include source artifact family and script provenance.
- Keep conservative baseline bucket wording from `EXTERNAL_BASELINE_PAPER_READINESS_DECISION_PACKAGE.md`.

## Blocking issues (if any)

- None newly identified in this polish pass beyond known baseline breadth and broader confirmation gaps.

## Baseline gap note (test-time compute literature)
Recent literature makes token-budget allocation, training-free difficulty-proxy allocation, s1-style budget forcing, verifier/intermediate-state allocation, and routing/cascade baselines increasingly important for claim safety. This repository contains several matched-action adapters and adjacent validators, but **official/full-stack comparisons** and **token/cost-normalized dominance** remain open gaps.

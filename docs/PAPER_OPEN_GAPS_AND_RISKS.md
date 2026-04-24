# PAPER_OPEN_GAPS_AND_RISKS

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

   - Appendix reviewer-risk-reduction token/accounting validation scaffold now added (`scripts/run_real_model_token_accounting_validation.py`) with dry-run-safe packaging and resumable per-case artifacts (`outputs/real_model_token_accounting_validation_<timestamp>/`).
   - This closes packaging/diagnostic visibility risk, but does **not** by itself close broader real-model breadth risk without larger API-backed runs.
   - Cross-provider extension (OpenAI+Cohere) is now supported in the same runner and can emit a unified appendix package (`outputs/cross_provider_real_model_token_accounting_validation_<timestamp>/`) to reduce provider-robustness risk without changing the primary action-budget manuscript contract.
   - A small OpenAI appendix accounting run now exists (`outputs/real_model_token_accounting_validation_20260424T170000Z_SMALLAPPX_S1/`; note `docs/REAL_MODEL_TOKEN_ACCOUNTING_VALIDATION_20260424T170000Z_SMALL_APPENDIX.md`). This closes a minimal real-accounting check but remains non-headline and small-sample.

4. **Manuscript consolidation debt**
   - Surface-specific claims (`strict_gate1_cap_k6` vs `strict_f3`) must remain explicitly separated across all sections.

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

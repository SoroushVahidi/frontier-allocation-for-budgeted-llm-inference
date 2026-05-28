# Repository map

## Purpose

Maps where to find canonical interpretation, runnable entry points, selector artifacts, and provenance material.

## Current navigation (fast path)

- `../README.md` — short interpretation link hub (**start here hierarchy** echoed below)
- `../START_HERE_CURRENT.md`
- `CURRENT_PROJECT_STATUS.md`
- `CURRENT_EXTERNAL_BASELINE_GAP.md`
- `FAILED_AND_NEGATIVE_RESULTS_INDEX.md`
- `DISCOVERY_FAILURE_TAXONOMY.md`
- `OUTPUT_RETENTION_POLICY_CURRENT.md`
- `METHOD_STATUS_TABLE.md`
- `ARTIFACT_STATUS_TABLE.md`
- `../scripts/CURRENT_RUNBOOK.md`
- `REPOSITORY_HYGIENE_AUDIT_20260502.md`

## Recommended interpretation hierarchy

1. `../START_HERE_CURRENT.md` — minimally sufficient guardrails
2. `CURRENT_PROJECT_STATUS.md` — engineering + research synthesis
3. `CURRENT_EXTERNAL_BASELINE_GAP.md` — bounded **`external_l1_max`** comparison narrative
4. `FAILED_AND_NEGATIVE_RESULTS_INDEX.md` + `DISCOVERY_FAILURE_TAXONOMY.md` — non-headline pilots & vocabulary
5. `ARTIFACT_STATUS_TABLE.md` — interpret `outputs/` trees before citing numbers

Retention / cleanup philosophy: **`OUTPUT_RETENTION_POLICY_CURRENT.md`** and **`LOCAL_ONLY_CLEANUP_CANDIDATES_20260502.md`** (brainstorm-only).

## Canonical onboarding path

1. `../README.md`
2. `../START_HERE_CURRENT.md`
3. `CURRENT_PROJECT_STATUS.md`
4. `REPO_ORGANIZATION_GUIDE_20260501.md`
5. `DOCS_INDEX.md`
6. `CANONICAL_START_HERE.md`
7. `REPO_MAP.md`
8. `PAPER_SOURCE_OF_TRUTH.md`
9. `../scripts/CANONICAL_START_HERE.md`
10. `CANONICAL_INSTALL_AND_DEV.md`

## Selector-phase path

Use this path when the task is final-answer selector choosing or L1-defeat work:

1. `CURRENT_PROJECT_STATUS.md`
2. `CURRENT_SELECTOR_DECISION.md`
3. `LITERATURE_SELECTOR_BASELINES.md`
4. `SELECTOR_WORK_START_HERE_20260501.md`
5. `SELECTOR_CHOOSING_PLAYBOOK_20260501.md`
6. `SELECTOR_EVIDENCE_RETENTION_POLICY_20260501.md`
7. `ARTIFACT_INDEX_20260501.md`
8. `OUTCOME_VERIFIER_SELECTOR_ROADMAP.md`
9. `FAST_SELECTOR_EXECUTION_POLICY.md`
10. `OUTPUTS_SELECTOR_TRACE_INDEX.md`

Current selector caveat: the selected Cohere cached outcome-verifier selector is audited for the recovery selector-evidence track only. It is not runtime-promoted and is not an `external_l1_max` defeat claim. Fully scored paired comparison is still required for claim-safe external-baseline comparison.

## Directory roles

- `docs/` — interpretation and policy layer.
  - Canonical: current project/paper truth.
  - Selector: current L1-defeat work, artifact indexes, selector promotion criteria.
  - Diagnostic: bounded investigations and side branches.
  - Historical: provenance-preserving records.
- `scripts/` — runnable entry points and orchestration wrappers.
  - Selector evidence scripts include collectors, trace recovery, unified evidence building, schema inspection, and artifact inventory helpers.
  - Current selector runners include outcome-verifier, self-consistency, and external-baseline comparison scripts.
- `scripts/paper/` — canonical paper artifact builders for anonymous NeurIPS deliverables.
- `experiments/` — reusable implementation modules used by scripts.
  - Selector modules include conservative trace support, outcome-verifier answer-group selection, and self-consistency majority vote.
- `configs/` — machine-readable contracts for datasets/baselines/runs.
  - `configs/selected_selector_current.json` is the canonical current selected-selector config.
- `outputs/` — generated artifacts (not interpretation authority by itself).
  - `outputs/unified_selector_evidence_20260501T145906Z/` — corrected recovery selector-evidence input used for selected-selector decision.
  - `outputs/final_selector_decision_20260501T175547Z/` — final recovery-track selector decision package.
  - `outputs/selected_selector_audit_20260501T181608Z/` — selected-selector audit package.
  - `outputs/best_selector_vs_external_l1_comparison_*/` — external-baseline comparison outputs; cache-limited verifier comparisons remain diagnostic.
  - `outputs/self_consistency_*` — self-consistency literature-baseline outputs.
  - `outputs/selector_evidence_package_*/` — present-not-selected/absent/current-correct-risk casebooks.
  - `outputs/selector_evidence_trace_recovery_*/` — trace-recovery packages; verify candidate lists and manifests before use.
  - `outputs/candidate_artifact_inventory_*/` and `outputs/selector_evidence_schema_debug_*/` — diagnostic inventory/schema reports.
  - `outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/` — **1018248**: fully verifier-scored selector rerun on **88** external-loss cases (paired with **`docs/FULL_SCORE_COMPLETION_88_EXTERNAL_LOSSES_20260502.md`**).
  - `outputs/gold_absent_path_gap_diagnostic_20260502T215957Z/` — **1018287**: preferred gold-absent **path-gap proxy** diagnostic (**supersedes `...215820Z/`**, **1018285**).
  - `outputs/last_10_wulver_jobs_audit_20260502T220857Z/` — machine-readable appendix for **`docs/LAST_10_WULVER_JOBS_AUDIT_20260502.md`**.
- `tests/` — lightweight correctness/regression checks.
- `references/` — literature and citation material.
- `external/` — external baseline integration assets.
- `archive/` — preserved historical/provenance material.
- `manuscript_integration/` — manuscript-side integration helpers and packaging bridges.
- `neurips2026_anonymous_artifact/` — anonymous artifact payload staging area.
- `batch/` — Slurm submission scripts for non-interactive cluster runs.
  - `run_gold_absent_path_gap_diagnostic_wulver.sbatch` — preferred gold-absent path-gap diagnostic (pairs with `scripts/diagnose_gold_absent_path_gap.py`).
  - `run_strategy_seeded_discovery_on_66_gold_absent_wulver.sbatch` — strategy-seeded discovery pilot on the 66-case gold-absent slice (pairs with `scripts/run_strategy_seeded_discovery_on_66_gold_absent.py`).
- `jobs/` — job templates and generated scheduler files.
- `logs/` — lightweight run logs and command traces.

## Manuscript-support documents

- Source of truth: `PAPER_SOURCE_OF_TRUTH.md`
- Artifact policy: `NEURIPS_PAPER_ARTIFACTS.md`, `../outputs/README.md`
- Promotion/decision outcome: `INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
- Matched-surface rerun: `MATCHED_SURFACE_MULTI_SEED_MAIN_COMPARISON_20260423T235900Z.md`

## Canonical outputs (2026-05-27, current)

These are the canonical local-only outputs for the current FTA research phase. All are untracked/local-only.

| Output directory | Purpose | Paper-facing | Status |
|---|---|---|---|
| `outputs/fta_independent_verification_20260527/run_20260527T003000Z/` | FTA/FIX-2+FIX-4 offline verification audit | YES — main claim | CANONICAL |
| `outputs/final_fix24_all_external_validation_20260519_20260520T000902Z/` | FTA Final-300 raw per-example records | YES | CANONICAL |
| `outputs/final_fix24_all_external_postrun_20260520_20260520T025349Z/` | FTA postrun metrics, gate counts, CI, leakage scan | YES | CANONICAL |
| `outputs/current_research_evidence_summary_20260527/run_20260527T003000Z/` | Consolidated evidence summary | Supporting | CANONICAL |
| `outputs/repository_situation_and_scenario_ranking_20260527/run_20260527T010000Z/` | Scenario ranking and claim safety table | Supporting | CANONICAL |
| `outputs/job_d9_retrain_with_mistral_20260526/run_20260526T234411Z/` | D9 final retrain with 550 D6 pools | Supporting | CANONICAL |
| `outputs/job_d9_retrain_with_cohere_math500_expansion_20260526/run_20260526T144632Z/` | D9 retrain with 400 D6 pools (prior to Mistral) | Supporting | HISTORICAL |
| `outputs/job_cloudrift_qwen_extraction_repair_20260526/run_20260527T002012Z/` | Cloudrift/Qwen extraction repair audit | Supporting | CANONICAL |
| `outputs/job_d6_mistral_eval_20260526/run_20260526T232755Z/` | Mistral D6 standalone eval | Diagnostic | CANONICAL |
| `outputs/job_d8_1_runtime_feature_learning_selectors_20260526/run_20260526T014937Z/` | D8.1 learned selectors (test-split only) | Diagnostic (not independent) | NOT PROMOTED |
| `outputs/local_failure_workbench_20260525/` | Four-scenario failure workbench (Cohere/Mistral × GSM8K/MATH-500) | Diagnostic | SUPPORTING |
| `outputs/unified_learning_tables_20260525/run_20260525T184354Z/` | Unified candidate-action training table | Training data | SUPPORTING |
- Conditional-risk status (supportive, not replacement):
  - `CONDITIONAL_RISK_CAP_MANUSCRIPT_PROMOTION_DECISION_20260423T203259Z.md`
  - `CONDITIONAL_RISK_CAP_PROMOTION_DECISION_CONFIRMATION_20260423.md`
- Baseline fairness outcome: `MAIN_TABLE_EXTERNAL_BASELINE_FAIRNESS_AUDIT_20260423T205134Z.md`

## Paper-facing runners

- Primary: `../scripts/paper/run_all_neurips_paper_artifacts.py`
- Compatibility alias: `../scripts/paper/run_all_neurips_artifacts.py`

## Paper-facing output roots

- `../outputs/paper_plot_data/`
- `../outputs/paper_figures/`
- `../outputs/paper_tables/`

## Outputs orientation (non-authoritative index)

- Current organization guide: [`REPO_ORGANIZATION_GUIDE_20260501.md`](REPO_ORGANIZATION_GUIDE_20260501.md)
- Current selector artifact index: [`ARTIFACT_INDEX_20260501.md`](ARTIFACT_INDEX_20260501.md)
- Selector trace usability index: [`OUTPUTS_SELECTOR_TRACE_INDEX.md`](OUTPUTS_SELECTOR_TRACE_INDEX.md)
- Folder-level classes and OV rerank timestamp provenance: [`OUTPUTS_ARTIFACT_INDEX.md`](OUTPUTS_ARTIFACT_INDEX.md)
- Longer policy text: [`../outputs/README.md`](../outputs/README.md)

## Selector vs coverage roadmap

- Current selector choosing checklist: [`SELECTOR_CHOOSING_PLAYBOOK_20260501.md`](SELECTOR_CHOOSING_PLAYBOOK_20260501.md)
- Current focused selector front door: [`SELECTOR_WORK_START_HERE_20260501.md`](SELECTOR_WORK_START_HERE_20260501.md)
- Ordered plan (outcome verifier → PRM → pairwise → coverage-aware): [`SELECTOR_AND_COVERAGE_CONTROLLER_ROADMAP_20260429.md`](SELECTOR_AND_COVERAGE_CONTROLLER_ROADMAP_20260429.md)

## Guardrails

- Keep the `strict_f3` vs `strict_gate1_cap_k6` surface distinction explicit.
- Do not treat non-canonical output folders as headline evidence unless promoted by canonical docs.
- Preserve historical artifacts for provenance; demote/label rather than delete.
- For selector work, use existing candidate pools first, dry-run paid call counts, and cache every verifier score.
- Treat cache-limited selected-verifier external comparisons as diagnostic until missing selector scores are zero.
- Compare selector families only on matched paired slices when making headline claims.

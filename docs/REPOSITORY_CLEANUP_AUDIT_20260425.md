# Repository Cleanup Audit (2026-04-25)

## Scope and intent
This audit inventories repository structure and evidence classes for NeurIPS-style submission hygiene, without changing scientific conclusions, default method behavior, or canonical outputs.

## Top-level directory map (current)
- `.git/` — VCS metadata.
- `archive/` — historical scripts and deprecated utilities.
- `batch/` — Wulver batch entrypoints (`.sbatch`).
- `configs/` — configuration files and method settings.
- `datasets/` — dataset resources and local task assets.
- `docs/` — manuscript-facing and operational documentation.
- `experiments/` — experiment logic and reusable components.
- `external/` — external baseline integrations/adapters.
- `jobs/` — additional cluster launch scripts and job runbooks.
- `logs/` — run logs, notably `logs/slurm/` for Wulver evidence.
- `manuscript_integration/` — manuscript packaging/integration bundles.
- `outputs/` — generated artifacts (canonical, diagnostic, audit, and exploratory).
- `references/` — references and paper metadata.
- `scripts/` — executable experiment/report scripts.
- `tests/` — unit/integration regression checks.
- `theory/` — theoretical notes/material.

## Canonical artifact locations
### Canonical scripts (paper-facing)
- `scripts/paper/run_all_neurips_paper_artifacts.py`
- `scripts/run_broader_strict_phased_default_decision_eval.py`
- `scripts/run_paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3.py`
- `scripts/build_paper_facing_baseline_tables.py`

### Canonical manuscript-facing outputs
- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `outputs/paper_facing_baseline_tables/`
- `outputs/paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3/`

### Canonical documentation anchors
- `docs/PAPER_SOURCE_OF_TRUTH.md`
- `docs/CLAIM_BOUNDARIES.md`
- `docs/PAPER_ARTIFACT_MAP.md`
- `docs/RESULTS_GUIDE.md` (updated in this cleanup)

## Diagnostic/probe artifact locations
- Loss analysis and rich traces:
  - `outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG/`
  - `outputs/strict_f3_external_l1_max_rich_failure_traces_20260425T051500Z/`
  - `outputs/internal_methods_vs_external_l1_max_rich_failure_traces_20260425T054200Z/`
  - `outputs/cohere_gsm8k_strict_f3_vs_external_l1_max_diagnostic_20260425T235500Z/`
- Probe variants and controlled diagnostics:
  - `outputs/case_split_direction_aware_offline_eval_20260425T120000Z/`
  - `docs/SHALLOW_EXHAUSTIVE_PROBE_REPORT_20260425T_*.md`
  - `docs/DIRECTION_COMBINATORICS_GUARD_EVAL_20260425T_*.md`
  - `docs/TYPED_STRATEGY_SEEDED_EVAL_20260425T_*.md`
  - `docs/FAMILY_NORMALIZED_RERANK_EVAL_20260425T_*.md`

## Wulver batch files and job orchestration
### `batch/`
- `batch/run_wulver_cohere_nonmath_external_validity_audit.sbatch`
- `batch/run_wulver_cohere_strict_f3_vs_external_l1_max_long.sbatch`
- `batch/run_wulver_offline_submission_audit.sbatch`

### `jobs/` (selected high-signal)
- `jobs/paper_main_numeric_results_bundle_wulver.sbatch`
- `jobs/openai_real_model_main_20260424.sbatch`
- `jobs/cohere_real_model_main_20260424.sbatch`
- `jobs/run_missing_openai_real_model_main_slices_20260424T163922Z.sbatch`
- `jobs/run_missing_cohere_real_model_main_slices_20260424T163922Z.sbatch`

## Generated reports, logs, tests, configs, docs
- Generated reports: dense set in `docs/` and `docs/reports/` (timestamped status/evidence reports).
- Logs: `logs/slurm/*.out|*.err` are retained evidence for cluster executions.
- Tests: `tests/` includes canonical and diagnostic checks; key tests include ten-case deep dive, family-normalized rerank, typed-strategy seeded, and direction-combinatorics guard.
- Configs: `configs/` stores reusable experiment parameters.
- Documentation: `docs/` contains both canonical and exploratory material; currently high-volume and timestamp-heavy.

## Potentially stale or duplicate files (do not use for claims unless explicitly promoted)
- Placeholder/future-dated claim-safety docs:
  - `docs/HELD_OUT_SURFACE_GENERALIZATION_CLAIM_SAFETY_20990101T000000Z.md`
  - `docs/HELD_OUT_SURFACE_GENERALIZATION_CLAIM_SAFETY_20990101T000001Z.md`
- Patch/variant duplications for real-model validation docs where base and patch documents coexist (use only the explicitly promoted canonical set in `RESULTS_GUIDE.md`).
- Multiple timestamped status notes that summarize the same experiment family should be treated as history/provenance unless referenced by canonical source-of-truth docs.

## Files that should NOT be used for paper claims
- Dry-run/smoke/diagnostic artifacts (names containing `DRY`, `SMOKE`, `TEST_DRY`, `diagnostic`) unless explicitly cited as diagnostics.
- Exploratory variant reports for unpromoted methods.
- Partial or blocked external baseline integration notes.
- Operational logs without paired claim-safe aggregation.

## Files safe as paper-facing evidence
- Outputs from `outputs/paper_tables/`, `outputs/paper_plot_data/`, `outputs/paper_figures/`.
- Promoted method/baseline tables in manuscript-facing bundles.
- Canonical fairness/contract reports when referenced by source-of-truth docs.
- Claim boundary and artifact map documents that define permissible claim language.

## Missing documentation / clarity gaps
- A concise single-page reproduction checklist for new reviewers (added in this cleanup: `docs/REPRODUCTION_CHECKLIST.md`).
- A consolidated conservative claims file scoped specifically for NeurIPS 2026 wording (added: `docs/SAFE_CLAIMS_FOR_NEURIPS_2026.md`).
- Sharper segregation of canonical vs diagnostic outputs in one front-door guide (updated: `docs/RESULTS_GUIDE.md`, `README.md`).

## Recommended organization changes
1. Keep canonical evidence in stable paths and reference only those paths for manuscript tables/figures.
2. Label diagnostic families consistently as diagnostic/stress-test artifacts.
3. Route transient local files into dated archive directories only when clearly duplicate/temp and non-canonical.
4. Continue preserving Wulver logs for reproducibility and auditability.
5. Keep claims synchronized with conservative claim-boundary docs before manuscript updates.

## Cleanup moves performed in this pass
- No output files were moved in this pass.
- Reason: no clearly duplicate/transient files were identified that could be moved without risk to references or reproducibility.

# Repository start paths

This guide gives the shortest reliable entry path depending on what you are trying to do.

## Project identity in one sentence

The repository’s canonical direction is **fixed-budget cross-controller frontier allocation for LLM reasoning**, centered on **which active branch should receive the next unit of compute**.

This repository is **not** centered on the old binary revise-routing manuscript.

## Start here by goal

### 1. I want the fastest correct overview
Read in this order:
1. [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
2. [`CURRENT_PROJECT_STATUS.md`](CURRENT_PROJECT_STATUS.md)
3. [`CURRENT_BOTTLENECKS.md`](CURRENT_BOTTLENECKS.md)
4. [`CURRENT_SAFE_CLAIMS.md`](CURRENT_SAFE_CLAIMS.md)
5. [`PAPER_POSITIONING_NOTE.md`](PAPER_POSITIONING_NOTE.md)
6. [`REPO_MAP.md`](REPO_MAP.md)

### 2. I want to understand the current method and where it is weak
Read next:
1. [`CURRENT_METHOD_SUMMARY_AND_GAPS.md`](CURRENT_METHOD_SUMMARY_AND_GAPS.md)
2. [`WHAT_IS_NOT_WORKING_NOW.md`](WHAT_IS_NOT_WORKING_NOW.md)
3. [`HARD_PAIR_SUPERVISION_CLEANUP_NEXT_STEP.md`](HARD_PAIR_SUPERVISION_CLEANUP_NEXT_STEP.md)
4. [`STRUCTURED_AMBIGUITY_STATUS_2026_04_18.md`](STRUCTURED_AMBIGUITY_STATUS_2026_04_18.md)
5. [`REPOSITORY_AUDIT_AND_NEXT_STEP_2026_04_18.md`](REPOSITORY_AUDIT_AND_NEXT_STEP_2026_04_18.md)

### 3. I want to run the current code path
Start with:
1. [`../scripts/CANONICAL_START_HERE.md`](../scripts/CANONICAL_START_HERE.md)
2. [`../scripts/README.md`](../scripts/README.md)
3. [`REPO_MAP.md`](REPO_MAP.md)

### 4. I want to understand evaluation and baselines
Read:
1. [`EVALUATION_AND_BASELINES_INDEX.md`](EVALUATION_AND_BASELINES_INDEX.md)
2. [`CURRENT_SAFE_CLAIMS.md`](CURRENT_SAFE_CLAIMS.md)
3. [`OUTPUTS_INTERPRETATION_GUIDE.md`](OUTPUTS_INTERPRETATION_GUIDE.md)
4. [`external_baseline_completeness_report.md`](external_baseline_completeness_report.md)

### 5. I want to understand the hard ambiguous-case line
Read:
1. [`HARD_CASE_FEATURE_REPRESENTATION_STATUS.md`](HARD_CASE_FEATURE_REPRESENTATION_STATUS.md)
2. [`NEAR_TIE_POINTWISE_EXPERT_STATUS.md`](NEAR_TIE_POINTWISE_EXPERT_STATUS.md)
3. [`STRICT_COUPLED_TIE_AWARE_POSTHOC_DEFERRAL_STATUS.md`](STRICT_COUPLED_TIE_AWARE_POSTHOC_DEFERRAL_STATUS.md)
4. [`STRICT_COUPLED_TIE_AWARE_LEARNED_TWO_STAGE_DEFERRAL_STATUS.md`](STRICT_COUPLED_TIE_AWARE_LEARNED_TWO_STAGE_DEFERRAL_STATUS.md)
5. [`LEARNED_TWO_STAGE_DEFERRAL_CALIBRATION_POLICY_STATUS.md`](LEARNED_TWO_STAGE_DEFERRAL_CALIBRATION_POLICY_STATUS.md)
6. [`STRUCTURED_AMBIGUITY_STATUS_2026_04_18.md`](STRUCTURED_AMBIGUITY_STATUS_2026_04_18.md)

### 6. I want to interpret outputs quickly
Use:
- [`OUTPUTS_INTERPRETATION_GUIDE.md`](OUTPUTS_INTERPRETATION_GUIDE.md)
- [`ASSET_AUDIT_AND_WORKING_SET_2026_04_17.md`](ASSET_AUDIT_AND_WORKING_SET_2026_04_17.md)

## Directory-level interpretation

- `docs/`: canonical interpretation, planning notes, grouped navigation pages, exploratory notes, and historical guidance.
- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact result notes.
- `configs/`: dataset, baseline, and experiment configuration files.
- `datasets/`: dataset-policy and dataset-readiness assets.
- `external/`: external baseline references and integration notes.
- `outputs/`: generated artifacts and paper-support outputs.
- `archive/`: provenance-only historical material.

## Interpretation rules

- Use **canonical docs** for the current project identity and paper planning.
- Use **exploratory notes** for active but non-default method lines.
- Use **historical material** only for provenance.

See also:
- [`README.md`](README.md)
- [`../README.md`](../README.md)
- [`EXPLORATORY_INDEX.md`](EXPLORATORY_INDEX.md)
- [`HISTORICAL_AND_ARCHIVE_POLICY.md`](HISTORICAL_AND_ARCHIVE_POLICY.md)

# Repository start paths

This guide gives the shortest reliable entry path depending on what you are trying to do.

## Project identity in one sentence

The repository’s canonical direction is **fixed-budget branch allocation for LLM reasoning**, centered on **which active branch should receive the next unit of compute and how to keep answer-distinct alternatives alive long enough to matter**.

This repository is **not** centered on the old binary revise-routing manuscript.

## Start here by goal

### 1. I want the fastest correct overview
Read in this order:
1. [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
2. [`CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`](CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md)
3. [`CURRENT_PROJECT_STATUS.md`](CURRENT_PROJECT_STATUS.md)
4. [`CURRENT_BOTTLENECKS.md`](CURRENT_BOTTLENECKS.md)
5. [`CURRENT_SAFE_CLAIMS.md`](CURRENT_SAFE_CLAIMS.md)
6. [`REPO_MAP.md`](REPO_MAP.md)

### 2. I want to understand the current method and where it is weak
Read next:
1. [`CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`](CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md)
2. [`CURRENT_METHOD_SUMMARY_AND_GAPS.md`](CURRENT_METHOD_SUMMARY_AND_GAPS.md)
3. [`WHAT_IS_NOT_WORKING_NOW.md`](WHAT_IS_NOT_WORKING_NOW.md)
4. [`TWENTY_DEFEAT_CASES_WITH_BRANCH_REASONING_2026_04_19.md`](TWENTY_DEFEAT_CASES_WITH_BRANCH_REASONING_2026_04_19.md)
5. [`TWENTY_DEFEAT_CASES_WITH_DISCOVERED_TREES_2026_04_19.md`](TWENTY_DEFEAT_CASES_WITH_DISCOVERED_TREES_2026_04_19.md)

### 3. I want to run the current code path
Start with:
1. [`../scripts/CANONICAL_START_HERE.md`](../scripts/CANONICAL_START_HERE.md)
2. [`../scripts/README.md`](../scripts/README.md)
3. [`REPO_MAP.md`](REPO_MAP.md)

### 4. I want to understand evaluation and baselines
Read:
1. [`EVALUATION_AND_BASELINES_INDEX.md`](EVALUATION_AND_BASELINES_INDEX.md)
2. [`FULL_METHOD_COMPARISON_STATUS_2026_04_18.md`](FULL_METHOD_COMPARISON_STATUS_2026_04_18.md)
3. [`CURRENT_SAFE_CLAIMS.md`](CURRENT_SAFE_CLAIMS.md)
4. [`OUTPUTS_INTERPRETATION_GUIDE.md`](OUTPUTS_INTERPRETATION_GUIDE.md)

### 5. I want to understand the current failure-analysis stack
Read:
1. [`TWENTY_DEFEAT_CASES_WITH_BRANCH_REASONING_2026_04_19.md`](TWENTY_DEFEAT_CASES_WITH_BRANCH_REASONING_2026_04_19.md)
2. [`TWENTY_DEFEAT_CASES_WITH_DISCOVERED_TREES_2026_04_19.md`](TWENTY_DEFEAT_CASES_WITH_DISCOVERED_TREES_2026_04_19.md)
3. [`WORST_REAL_FAILURE_CASEBOOK_WITH_REASONING_20260418.md`](WORST_REAL_FAILURE_CASEBOOK_WITH_REASONING_20260418.md)
4. [`FINAL_ANSWER_RECOVERY_STATUS_2026_04_18.md`](FINAL_ANSWER_RECOVERY_STATUS_2026_04_18.md)

### 6. I want to interpret outputs quickly
Use:
- [`OUTPUTS_INTERPRETATION_GUIDE.md`](OUTPUTS_INTERPRETATION_GUIDE.md)
- [`ASSET_AUDIT_AND_WORKING_SET_2026_04_17.md`](ASSET_AUDIT_AND_WORKING_SET_2026_04_17.md)
- `../outputs/repository_audit/repository_audit_summary_2026_04_18.json`

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

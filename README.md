# Adaptive Reasoning Budget Allocation (Anonymous NeurIPS 2026 Repository)

This repository studies **frontier allocation for budgeted LLM inference** under explicit compute/action-budget contracts.

## Project goal
Build and evaluate methods that allocate limited reasoning budget more effectively than fixed or naive allocation policies, while preserving transparent, reproducible evidence boundaries.

## Method family (high-level)
- Frontier-aware allocation/controller methods.
- Matched-budget internal comparisons (`strict_f3`, `strict_gate1_cap_k6`, related variants).
- External adapter baselines under documented contract/fairness checks.
- Diagnostic variants for failure analysis (not automatically canonical).

## Current main result status
- Canonical manuscript-facing evidence is generated into:
  - `outputs/paper_tables/`
  - `outputs/paper_plot_data/`
  - `outputs/paper_figures/`
- These are the primary sources for paper claims.
- Surface distinction for claim safety:
  - manuscript-facing matched-surface representative: `strict_f3`
  - broader operational default on a different surface: `strict_gate1_cap_k6`
  - their margin on matched-surface slices is fragile/non-decisive unless explicitly supported by canonical statistical evidence.

## Reproduce canonical outputs (local, no external API required)
```bash
python scripts/check_repo_health.py
python -m pytest
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## Inspect real-model validation (diagnostic/supporting)
- OpenAI/Cohere validation artifacts live under:
  - `outputs/real_model_ours_vs_external_validation_20260424T_OPENAI_REAL_MAIN/`
  - `outputs/real_model_ours_vs_external_validation_20260424T_COHERE_REAL_MAIN/`
  - `outputs/real_model_ours_vs_external_validation_20260425T_WULVER_COHERE_LONG/`
- Treat these as diagnostic/stress-test evidence unless explicitly promoted for a bounded claim.

## Inspect failure diagnostics
- Detailed loss-case analysis and deep-dive packages are documented in:
  - `docs/DETAILED_LOSS_CASE_ANALYSIS_20260425T_WULVER_COHERE_LONG_DETAIL.md`
  - `docs/TEN_CASE_LOSS_DEEP_DIVE_20260425T221500Z.md`

## Safe-claims policy
Before writing manuscript text, read:
- `docs/SAFE_CLAIMS_FOR_NEURIPS_2026.md`
- `docs/RESULTS_GUIDE.md`
- `docs/PAPER_SOURCE_OF_TRUTH.md`
- `docs/CLAIM_BOUNDARIES_CURRENT.md`
- `docs/PAPER_ARTIFACTS_README.md`
- `docs/REVIEWER_REPRO_AND_SCOPE_GUIDE.md`

## Anonymous supplement

- Anonymous reviewer package source: `neurips2026_anonymous_artifact/`
- Packaging/build path: `scripts/create_anonymous_neurips_artifact.py`
- Keep canonical paper-facing and diagnostic artifacts explicitly separated when preparing anonymous releases.

## Repository organization and artifact classes
For a reviewer-safe map of canonical, diagnostic, and provenance artifacts, see:
- `docs/RESULTS_AND_ARTIFACTS_GUIDE.md`
- `docs/METHOD_AND_VARIANT_MAP.md`
- `docs/DIRECT_RESERVE_LEARNED_SCORER_STATUS.md`
- `docs/NONMATH_FAILURE_DIAGNOSIS_AND_ROADMAP.md`
- `docs/IDEAS_AND_REFERENCES_FOR_FUTURE_WORK.md`

## Tests
Run focused local checks:
```bash
python -m pytest tests/test_ten_case_loss_deep_dive.py \
  tests/test_family_normalized_rerank.py \
  tests/test_typed_strategy_seeded.py \
  tests/test_direction_combinatorics_guard.py

# Artifact-dependent integration checks (require generated package):
python -m pytest tests/test_family_normalized_rerank.py::test_smoke_runner_outputs_and_ablation \
  tests/test_typed_strategy_seeded.py::test_dry_run_and_outputs_exist \
  tests/test_direction_combinatorics_guard.py::test_dry_run_completes_without_api_keys
```

## What not to claim yet
- Do **not** claim robust/universal superiority over external baselines.
- Do **not** present diagnostic variants as final methods unless validated and promoted.
- Do **not** assume historical runs have complete trace coverage.

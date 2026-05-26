# Current Learning and D6 Status (2026-05-25)

This note is a concise handoff for current no-API learning status and D6 readiness.

## Guardrails and evidence boundaries
- Use corrected fixed-policy baselines only for comparisons.
- Do not use row-wise max over correctness as a baseline (that is oracle-like and forbidden).
- Oracle metrics are upper bounds only.
- Current canonical promoted policy remains FIX-2+FIX-4 as documented in `docs/LATEST_RESULTS_AND_CLAIMS.md`.

## D6 status
- D6 pilot preparation is complete and captured under:
  - `outputs/job_d6_frontier_improvement_pilot_20260525/run_20260525T213951Z`
- D6 remains `prepared_not_run` / `FIX_FIRST`.
- `scripts/d6_generate_frontier_variants.py` is still a guarded placeholder and does not implement generation output/log handling.
- `scripts/d6_evaluate_frontier_variants.py` is still a placeholder and does not implement corrected-baseline evaluation.
- No API generation should run until those blockers are implemented and re-audited.

## D8 status
- D8 fold-safe learning iteration completed at:
  - `outputs/job_d8_foldsafe_learning_selectors_20260525/run_20260525T221353Z`
- Best current D8 variant: D8A (xgboost calibrated).
- Clean-test W/T/L vs best corrected fixed baseline: `3/1/0`.
- Manual review verdict: `D8_NEEDS_FEATURE_UPGRADE` and `not_promotable_global`.
- D8A should be treated as module-level/use-case-limited evidence, not global replacement.

## Bottlenecks and next direction
- MATH-500 is still the main bottleneck, especially `cohere_math500` and `cloudrift_math500` slices.
- Learning readiness remains partial (`LEARNING_PARTIAL_READY_NEEDS_FEATURES`): next learning upgrades should emphasize stronger runtime-visible features and split-safe evaluation.
- Priority sequence:
  1. Fix D6 generation/evaluation script blockers.
  2. Continue D8.1 feature-schema upgrades (runtime-visible only).
  3. Build scenario-defeat matrix toward journal target (best method above best corrected external baseline in each provider/API × dataset scenario).

## Runtime-algorithm wording boundary
- Describe the algorithm as adapting to provider/API, instance-level signals, and candidate-pool structure at runtime.
- Do not describe it as using raw test labels at runtime.

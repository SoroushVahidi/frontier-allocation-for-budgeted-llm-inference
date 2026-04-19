# Diversity-needed gate bounded comparison status (2026-04-19)

## Scope
This pass is strictly a bounded integration test inside the current broad diversity/aggregation family:
- base: `broad_diversity_aggregation_strong_v1`
- gated: `broad_diversity_aggregation_strong_v1_diversity_needed_gate`
- optional easy baseline: `broad_diversity_aggregation_strong_v1_heuristic_gate`

No new controller family was introduced.

## Matched run
- datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`
- seeds: `11, 23`
- budgets: `6, 8`
- matched comparisons: 240 example-level base-vs-gated pairs
- artifact root: `outputs/diversity_needed_gate_bounded_comparison_20260419/`

## Key evidence
- mean accuracy: base `0.6917`, gated `0.6750` (delta `-0.0167`)
- near-tie slice accuracy: base `0.4545`, gated `0.5185` (local improvement)
- improved/harmed/unchanged: `51 / 55 / 134`
- gate interventions: 563 action-level interventions across 207 matched cases
- intervention success rate (improved among intervened cases): `0.217`

## Failure pattern shift
- `insufficient_diversity_realized`: base `53` -> gated `6` (large reduction)
- `aggregation_instability`: base `19` -> gated `66` (large increase)
- `commit_timing`: base `1` -> gated `4`

Interpretation: the gate pushes diversity effectively, but current thresholds/decision coupling over-trigger diversity and increase downstream aggregation instability.

## Explicit decision
- **Is the diversity-needed predictor useful enough to justify another pass?**
  - **Yes, but only one deeper bounded pass.** The near-tie and insufficient-diversity behavior moved in the expected direction.
- **Diagnostic-only vs serious integration candidate now?**
  - **Still not a serious integration candidate yet.** Overall accuracy regressed and harms roughly match gains.
- **Best next step**
  - run one narrow threshold-coupling pass that reduces positive gate pressure and tightens fallback/commit coupling,
  - target specifically: preserve insufficient-diversity reduction while recovering aggregation stability.


# Faithful Baseline Implementation Plan

## Implemented in this change
- Added new non-destructive faithful/fair IDs:
  - `external_s1_budget_forcing_faithful_v1`
  - `external_tale_ep_prompt_budgeting_faithful_v1`
  - `external_l1_max_fair_v1`
- Kept old IDs unchanged and still registered:
  - `external_s1_budget_forcing`, `external_tale_prompt_budgeting`, `external_l1_max`
- Added faithful metadata fields in controllers.
- Registered new IDs in both runtime strategy registry and validation script method registry.

## Faithfulness status after implementation
- S1 faithful v1: closer behavior-level match (continuation cue + ignore-stop controls + explicit deviations metadata).
- TALE-EP faithful v1: closer EP adapter (explicit budget prompt template and estimator metadata), still not TALE-PT reproduction.
- L1 max fair v1: transparent fair comparator with explicit non-official flag.

## Known deviations still present
- S1: action-budget/branch-level control differs from official token-level serving + official checkpoint stack.
- TALE-EP: heuristic estimator and local harness; TALE-PT not implemented.
- L1 fair: not official external reproduction path.

## Safe claim wording after this implementation (before rerun)
- "our implemented faithful S1-style, TALE-EP-style, and fair L1-style baselines"
- still avoid "official baseline reproduction" wording.

## What remains partial / requires rerun
- Need rerun baseline comparisons using new IDs to update result tables.
- Need manual TALE official repo verification (template/estimator/inference commands) for stronger claims.

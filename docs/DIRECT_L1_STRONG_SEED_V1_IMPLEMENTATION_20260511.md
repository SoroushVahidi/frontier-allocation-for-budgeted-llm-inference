# Direct L1 Strong Seed v1 (Opt-In) Implementation (2026-05-11)

## Goal

Implement an **opt-in** stronger Direct L1 seed variant to target the dominant PAL unresolved bottleneck:

- Gold absent from the candidate pool.
- Frontier collapse / low diversity (often single answer-group collapse).
- Weak or wrong direct seed causing the wrong group to dominate early.

This change is **not** a runtime default change. It introduces a new method ID only.

## Evidence / Motivation (Artifacts Only)

From the merged recovery-coverage and PAL-157 audits (see [docs/PAL_157_DEEP_PATTERN_MINING_20260511.md](/home/soroush/frontier-allocation-for-budgeted-llm-inference/docs/PAL_157_DEEP_PATTERN_MINING_20260511.md) and [docs/DIRECT_L1_SEED_STRENGTHENING_PREFLIGHT_20260511.md](/home/soroush/frontier-allocation-for-budgeted-llm-inference/docs/DIRECT_L1_SEED_STRENGTHENING_PREFLIGHT_20260511.md)):

- PAL unresolved covered cases: `157`.
- `direct_seed_wrong_or_missing`: `155/157`.
- `direct_l1_anchor_potential`: `43/157`.
- `direct_l1_patch_effect_match`: `18/157`.
- Best scored candidate fix: `stronger_direct_l1_seed_with_independent_arithmetic_unit_self_check`.

## Method ID

New opt-in method ID:

`direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_l1_strong_seed_v1`

## Behavior Change

This method reuses the existing **guarded K1 frontier4 + frontier tiebreak** controller and the existing **direct-hybrid seed mechanism**, but changes the **prompt style used for the direct-hybrid (Direct L1) seed call**.

Prompt behavior for the seed call:

1. State exactly what quantity the problem asks for (with units if applicable).
2. Compute the answer directly.
3. Independently self-check the arithmetic and unit consistency using a different computation path.
4. If the check disagrees, fix the solution.
5. Output only the final numeric answer in `\boxed{}`.

All other method behavior is unchanged relative to the baseline controller configuration.

## No Runtime Default Change

- No existing method ID is modified to use this prompt.
- No default method selection is changed.
- The baseline `..._direct_hybrid` and `..._diverse_anchor` method IDs retain their prior behavior.

## No Paid / Model API Calls

This implementation is no-API and is validated with registry/prompt wiring tests and exact-case validate-only mode.

## Validation Ladder (No-API Only)

1. Method registry resolution (no API): focused pytest for the new method.
2. Exact-case JSONL loader validation (no API): ensure the 15-case slice loads deterministically.
3. Validate-only call-plan / method-resolution check (no API):
   `python3 scripts/run_cohere_real_model_cost_normalized_validation.py --validate-exact-cases-only ...`

Optional future step (requires explicit approval, not done here):

- Live 15-case diagnostic run for this method ID.

## Exact-Case Diagnostic Slice (15)

Tracked exact-case JSONL:

[docs/project_handoff_20260510/exact_case_replay/direct_l1_strong_seed_15case_exact_cases_20260511.jsonl](/home/soroush/frontier-allocation-for-budgeted-llm-inference/docs/project_handoff_20260510/exact_case_replay/direct_l1_strong_seed_15case_exact_cases_20260511.jsonl)

## Scope Notes

- This doc makes no external-baseline claim.
- Missing coverage in other methods (e.g., uncertainty-retry variants) is not treated as failure.

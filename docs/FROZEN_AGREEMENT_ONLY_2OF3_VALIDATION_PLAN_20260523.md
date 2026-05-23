# FROZEN_AGREEMENT_ONLY_2OF3_VALIDATION_PLAN_20260523

## Status
- Policy candidate: `agreement_only_2of3_against_frontier`
- State: **frozen for validation** (not promoted)
- Date frozen: 2026-05-23
- API usage in this phase: **none**

## Frozen Policy Definition
For each example:
1. Start from frontier answer.
2. Normalize frontier/L1/S1/TALE answers with repository canonicalization (`experiments.support_aware_selector._normalize_answer`).
3. If any external answer is missing or unparseable: keep frontier (conservative).
4. If at least 2 of 3 externals agree on normalized answer `A` and `A != frontier_normalized`: defer to `A`.
5. Otherwise keep frontier.

Implementation:
- `experiments/support_aware_selector.py`: `agreement_only_2of3_against_frontier`
- Unit tests: `tests/test_support_aware_selector.py`

Policy metadata contract:
- `deferred`
- `agreement_pattern`
- `selected_action`
- `selected_source`
- `external_majority_answer`
- `reason`

## Runtime-Legal Inputs
Allowed runtime inputs:
- `frontier_answer`
- `l1_answer`
- `s1_answer`
- `tale_answer`

Explicitly excluded runtime inputs:
- `gold_answer`, `gold_answer_canonical`
- `exact_match`, correctness flags
- `example_id`
- artifact paths / run provenance fields

## Offline Reproduction Gate (Must Pass Before Live API)
Replayed with:
- `scripts/replay_agreement_only_2of3_against_frontier.py`

Required checkpoints and observed results:
- GSM8K aggregate-720: expected `591/720 = 82.08%`, observed `591/720 = 0.8208`
- MATH-500 complete-case: expected `147/488 = 30.12%`, observed `147/488 = 0.3012`

Result: **reproduced exactly**.

## Validation Datasets and Budget
Planned live validation settings:
- Provider: Cohere
- Budget: `B=6` (fixed, matched with existing evidence)
- Methods generated:
  - `direct_reserve_semantic_frontier_v2`
  - `external_l1_max`
  - `external_s1_budget_forcing`
  - `external_tale_prompt_budgeting`

Execution order:
1. Run 1 (first): GSM8K unbiased 300-case validation (`seed=71`, `n=300`).
2. Run 2: MATH-500 full 500-case validation (`seed=11`, `n=500`) with completeness hardening.

Rationale for order:
- Fast confirmation on established GSM slice before spending larger MATH budget.
- MATH run has known incompleteness risk from transient provider failures; run after hardening checks.

## Sample Selection Protocol (Frozen)
- Use exact seed/dataset protocol in `proposed_validation_runs.json`.
- Prefer exact-case manifest protocol (`--exact-cases-jsonl`) for deterministic example identity.
- No policy tuning or tie-order changes after run start.

## Required Logged Fields for Replay
Per-example records must include:
- run identity: `dataset`, `seed`, `budget`, `method`, `example_id`, `status`, `error`
- answer fields: `final_answer_canonical`, `selected_answer_canonical`, `final_answer_raw`
- eval fields (offline only): `gold_answer_canonical`, `exact_match`
- frontier metadata: `result_metadata.override_reason`, `result_metadata.frontier_support`, `result_metadata.candidate_pool_answer_group_count`, `result_metadata.support_margin`, `result_metadata.direct_frontier_agree`
- API/cost diagnostics: `cohere_logical_api_calls`, `retry_attempts`

## Completion Criteria (Before Looking at Deltas)
- All four methods scored for every selected example.
- Zero missing per-method rows in selected slice.
- Zero policy fallbacks due to missing answers.
- Replay fields sufficient for both old FTA (`FIX-2+FIX-4`) and frozen agreement-only policy.

## Metrics and Statistical Tests
Primary metrics:
- Accuracy
- Delta vs frontier / L1 / pooled4
- Deferral rate
- Recoveries / regressions / net gain vs frontier
- Win/loss/tie vs current FTA and vs L1
- Oracle regret over fixed 4-answer pool

Statistical tests:
- Paired bootstrap 95% CI for policy deltas vs current FTA, L1, pooled4.
- Report wins/losses/ties alongside CIs.

Current offline paired CI snapshot (for reference, not promotion evidence):
- GSM8K vs current FTA: delta `+1.39pp`, CI `[-0.14, +2.92]`
- MATH complete-case vs current FTA: delta `+2.46pp`, CI `[+0.20, +4.92]`
- Combined vs current FTA: delta `+1.82pp`, CI `[+0.50, +3.15]`

## Promotion / Failure Criteria
Promotion-justifying result (minimum):
- Complete slices only.
- Policy >= current FTA on GSM8K with non-negative paired delta point estimate and no major regression concentration.
- Policy improves MATH point estimate vs current FTA on completed full slice.
- Claim wording remains bounded if CIs include zero.

Failure criteria:
- Incomplete slices or missing method rows.
- Reproduction mismatch vs frozen offline checkpoints.
- Material regression on GSM8K vs current FTA with no compensating evidence.

## Risks and Required Pre-Live Changes
Known risk for MATH incompleteness:
- Prior MATH runs had transient Cohere HTTP 500 and read timeout failures, leaving slices below target (e.g., frontier 484/500).

Required script/process changes before paid execution:
1. `run_cohere_real_model_cost_normalized_validation.py`: bypass provider readiness API probe when `--dry-run-call-plan` is set (today it still performs readiness call).
2. Add stronger retry/backoff + failure recovery queue to reach `target_scored_per_slice` despite transient HTTP 500/timeouts.
3. Emit automatic failure taxonomy summary from `raw/failures.jsonl` for quick stop/go decisions.

## API Call Plan (Dry-Run Estimate, No API Calls)
See `outputs/frozen_agreement_only_2of3_validation_plan_20260523/api_call_plan_dryrun.json`.

Headline estimates:
- Run 1 (GSM8K n=300): ~`1485` logical calls (historical mean-based), conservative bound `7200`.
- Run 2 (MATH n=500): ~`5222` logical calls (historical mean-based), conservative bound `12000`.
- Combined estimate (runs 1+2): ~`6707` logical calls.

## Claim-Safety Pre-Registration Boundary
- This policy is a **frozen validation candidate** only.
- No policy tuning after seeing validation outcomes.
- No post-hoc rule edits, threshold edits, or tie-order changes within this validation cycle.
- Live-run claims must remain within completed-slice evidence.

## Planned Outputs From Future Live Run
- Full artifact dir with:
  - `manifest.json`
  - `per_example_records.jsonl`
  - `slice_summary.csv`
  - `incomplete_slices.csv`
  - `pairwise_comparisons.csv`
  - replay package for frozen policy decisions and paired CIs

## Existing Script Suitability
Best existing generator script:
- `scripts/run_cohere_real_model_cost_normalized_validation.py`

Offline replay/verification script added in this task:
- `scripts/replay_agreement_only_2of3_against_frontier.py`

Repository live-readiness verdict:
- **Conditionally ready** after pre-live changes listed above; generation/replay path exists, but dry-run and MATH completeness hardening should be addressed first.

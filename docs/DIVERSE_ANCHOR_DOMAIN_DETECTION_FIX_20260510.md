# Diverse-Anchor Domain Detection Fix (2026-05-10)

## Bug Observed
In the exact-case 30-case Cohere diagnostic (failure-recovery slice with 10 money, 10 ratio, 10 multi-step cases), the domain-aware diverse-anchor priority mechanism did **not** activate for the ratio and multi-step slices:
- money/cost/revenue: detected correctly
- ratio/proportion/percentage: detected as `unknown`
- multi-step arithmetic: detected as `unknown`

Because `budget=4` only allows two non-direct anchors, and `unknown` falls back to the default ordering, the run still executed:
- `direct_l1_anchor`
- `equation_first_anchor`
- `unit_ledger_money_anchor`

and still skipped:
- `ratio_percentage_anchor`
- `backward_check_anchor`

## Root Cause
Domain detection was based on a lightweight heuristic over the raw `question` string. For this exact-case set, many ratio/multi-step questions did not trigger the heuristic patterns reliably, so they fell into `unknown`.

## Fix
### 1) Prefer exact-case metadata when available
When running `scripts/run_cohere_real_model_cost_normalized_validation.py` in `--exact-cases-jsonl` mode, we now attach the per-example JSONL row to the controller instance:
- `controller.current_example_id`
- `controller.current_exact_case_metadata`

`detect_problem_domain_hint_with_source()` checks `current_exact_case_metadata["failure_domain"]` (when present) and maps it to:
- `money_cost_revenue`
- `ratio_percent`
- `multi_step_arithmetic`

This makes the domain-aware prioritization deterministic for exact-case diagnostics.

### 2) Improve heuristic fallback (non-exact-case usage)
When explicit metadata is not available, heuristics are broadened for:
- ratio terms (ratio/proportion/percent/percentage/fraction/half/third/quarter/twice/triple/out of/share/per)
- multi-step terms (then/after/before/altogether/remaining/left/combined/first/second/bought/sold/gave/received/added/subtracted), gated by presence of digits

### 3) New metadata fields for auditability
Controller per-example metadata now includes:
- `detected_problem_domain`
- `domain_detection_source`: `exact_case_metadata` | `heuristic` | `unknown`
- `domain_detection_evidence`: short string explaining what matched

## Expected Outcome
For the failure-recovery exact-case JSONL (10 money, 10 ratio, 10 multi-step):
- money cases → `money_cost_revenue`
- ratio cases → `ratio_percent`
- multi-step cases → `multi_step_arithmetic`

So under `budget=4`, the two non-direct anchors should now execute as:
- money: `unit_ledger_money_anchor`, `equation_first_anchor`
- ratio: `ratio_percentage_anchor`, `equation_first_anchor`
- multi-step: `equation_first_anchor`, `backward_check_anchor`

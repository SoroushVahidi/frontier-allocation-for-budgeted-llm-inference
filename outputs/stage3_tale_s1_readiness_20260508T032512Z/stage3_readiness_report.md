# Stage-3 TALE/S1 Readiness Report

## Artifacts found
- Reusable 4-way external baseline artifact exists: `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/all_casebook.csv` (245 cases; includes PAL, external_l1_max, TALE, S1, best_external fields).
- Companion method-row provenance exists in `.../per_example_records.jsonl`.
- Smaller 30-case 4-way pilot exists, but lower power.

## Recommended Stage-3 case set
- **Option A**: existing 245-complete 4-way collection (from the 247 run; two incomplete on external_l1 only).
- Reason: full reusable TALE/S1/L1 outputs + gold/problem text + best_external labels without new external calls.

## Reuse vs new calls
- Reuse external baselines: **yes** (TALE/S1/external_l1/best_external from casebook).
- New calls needed: integrated validated-fixes method only, estimated **245**.
- Estimated external baseline calls: **0**.

## Runner support / dry-run
- Existing runner supports TALE/S1/external methods and dry-run call-plan flags.
- Missing support: direct replay of precomputed external outputs + custom validated-fixes alias not yet first-class in runner.
- Minimal changes recommended in manifest before live Stage-3 run.

## Proposed commands
- Dry-run call plan (no API):
  `python scripts/run_cohere_real_model_cost_normalized_validation.py --providers cohere --datasets openai/gsm8k --budgets 6 --seeds 20260501 --methods direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_targeted_retry_v1,external_l1_max,external_tale_prompt_budgeting,external_s1_budget_forcing --allowed-example-ids-file outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/selected_failure_cases.jsonl --dry-run-call-plan --output-root outputs --timestamp 20260508T032512Z`
- Live Stage-3 should be deferred until replay-or-alias support is finalized.

## Claim boundaries
- This readiness package is no-API and provenance-only.
- It does not claim Stage-3 performance without running integrated predictions on the recommended case set.

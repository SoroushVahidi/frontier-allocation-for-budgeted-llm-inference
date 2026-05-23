# LIVE_VALIDATION_HARDENING_FOR_FROZEN_AGREEMENT_POLICY_20260523

## Scope
- Policy: `agreement_only_2of3_against_frontier` (unchanged).
- Work type: pre-live hardening only.
- API usage: none.

## Canonical Scripts
- First GSM8K-300 validation script: `scripts/run_cohere_real_model_cost_normalized_validation.py`
- Later MATH-500 validation script: `scripts/run_cohere_real_model_cost_normalized_validation.py`
- Note: `scripts/run_canonical_real_model_validation.py` is not the active Cohere scale-up entrypoint for this workflow.

## Changed Files
- `scripts/run_cohere_real_model_cost_normalized_validation.py`
  - `--dry-run-call-plan` now bypasses readiness probes and API key requirements.
  - Writes structured dry-run plan JSON with exact IDs/methods/estimated logical calls/output paths.
  - Adds configurable retry args passthrough to generator:
    - `--api-retry-max-attempts`
    - `--api-retry-base-delay-seconds`
    - `--api-retry-backoff-multiplier`
    - `--api-retry-max-delay-seconds`
    - `--api-retry-jitter-seconds`
  - Adds recovery queue passes via `--max-recovery-passes`.
  - Adds completion summaries:
    - `completion_summary.json`
    - `completion_per_method.csv`
    - `completion_per_example.csv`
  - Adds failure taxonomy outputs:
    - `failure_taxonomy_summary.json`
    - `failure_taxonomy_summary.csv`
  - Adds failure taxonomy section in run report markdown.
- `experiments/branching.py`
  - Cohere call path now uses bounded exponential backoff + jitter.
  - Handles retryable HTTP failures (including 500 family and 429 with `Retry-After`) and transient timeout/connection errors.
  - Logs every retry attempt.
- `tests/test_live_validation_hardening_20260523.py`
  - Covers taxonomy classification and API-key-free dry-run behavior.

## Dry-Run Command Executed (No API Calls)
```bash
python3 scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp 20260523T210000Z \
  --providers cohere \
  --datasets openai/gsm8k \
  --seeds 71 \
  --budgets 6 \
  --methods direct_reserve_semantic_frontier_v2,external_l1_max,external_s1_budget_forcing,external_tale_prompt_budgeting \
  --target-scored-per-slice 300 \
  --max-examples 300 \
  --dry-run-call-plan \
  --output-root outputs/live_validation_hardening_frozen_agreement_policy_20260523
```

## Dry-Run Plan Artifact
- `outputs/live_validation_hardening_frozen_agreement_policy_20260523/gsm8k300_dryrun_call_plan.json`
- Headline values:
  - `total_planned_case_rows = 1200`
  - `estimated_logical_calls_upper_bound_total = 6000`

## Live Command Template (Do Not Run Automatically)
```bash
python3 scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp <UTC_TIMESTAMP> \
  --providers cohere \
  --datasets openai/gsm8k \
  --seeds 71 \
  --budgets 6 \
  --methods direct_reserve_semantic_frontier_v2,external_l1_max,external_s1_budget_forcing,external_tale_prompt_budgeting \
  --target-scored-per-slice 300 \
  --max-examples 300 \
  --api-retry-max-attempts 5 \
  --api-retry-base-delay-seconds 1.0 \
  --api-retry-backoff-multiplier 2.0 \
  --api-retry-max-delay-seconds 20.0 \
  --api-retry-jitter-seconds 0.5 \
  --max-recovery-passes 2 \
  --output-root outputs/live_validation_hardening_frozen_agreement_policy_20260523
```

## Recovery Behavior
- First pass runs planned method-example rows.
- Unresolved rows are retried in recovery passes (failed/missing only), up to `--max-recovery-passes`.
- Completed rows are not re-run.
- Completion outputs report target/scored/missing/failed/duplicate and per-method/per-example completeness.

## Failure Taxonomy
- Output files are generated automatically after live runs:
  - `failure_taxonomy_summary.json`
  - `failure_taxonomy_summary.csv`
- Categories:
  - `HTTP 500`
  - `timeout`
  - `rate limit`
  - `parse failure`
  - `unparseable answer`
  - `provider response error`
  - `missing output`
  - `unknown`

## Pre-Live Checklist / Readiness Outputs
- `outputs/live_validation_hardening_frozen_agreement_policy_20260523/pre_live_checklist.json`
- `outputs/live_validation_hardening_frozen_agreement_policy_20260523/script_readiness_report.json`
- `outputs/live_validation_hardening_frozen_agreement_policy_20260523/manifest.json`

## Exact Next Human Command
```bash
python3 scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp <UTC_TIMESTAMP> \
  --providers cohere \
  --datasets openai/gsm8k \
  --seeds 71 \
  --budgets 6 \
  --methods direct_reserve_semantic_frontier_v2,external_l1_max,external_s1_budget_forcing,external_tale_prompt_budgeting \
  --target-scored-per-slice 300 \
  --max-examples 300 \
  --api-retry-max-attempts 5 \
  --api-retry-base-delay-seconds 1.0 \
  --api-retry-backoff-multiplier 2.0 \
  --api-retry-max-delay-seconds 20.0 \
  --api-retry-jitter-seconds 0.5 \
  --max-recovery-passes 2 \
  --output-root outputs/live_validation_hardening_frozen_agreement_policy_20260523
```

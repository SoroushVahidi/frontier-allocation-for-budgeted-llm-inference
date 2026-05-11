# Uncertainty-Retry Reserved Budget 30-Case Result

## Executive Status

The 30-case Cohere budget-4 exact run completed successfully and supports the intended replay comparison.

Run artifact directory:
`/tmp/cohere_exact_case_uncertainty_retry_reserved_budget4_30case_20260510`

## Paired Result

- Baseline method: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor`
- Treatment method: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_uncertainty_retry_v1`
- Baseline exact match: `9/30`
- Treatment exact match: `13/30`
- Improved cases: `openai_gsm8k_190`, `openai_gsm8k_347`, `openai_gsm8k_433`, `openai_gsm8k_458`
- Regressions: none
- Gold-in-pool: `12/30 -> 15/30`
- Retry budget available: `30/30`
- Retry triggered: `22/30`
- Retry released: `8/30`
- Logical Cohere calls: `232/300`

## Interpretation

This is a direct 30-case exact replay result, not a proxy audit.
Within this set, the uncertainty-retry treatment recovered 4 additional cases relative to the diverse-anchor baseline, with no observed regressions in the provided summary.

## Artifacts Seen

The `/tmp` output bundle was available and included:

- `manifest.json`
- `per_example_records.jsonl`
- `method_summary.csv`
- `slice_summary.csv`
- `pairwise_comparisons.csv`
- `exact_case_validation_report.json`

The summary files reported:

- Baseline method accuracy: `0.3`
- Treatment method accuracy: `0.43333333333333335`
- Baseline mean total tokens per scored example: `2073.233333333333`
- Treatment mean total tokens per scored example: `1928.7`
- Baseline mean latency per scored example: `9.315942266666667`
- Treatment mean latency per scored example: `8.283119466666667`

## Method Resolution

The no-API validator resolves both methods:

- `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor`
- `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_uncertainty_retry_v1`

## 50-Case Replay Prep

The next exact replay file is prepared at:

`docs/project_handoff_20260510/exact_case_replay/failure_recovery_50case_exact_cases_20260510.jsonl`

Selection method:

- Keep the existing 30 exact replay cases in order.
- Append 20 additional fully tracked latest-method failures chosen from the gold-absent / low-diversity audit.
- Stratify the new 20 cases across:
- `money/cost/revenue`: 7 cases
- `ratio/proportion/percentage`: 7 cases
- `multi-step arithmetic`: 6 cases
- Avoid duplicates with the existing 30-case set.

The 20 added cases were chosen to preserve the failure-recovery focus and to emphasize gold-absent or low-diversity behavior rather than selector-only variations.

## Validation

Planned and executed no-API validation targets:

- Exact case count: `50`
- Duplicate count: `0`
- Required fields present: `question`, `gold_answer_canonical`, `failure_domain`
- Runner validate-only mode: passes
- Method resolution: passes for both treatment methods

No paid or model API calls were made while preparing this report and replay file.

## Next Run

Recommended 50-case validation command:

```bash
python3 scripts/run_cohere_real_model_cost_normalized_validation.py \
  --validate-exact-cases-only \
  --provider cohere \
  --datasets openai/gsm8k \
  --budgets 4 \
  --methods direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor,direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_uncertainty_retry_v1 \
  --exact-cases-jsonl docs/project_handoff_20260510/exact_case_replay/failure_recovery_50case_exact_cases_20260510.jsonl \
  --expected-exact-case-count 50
```

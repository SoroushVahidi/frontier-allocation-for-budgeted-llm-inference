# Matched-rate evaluation smoke test (structural, non-claim)

Date: 2026-04-15.

## Goal

Verify structurally that:

1. run summaries include threshold sweeps,
2. comparison summary emits matched-ACT-rate selection and residuals,
3. selective-vs-random matched-rate deltas are present,
4. matched-compute availability handling is explicit.

## Commands executed

```bash
python scripts/train_oracle_distilled_stop_vs_act_student.py \
  --distill-dataset outputs/oracle_behavior_smoke/distill_with_gap.jsonl \
  --output-dir outputs/oracle_behavior_smoke/run_anchor \
  --run-name smoke_anchor \
  --train-buckets accepted,borderline,rejected \
  --eval-buckets accepted,borderline,rejected \
  --train-selection-mode bucket \
  --filter-policy anchor_default

python scripts/train_oracle_distilled_stop_vs_act_student.py \
  --distill-dataset outputs/oracle_behavior_smoke/distill_with_gap.jsonl \
  --output-dir outputs/oracle_behavior_smoke/run_selective \
  --run-name smoke_selective \
  --train-buckets accepted,borderline \
  --eval-buckets accepted,borderline,rejected \
  --train-selection-mode bucket \
  --filter-policy oracle_distilled_accepted_plus_borderline

python scripts/train_oracle_distilled_stop_vs_act_student.py \
  --distill-dataset outputs/oracle_behavior_smoke/distill_without_gap.jsonl \
  --output-dir outputs/oracle_behavior_smoke/run_random_missinggap \
  --run-name smoke_random_missinggap \
  --train-selection-mode selected_flag \
  --filter-policy random_matched_coverage_baseline

python scripts/compare_oracle_distilled_stop_vs_act_runs.py \
  --summaries \
    outputs/oracle_behavior_smoke/run_anchor/oracle_distilled_student_summary.json \
    outputs/oracle_behavior_smoke/run_selective/oracle_distilled_student_summary.json \
    outputs/oracle_behavior_smoke/run_random_missinggap/oracle_distilled_student_summary.json \
  --output-dir outputs/oracle_behavior_smoke/comparison \
  --required-roles anchor_default,oracle_distilled_accepted_plus_borderline,random_matched_coverage_baseline
```

## Structural checks observed

- Threshold sweeps emitted in each run summary under `evaluation.threshold_sweep`.
- Comparison summary emitted:
  - `comparison_protocol.matched_act_rate_target` and source,
  - `matched_point_by_run` with threshold + residual,
  - `pairwise_controls.*.matched_act_rate_evaluation`,
  - `pairwise_controls.*.matched_compute_rate_evaluation` availability status.
- Behavior metrics remained available only where `oracle_action_gap` existed; unmatched sources were flagged explicitly.

## Interpretation guardrail

These results are structural validations on mock-compatible artifacts and are not oracle-phase performance evidence.

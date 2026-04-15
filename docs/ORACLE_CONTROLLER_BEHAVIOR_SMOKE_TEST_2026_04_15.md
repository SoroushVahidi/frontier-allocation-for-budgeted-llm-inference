# Oracle controller-behavior metrics smoke test (structural, non-claim)

Date: 2026-04-15.

## Goal

Structural validation only (no oracle-phase claim):

1. New controller-behavior metrics are emitted when `oracle_action_gap` is available.
2. Missing-data handling is explicit when `oracle_action_gap` is absent.
3. Comparison summaries remain structurally coherent with mixed availability.

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

## Structural results

- `run_selective` summary emitted `evaluation.controller_behavior.available=true` with BAR/HAR/HPSR/BSR/regret fields.
- `run_random_missinggap` emitted `available=false` and `reason=missing_oracle_action_gap` instead of fabricated zero metrics.
- Comparison summary populated run-level behavior coverage and pairwise behavior-availability diagnostics.

## Interpretation guardrail

This smoke test used mock/non-oracle-compatible artifacts and validates only output structure and metric plumbing. It is not evidence for oracle-distillation quality gains.

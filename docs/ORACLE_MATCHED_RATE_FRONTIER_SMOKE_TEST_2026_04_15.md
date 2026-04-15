# Matched-rate frontier smoke test (structural, non-claim)

Date: 2026-04-15.

## Goal

Validate structurally that the comparison path can:

1. build a shared matched ACT-rate frontier grid,
2. emit per-run frontier points,
3. emit pairwise frontier deltas and compact summaries,
4. preserve one-point matched-rate outputs.

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
  --required-roles anchor_default,oracle_distilled_accepted_plus_borderline,random_matched_coverage_baseline \
  --frontier-points 5
```

## Structural checks observed

- Comparison summary emitted `comparison_protocol.frontier_rate_grid`.
- Summary emitted `frontier_points_by_run` for each run.
- Pairwise controls emitted `matched_act_rate_frontier` with per-point deltas.
- Frontier compact summary fields (mean deltas, win counts, AUC-style summaries, mean residual gap) were present where points were available.
- Existing one-point matched-rate output (`matched_point_by_run`) remained present.

## Interpretation guardrail

This smoke test validates evaluation plumbing on mock-compatible artifacts only and is not oracle-phase evidence.

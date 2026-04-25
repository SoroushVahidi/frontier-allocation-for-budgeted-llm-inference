# Trace-Level Learned Branch Scorer Eval (20260425TTRACEPIPE)

## Scope
This pass implements the next engineering step from proxy diagnostics to true trace-level candidate rows, with conservative offline validation.

## What was implemented
1. **Trace-level dataset builder** from `outputs/ten_case_reasoning_diversity_trace_rerun_<timestamp>/`:
   - `scripts/build_trace_level_learned_branch_scorer_dataset.py`
   - emits: `examples.csv`, `feature_schema.json`, `dataset_summary.csv`, `case_coverage.csv`, `README.md`.
   - supports `source_type` = `trace_level_branch`, `trace_level_answer_group`, `proxy_answer_group_only`.
   - includes required controller/candidate/gold/selection/support/diversity fields when available.

2. **Training extension** for leakage-aware splits and richer selection diagnostics:
   - updated `scripts/train_learned_branch_scorer.py`
   - adds leave-one-example-out + seed/budget/joint holdouts.
   - reports top-k recall, gold-present selection deltas, present-not-selected reduction, and degradation rate.
   - emits `case_level_selection_metrics.csv` in addition to existing outputs.

3. **Trace-level offline selector comparison**:
   - `scripts/run_trace_level_learned_scorer_eval.py`
   - compares:
     - current controller selection,
     - support-based selection,
     - learned candidate scorer,
     - learned answer-group aggregation.

4. **No-key tests**:
   - added `tests/test_trace_level_learned_branch_scorer_pipeline.py`
   - verifies trace dataset build, train, eval, required columns, and proxy fallback mode.

## True-trace 10-case package status (dry-run)
Executed trace rerun with full trace emission in dry-run mode:
- `outputs/ten_case_reasoning_diversity_trace_rerun_20260425TTRACEPIPE/`

Built trace-level dataset from that package:
- `outputs/trace_level_learned_branch_scorer_dataset_20260425TTRACEPIPE/`
- Result: 10 cases, 10 rows, **0 gold-present rows** (expected in dry-run-only traces).

Training/eval still run structurally via fallback support proxy:
- `outputs/trace_level_learned_branch_scorer_train_20260425TTRACEPIPE/`
- `outputs/trace_level_learned_scorer_eval_20260425TTRACEPIPE/`

## Small synthetic trace-level validation (no-key, positive-label sanity)
Using the synthetic trace package test fixture output:
- dataset: `outputs/trace_level_learned_branch_scorer_dataset_20260425T_TRACE_DATASET_TEST/`
- training: `outputs/trace_level_learned_branch_scorer_train_20260425T_TRACE_TRAIN_TEST/`
- eval (best lightweight model): `outputs/trace_level_learned_scorer_eval_20260425T_TRACE_EVAL_RF_TEST/`

Headline diagnostic outcome on this tiny trace-level pool:
- gold-present cases: 2/2
- current controller selected-gold rate: 0.5
- learned candidate scorer selected-gold rate: 1.0
- present-not-selected: 0.5 -> 0.0
- degradation cases: 0

These numbers are tiny-sample only and not publication-grade; they confirm the **pipeline can detect and improve present-not-selected** when gold candidates are present in the traced pool.

## Runtime integration decision
Deferred in this pass.
- Canonical `strict_f3` behavior is unchanged.
- Priority was robust trace-level offline validation and training/eval plumbing.

## Readiness and next engineering step
- **Ready for bounded real-trace run** (non-dry-run) to gather gold-present candidate traces with real API outputs.
- Next step:
  1. run trace-enabled 10-case package with real keys,
  2. rebuild trace-level dataset,
  3. retrain/evaluate with leave-one-case-out and budget/seed holdouts,
  4. if gains persist with low degradations, add low-risk runtime rerank gate method behind explicit artifact flag.

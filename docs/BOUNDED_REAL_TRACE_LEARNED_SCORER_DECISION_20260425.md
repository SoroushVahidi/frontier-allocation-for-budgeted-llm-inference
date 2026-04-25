# Bounded Real Trace Learned Scorer Decision (2026-04-25)

## Current status

- Real traced cases collected in this repository run: **0** (dry-run only in CI/no-key validation).
- Candidate branches / answer groups on real traces: **not available yet**.
- Gold absent vs present-not-selected fractions: **not estimable until real traces are collected**.

## Decision rule

Integrate learned scorer only if grouped held-out problem evaluation shows all of:

1. At least **+5 percentage points** selected-gold improvement on gold-present cases.
2. No more than **0.5 percentage point degradation** on already-correct control cases.
3. No severe overfitting pattern across held-out problems.

If any criterion fails, do **not** integrate in runtime and prioritize coverage generation improvements.

## Preliminary recommendation (dry-run only)

- Runtime integration decision: **Not ready / deferred**.
- Reason: this branch contains the bounded real-trace workflow and grouped-split scorer tooling, but no real API trace data has been collected in this environment yet.
- Next step: run the command recipe below with real API enabled and evaluate the resulting package.

## Command recipe for real run (small bounded sweep)

```bash
python scripts/run_bounded_real_trace_collection.py \
  --run-real-api \
  --provider cohere \
  --model command-r-plus-08-2024 \
  --budgets 4,6,8 \
  --seeds 11,23 \
  --absent-count 10 \
  --present-count 10 \
  --control-count 10 \
  --emit-full-traces
```

Then:

```bash
python scripts/build_trace_level_learned_branch_scorer_dataset.py \
  --trace-dir outputs/bounded_real_trace_collection_<TIMESTAMP>

python scripts/train_learned_branch_scorer.py \
  --dataset-examples outputs/trace_level_learned_branch_scorer_dataset_<TIMESTAMP>/examples.csv \
  --split grouped_problem_holdout

python scripts/run_trace_level_learned_scorer_eval.py \
  --predictions outputs/trace_level_learned_branch_scorer_train_<TIMESTAMP>/predictions.csv
```

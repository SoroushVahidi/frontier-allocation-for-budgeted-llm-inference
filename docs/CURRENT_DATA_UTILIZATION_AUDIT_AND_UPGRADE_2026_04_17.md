# Current data utilization audit and minimal upgrade (2026-04-17)

## How current data are being used (canonical path)

Canonical branch-allocation data path in this repo:

1. `scripts/run_bruteforce_branch_label_generator.py`
   - emits `candidate_labels.jsonl`, `pairwise_labels.jsonl`, `state_summaries.jsonl`.
2. `scripts/build_bruteforce_target_regimes.py`
   - derives supervision regimes (`all_pairs`, `quality_mixed_trust`, `partial_order_incomparable`, `penalized_marginal_defer`, etc.).
3. `scripts/build_canonical_branch_learning_corpus.py`
   - merges/normalizes base + regime rows into canonical corpus with source precedence and split assignment.
4. `experiments/bruteforce_branch_allocator.py`
   - builds learning tables and consumes pair/candidate metadata for binary, ternary, defer, fallback-aware learning/eval.

## Where data usage is strong

- Strong near-tie and hard-slice metadata (`near_tie_flag`, `adjacent_rank`, uncertainty, label source).
- Existing defer/abstain handling is integrated in both target construction and evaluation.
- Source provenance and exact-vs-approx lineage are tracked and consumed.

## Where data usage is underutilized

- Advanced regime-specific pairwise fields (soft probabilities, partial-order labels, penalized fields, reliability weights, disagreement signals) were not fully preserved in canonical corpus rows.
- Exact-vs-approx disagreement signals existed in some regimes but were not explicitly elevated as a first-class canonical disagreement signal.
- Ambiguity handling in learning prep did not explicitly consume disagreement-signal fields when present.

## What was changed now (small, canonical, backward-compatible)

1. Canonical corpus passthrough expansion in `scripts/build_canonical_branch_learning_corpus.py`
   - preserve advanced pairwise fields when present (soft targets, partial-order labels, penalized fields, defer labels, reliability weights, disagreement signals).
   - add canonical derived field: `exact_vs_approx_disagreement_signal`.
   - add hard-slice summary counters for disagreement/partial-order/soft-prob/penalized row availability.
   - add dataset-level disagreement-signal rate.

2. Learning-table ambiguity usage upgrade in `experiments/bruteforce_branch_allocator.py`
   - ambiguity flagging now treats disagreement-signal fields as explicit ambiguity evidence.

3. Added reusable audit script:
   - `scripts/audit_current_data_utilization.py`
   - writes machine-readable and markdown summaries under `outputs/data_utilization_audit/<run_id>/`.

## Next recommended step

Single highest-value next Codex task:

- Implement a bounded **targeted exact relabel selection pass** driven by overlap of:
  - disagreement signal,
  - near-tie / adjacent-rank,
  - high uncertainty,
  then re-run matched coverage/accepted-accuracy reporting by budget/provenance slice.

This remains small and data-reuse-first, and avoids broad new data collection before current hard-case semantics are stabilized.

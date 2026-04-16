# Canonical external-supervision pass: budget-conditioned comparator semantics (2026-04-16)

## Objective
Test one richer but bounded budget-conditioned comparator design (beyond single `score_per_budget`) while keeping the same method family and canonical pipeline.

## 1) Budget-conditioned signals available now
From the current low-budget / exact-promoted-aware canonical regime:
- remaining budget: `remaining_budget`
- branch value/progress: `score`, `estimated_value_if_allocate_next`, `recent_delta`, `depth`, `branch_age`
- uncertainty: `allocation_value_std`, `pair_uncertainty_std_mean`
- comparator context: `score_gap_to_top`, `score_gap_to_prev`, `score_gap_to_next`, `branch_rank`, `frontier_branch_count`, `frontier_top2_gap`
- provenance: `is_exact_label`, `is_approx_label`, `label_source`, `replaced_approx_label`
- hard/fragile slices: near-tie, adjacent-rank, small-margin
- boundary diagnostics: eligible pairs, changed/helpful/harmful counts, top-1 changed states

These are enough to implement richer budget conditioning without new architecture.

## 2) Single bounded comparator improvement chosen
### Change
Add a **budget-bucket-conditioned score interaction block** (one feature block):
- `score_x_budget_low = score` if budget <= 2 else 0
- `score_x_budget_mid = score` if budget == 3 else 0
- `score_x_budget_high = score` if budget >= 4 else 0

This is more expressive than one scalar ratio (`score_per_budget`) while still linear-model compatible and narrow.

### Files modified
- `experiments/bruteforce_branch_allocator.py`
  - added new features to `ALLOC_FEATURE_NAMES_V2`
  - computed the three budget-bucket interactions in state-context feature builder
- `scripts/run_canonical_branch_learning_pass.py`
  - added matching external PRM mapping for the same feature block

No learner-family or architecture change.

## 3) Matched setup used
- Canonical corpus: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1`
- External PRM artifact: `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`
- Matched methods: anchor / broad / aligned / boundary

## 4) Exact commands run
```bash
python -m py_compile experiments/bruteforce_branch_allocator.py scripts/run_canonical_branch_learning_pass.py
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1 --output-root outputs/canonical_branch_learning_pass --run-id budgetconditioned_transfer_alignment_20260416 --seed 17 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_uncertainty_gated_blend --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-prm-max-uncertainty-std 1.0
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1 --output-root outputs/canonical_branch_learning_pass --run-id budgetconditioned_boundary_20260416 --seed 17 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_comparator_boundary_tiebreak --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02 --external-prm-max-uncertainty-std 1.0
```

## 5) Support counts (same regime as prior support-expansion pass)
- total test pairs: 30
- total top-1 states: 9
- near-tie: 12
- adjacent-rank: 18
- small-margin: 22
- exact-promoted: 2
- exact-only: 2
- approx-only: 28
- dataset slices: MATH-500=15, GSM8K=15
- budget slices: b1=2, b2=6, b3=9, b4=13
- boundary-eligible pairs: 4 (under this feature block's boundary dynamics)

Still small: b1 (`n=2`), exact-promoted/exact-only (`n=2`).

## 6) Anchor vs broad vs aligned vs boundary (new pass)
### Aggregate
- anchor: pairwise 0.5333, top1 0.3333
- broad: pairwise 0.6000, top1 0.3333
- aligned: pairwise 0.6000, top1 0.4444
- boundary: pairwise 0.6333, top1 0.3333

### Hard slices
- near-tie: anchor 0.4167, broad 0.4167, aligned 0.4167, boundary 0.5000
- adjacent-rank: anchor 0.5556, broad 0.5000, aligned 0.5000, boundary 0.5556
- small-margin: anchor 0.4545, broad 0.5000, aligned 0.5000, boundary 0.5455

### Budget slices
- b1 (n=2): anchor 1.0, broad 0.5, aligned 0.5, boundary 1.0
- b2 (n=6): anchor 0.3333, broad 0.5, aligned 0.5, boundary 0.5
- b3 (n=9): anchor 0.4444, broad 0.5556, aligned 0.5556, boundary 0.5556
- b4 (n=13): anchor 0.6154, broad 0.6923, aligned 0.6923, boundary 0.6923

### Provenance slices
- exact-promoted (n=2): anchor 0.0, broad 0.5, aligned 0.5, boundary 0.5
- exact-only (n=2): anchor 0.0, broad 0.5, aligned 0.5, boundary 0.5
- approx-only (n=28): anchor 0.5714, broad 0.6071, aligned 0.6071, boundary 0.6429

### Boundary diagnostics
- changed pairs: 3 (all helpful)
- changed top-1 states: 0/9

## 7) Method-ordering impact vs prior support-expansion regime
Compared with the immediate prior low-budget/exact-promoted regime run:
- anchor worsened (pairwise 0.5667 -> 0.5333)
- broad unchanged
- aligned unchanged
- boundary unchanged on aggregate
- broad vs aligned still tied on pairwise; aligned remains higher top-1
- boundary remains diagnostic for top-1 (no top-1 flips)

## 8) Conservative diagnosis
1. Comparator semantics are richer and explicitly budget-conditioned.
2. This richer block did **not** improve the internal anchor and did not create new broad-vs-aligned pairwise separation.
3. Method ordering on aggregate is effectively unchanged except anchor degradation.
4. Low-budget/extreme and exact-promoted slices are still small for strong conclusions.

## 9) Recommendation on Math-Shepherd
Still wait. This pass improves comparator expressivity but does not materially improve evidence quality or method separation beyond the prior support-expanded baseline.

## Files added/modified
- Modified: `experiments/bruteforce_branch_allocator.py`
- Modified: `scripts/run_canonical_branch_learning_pass.py`
- Added: `docs/CANONICAL_EXTERNAL_SUPERVISION_PRM800K_BUDGET_CONDITIONED_COMPARATOR_SEMANTICS_PASS_2026_04_16.md`
- Added: `docs/canonical_external_supervision_prm800k_budget_conditioned_comparator_semantics_pass_2026_04_16_summary.json`

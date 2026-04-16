# Canonical external-supervision pass: budget-aware comparator semantics (2026-04-16)

## Objective
Test one bounded budget-aware comparator improvement (no new model family) and check whether it improves branch-allocation decisions—especially low-budget and hard slices—better than the recent external-uncertainty filtering pass.

## Budget-aware/progress-aware signals available now

### Already available in canonical candidate/pairwise rows
- `remaining_budget`
- `features_branch_v1.depth`, `features_branch_v1.branch_age`
- `estimated_value_if_allocate_next`, `branch_vs_outside_gap`
- `features_branch_v1.recent_delta`
- `features_branch_v2.score_gap_to_top`, `score_gap_to_prev`, `score_gap_to_next`, `score_z`
- `allocation_value_std`, `pair_uncertainty_std_mean`
- frontier context: `frontier_branch_count`, `frontier_score_std`, `frontier_top2_gap`, etc.
- provenance: `is_exact_label`, `is_approx_label`, `label_source`, `replaced_approx_label`

### Already available in external PRM rows
- `quality_score`
- `remaining_budget`
- `source_dataset_key`, `source_split`, `supervision_origin`

### Cheaply derived signal chosen in this pass
- `score_per_budget = score / max(1, remaining_budget)`

Rationale: explicitly encode value-per-remaining-budget pressure (high value with low budget gets stronger signal), while keeping linear comparator family unchanged.

## Single bounded comparator improvement implemented
- Added one budget-aware feature to internal comparator representation (`v2`) and external PRM mapping:
  - `score_per_budget`

Files changed:
- `experiments/bruteforce_branch_allocator.py`
  - add `score_per_budget` to `ALLOC_FEATURE_NAMES_V2`
  - compute `score_per_budget` in state-context feature builder
- `scripts/run_canonical_branch_learning_pass.py`
  - map external PRM candidate rows to the same `score_per_budget` feature

No architecture/model-family change; still matched anchor + broad + aligned + boundary.

## Exact artifact paths used
- Canonical corpus: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_harder_uncertainty_v1`
- External PRM artifact: `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`
- New budget-aware runs:
  - `outputs/canonical_branch_learning_pass/budgetaware_transfer_alignment_20260416`
  - `outputs/canonical_branch_learning_pass/budgetaware_boundary_20260416`
- Comparison baseline runs from prior pass:
  - uncertainty-control: `ua_control_transfer_alignment_20260416`, `ua_control_boundary_20260416`
  - uncertainty-filtered: `ua_filtered_transfer_alignment_20260416`, `ua_filtered_boundary_20260416`

## Exact commands run
```bash
python -m py_compile experiments/bruteforce_branch_allocator.py scripts/run_canonical_branch_learning_pass.py
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_harder_uncertainty_v1 --output-root outputs/canonical_branch_learning_pass --run-id budgetaware_transfer_alignment_20260416 --seed 17 --near-tie-margin 0.04 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_uncertainty_gated_blend --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-prm-max-uncertainty-std 1.0
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_harder_uncertainty_v1 --output-root outputs/canonical_branch_learning_pass --run-id budgetaware_boundary_20260416 --seed 17 --near-tie-margin 0.04 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_comparator_boundary_tiebreak --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02 --external-prm-max-uncertainty-std 1.0
```

## Support counts (first-class)
- total test pairs: 18
- total top-1 states: 4
- near-tie: 5
- adjacent-rank: 10
- small-margin: 14
- exact-promoted: 1 (**too small**)
- exact-only: 1 (**too small**)
- approx-only: 17
- dataset slices: MATH-500=6, GSM8K=12
- budget slices: b2=6, b3=6, b4=6

## Matched comparison: anchor vs broad vs aligned vs boundary

### Budget-aware pass (this pass)
- anchor: pairwise 0.4444, top1 0.0000
- broad: pairwise 0.5556, top1 0.0000
- aligned: pairwise 0.5556, top1 0.0000
- boundary: pairwise 0.5556, top1 0.0000
- broad vs aligned: **tied**

### Versus recent uncertainty-filtered pass
- uncertainty-filtered broad/aligned were 0.5000 pairwise (top1 0.2500)
- budget-aware pass broad/aligned are 0.5556 pairwise (top1 0.0000)
- hard-slice pairwise recovered vs uncertainty-filtered:
  - near-tie: 0.40 -> 0.60
  - adjacent-rank: 0.40 -> 0.50
  - small-margin: 0.3571 -> 0.4286
  - exact-promoted (n=1): 0.0 -> 1.0 (tiny support)
- budget slices (broad/aligned):
  - b2: 0.50 -> 0.50 (flat)
  - b3: 0.50 -> 0.6667 (improved)
  - b4: 0.50 -> 0.50 (flat)

### Versus uncertainty-control pass
Numerically unchanged from uncertainty-control on aggregate/hard/budget slices in this environment.

### Boundary diagnostics
- boundary still diagnostic: helpful pair flips, no top-1 changes (0/4 states)

## Conservative interpretation
1. Comparator semantics are now slightly more budget-explicit (`score_per_budget`), and this is a clean, bounded change.
2. Relative to uncertainty-filtered pass, pairwise hard-slice behavior improved (mostly by returning to control-like behavior).
3. Relative to uncertainty-control, no measurable improvement emerged in this run.
4. Broad and aligned remain tied; no separation signal yet.
5. Evidence quality improved (we tested budget-aware semantics directly), but this does not yet demonstrate a robust bottleneck reduction.

## Recommendation on Math-Shepherd
Still wait. This pass does not materially improve broad-vs-aligned separation or produce a stable new win beyond prior uncertainty-control behavior.

## Files added/modified
- Modified: `experiments/bruteforce_branch_allocator.py`
- Modified: `scripts/run_canonical_branch_learning_pass.py`
- Added: `docs/CANONICAL_EXTERNAL_SUPERVISION_PRM800K_BUDGET_AWARE_COMPARATOR_PASS_2026_04_16.md`
- Added: `docs/canonical_external_supervision_prm800k_budget_aware_comparator_pass_2026_04_16_summary.json`

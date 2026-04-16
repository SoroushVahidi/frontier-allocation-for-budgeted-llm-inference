# Hard-case feature representation status (2026-04-16)

## Scope

This pass follows the hard-region exact-label promotion study and asks a narrower question:

> Are the hardest branch-comparison slices now more limited by weak feature representation than by label provenance alone?

Project framing is unchanged: fixed-budget next-step branch allocation, with pairwise branch comparison as the main learned object.

## Commands executed

```bash
python -m py_compile \
  experiments/bruteforce_branch_allocator.py \
  scripts/train_bruteforce_branch_allocator.py \
  scripts/audit_bruteforce_feature_representation.py \
  scripts/run_hard_case_feature_representation_experiment.py

python scripts/audit_bruteforce_feature_representation.py \
  --labels-dir outputs/branch_label_bruteforce_targets/hard_region_exact_augmented_regimes_20260416/regime_promoted_exact_hard_region \
  --run-id hard_case_feature_audit_20260416 \
  --seed 17 \
  --near-tie-margin 0.03

python scripts/run_hard_case_feature_representation_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/hard_region_exact_augmented_regimes_20260416 \
  --run-id hard_case_feature_representation_20260416 \
  --seeds 11,29,47 \
  --feature-sets v1,v2 \
  --regimes all_pairs_approx,promoted_exact_hard_region \
  --near-tie-margin 0.03
```

## Part A — Feature audit (v1 vs hard-case gaps)

Prior feature set (`v1`, 14 features) was dominated by local branch-only signals.

Hard-case coverage gaps identified and targeted:

- branch momentum/trend normalization,
- verification dynamics normalized by age/depth,
- branch rank and neighbor gap structure,
- frontier competition concentration (entropy/HHI/top2 gap),
- local uncertainty context relative to frontier dispersion,
- stagnation/instability ratios,
- score-to-top and score-to-neighbor gaps,
- normalized budget-context interactions,
- explicit pair-relational metadata for A vs B diagnostics.

Audit artifact:

- `outputs/branch_label_bruteforce_learning/hard_case_feature_audit_20260416/feature_audit.json`

Audit summary (promoted-exact-hard-region regime):

- v1 feature count: **14**
- v2 feature count: **33**
- newly added features: **19**
- near-tie pairs: **33**
- adjacent-rank pairs: **118**

## Part B — Richer feature construction

Implementation adds feature-set versioning in learning config (`feature_set: v1 | v2`) with backward compatibility.

### New candidate features (`v2`)

Added signals include:

- relative-to-top and neighbor gaps: `score_gap_to_top`, `score_gap_to_prev`, `score_gap_to_next`
- frontier context: `frontier_branch_count`, `frontier_score_mean`, `frontier_score_std`, `frontier_score_entropy`, `frontier_score_hhi`, `frontier_top2_gap`
- rank structure: `branch_rank`, `branch_rank_norm`, `score_z`
- verification dynamics: `verify_rate`, `verify_recent_delta_interaction`
- trend/stagnation: `recent_delta_per_depth`, `stalled_ratio`
- budget-context: `budget_norm_in_state`, `score_budget_interaction`
- uncertainty context: `uncertainty_rel_to_score_std`

### New pair-relational metadata (`v2`)

Per pair row we now compute:

- `rank_gap_abs`
- `score_gap_abs`
- `score_z_gap_abs`
- `verify_rate_gap_abs`
- `uncertainty_gap_abs`
- `score_to_top_gap_abs_diff`
- `adjacent_rank_flag`

These are emitted for hard-slice auditing and analysis while preserving existing model compatibility.

## Part C — Matched hard-slice evaluation (old vs richer features)

Fixed supervision regimes, seeds, and model families; only feature set changes (`v1` vs `v2`).

Primary regimes compared:

1. `all_pairs_approx`
2. `promoted_exact_hard_region`

### Pairwise logistic baseline (3-seed means)

`all_pairs_approx`:

- v1: pairwise **0.4629**, top1 **0.2915**, near-tie **0.4762**, adjacent **0.4421**
- v2: pairwise **0.7657**, top1 **0.7239**, near-tie **0.7262**, adjacent **0.7263**

`promoted_exact_hard_region`:

- v1: pairwise **0.4629**, top1 **0.2915**, near-tie **0.4762**, adjacent **0.4421**, exact-promoted slice **0.4765**
- v2: pairwise **0.7657**, top1 **0.7239**, near-tie **0.7262**, adjacent **0.7263**, exact-promoted slice **0.7127**

### CatBoost ranker (3-seed means)

In this bounded run, CatBoost remained unchanged between v1/v2 on reported slices (no clear feature-set lift signal).

### Per-dataset and per-budget slices (pairwise logistic)

Per-dataset in this run remains GSM8K-only:

- all_pairs v1: 0.4629
- all_pairs v2: 0.7657
- promoted-exact-hard-region v1: 0.4629
- promoted-exact-hard-region v2: 0.7657

Per-budget (all_pairs regime, pairwise logistic):

- B2: v1 0.3214 -> v2 0.3929
- B3: v1 0.4762 -> v2 0.8413
- B4: v1 0.6032 -> v2 0.8730

## Main question answer

Did richer hard-case features improve difficult slices more than recent exact-label promotion did?

- In this bounded run, **yes for the pairwise logistic baseline**: near-tie and adjacent-rank slices improved materially when switching v1 -> v2 under fixed supervision.
- This is stronger than the prior hard-region exact-promotion-only effect, which did not clearly move hardest slices.

## Conservative interpretation

Most conservative reading of this pass:

- representation weakness was a material part of the remaining bottleneck for the linear pairwise learner;
- hard-case ambiguity is **not eliminated** (model-family sensitivity remains; CatBoost did not show the same lift here);
- current bottleneck likely includes **both representation weakness and irreducible ambiguity/modeling limits**, not just label provenance.

## Artifacts

- Feature audit:
  - `outputs/branch_label_bruteforce_learning/hard_case_feature_audit_20260416/feature_audit.{json,md}`
- Matched feature-set experiment:
  - `outputs/branch_label_bruteforce_learning/hard_case_feature_representation_20260416/hard_case_feature_representation_{results,summary}.json`
  - `outputs/branch_label_bruteforce_learning/hard_case_feature_representation_20260416/hard_case_feature_representation_report.md`

# Canonical external-supervision pass: low-budget / exact-promoted support expansion (2026-04-16)

## Objective
Build one harder canonical evaluation regime with stronger held-out support in low-budget, exact-promoted, and comparator-fragile slices; then rerun the same matched method family (anchor / broad / aligned / boundary) without architecture changes.

## 1) Current support-gap audit (before expansion)
Using the latest budget-aware comparator pass as the immediate pre-pass baseline:

- total test pairs: 18
- total top-1 states: 4
- near-tie: 5
- adjacent-rank: 10
- small-margin: 14
- exact-promoted: 1
- exact-only: 1
- approx-only: 17
- dataset slices: MATH-500=6, GSM8K=12
- budget slices: b2=6, b3=6, b4=6 (no b1 support)
- boundary-eligible pairs: 5

Too small for confident interpretation:
- exact-promoted / exact-only (`n=1`)
- top-1 support (`n=4`)
- low-budget extreme slice (`b1=0`)

## 2) Bounded support-targeted harder corpus construction

### Targeting choices
Kept the same task definition and pipeline, but increased support where needed:
- more frontier states in approx + exact runs,
- explicit low-budget coverage (`min-remaining-budget=1`),
- larger exact pool for exact-promotion opportunities,
- split seed chosen to preserve more held-out exact-promoted + low-budget rows.

### Harder canonical corpus artifact
- `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1`

Corpus-level expansion vs prior corpus (`real_branch_learning_corpus_20260416_harder_uncertainty_v1`):
- pairwise rows: 194 -> 262
- test pairwise rows: 29 -> 85
- near-tie pairs: 58 -> 112
- adjacent-rank pairs: 110 -> 160
- small-margin pairs: 140 -> 191
- exact-promoted pairs: 16 -> 16 (unchanged corpus-wide, but held-out support increased)

## 3) Exact commands run
```bash
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_gsm8k_approx_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 17 --max-frontier-states 40 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 1 --max-remaining-budget 4 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 5
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_math500_approx_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 17 --max-frontier-states 40 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 1 --max-remaining-budget 4 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 5
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_gsm8k_exact_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 29 --max-frontier-states 20 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 1 --max-remaining-budget 3 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 3 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 3
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_math500_exact_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 29 --max-frontier-states 20 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 1 --max-remaining-budget 3 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 3 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 3
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/lbep_approx_runs.txt --output-dir outputs/branch_label_bruteforce_merged --run-id lbep_multi_dataset_merged_20260416_v1 --near-tie-margin 0.05
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/lbep_exact_runs.txt --output-dir outputs/branch_label_bruteforce_merged --run-id lbep_exact_merged_20260416_v1 --near-tie-margin 0.05
python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce_merged/lbep_multi_dataset_merged_20260416_v1 --output-dir outputs/branch_label_bruteforce_targets --run-id lbep_target_regimes_20260416 --pair-strategies all_pairs,adjacent_rank,top_vs_rest,uncertainty_filtered --near-tie-margin 0.05 --high-margin-threshold 0.10 --max-pair-std 0.08 --exact-labels-dir outputs/branch_label_bruteforce_merged/lbep_exact_merged_20260416_v1 --promote-exact-over-approx --tie-abs-margin-threshold 0.05 --tie-relative-margin-threshold 0.20 --tie-std-threshold 0.08 --tie-use-near-tie-flag --tie-include-approx
python scripts/build_canonical_branch_learning_corpus.py --base-labels-dir outputs/branch_label_bruteforce_merged/lbep_multi_dataset_merged_20260416_v1 --regime-root-dir outputs/branch_label_bruteforce_targets/lbep_target_regimes_20260416 --output-root outputs/branch_learning_corpora --run-id real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1 --split-seed 51 --train-ratio 0.70 --val-ratio 0.10 --near-tie-margin 0.05 --small-margin-threshold 0.10
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1 --output-root outputs/canonical_branch_learning_pass --run-id lowbudget_exactpromoted_transfer_alignment_20260416 --seed 17 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_uncertainty_gated_blend --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-prm-max-uncertainty-std 1.0
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1 --output-root outputs/canonical_branch_learning_pass --run-id lowbudget_exactpromoted_boundary_20260416 --seed 17 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_comparator_boundary_tiebreak --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02 --external-prm-max-uncertainty-std 1.0
```

## 4) Held-out support after expansion (new regime)
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
- boundary-eligible pairs: 9

Still small:
- exact-promoted / exact-only remain small (`n=2`)
- lowest-budget (`b1=2`) still fragile for strong claims

## 5) Matched method-family results on new regime

Methods:
- anchor: `intervention::pointwise`
- broad: `external::prm800k_pointwise_blend_from_reweighted_pointwise`
- aligned: `external::prm800k_uncertainty_gated_blend_from_reweighted_pointwise`
- boundary: `external::prm800k_comparator_boundary_tiebreak_from_reweighted_pointwise`

### Aggregate
- anchor: pairwise 0.5667, top1 0.3333
- broad: pairwise 0.6000, top1 0.3333
- aligned: pairwise 0.6000, top1 0.4444
- boundary: pairwise 0.6333, top1 0.3333

### Hard slices
- near-tie: anchor 0.4167, broad 0.4167, aligned 0.4167, boundary 0.5000
- adjacent-rank: anchor 0.5556, broad 0.5000, aligned 0.5000, boundary 0.5556
- small-margin: anchor 0.4545, broad 0.5000, aligned 0.5000, boundary 0.5455

### Exact/provenance slices
- exact-promoted (n=2): anchor 0.0, broad 0.5, aligned 0.5, boundary 0.5
- exact-only (n=2): anchor 0.0, broad 0.5, aligned 0.5, boundary 0.5
- approx-only (n=28): anchor 0.6071, broad 0.6071, aligned 0.6071, boundary 0.6429

### Budget slices
- b1 (n=2): anchor 1.0, broad 0.5, aligned 0.5, boundary 1.0
- b2 (n=6): all methods 0.5
- b3 (n=9): anchor 0.4444, broad 0.5556, aligned 0.5556, boundary 0.5556
- b4 (n=13): anchor 0.6154, broad 0.6923, aligned 0.6923, boundary 0.6923

### Boundary diagnostics
- boundary-eligible pairs: 9/30 (30%)
- changed pairs: 2 (both helpful; none harmful)
- changed top-1 states: 0/9

## 6) Conservative diagnosis
1. **Evaluation support improved materially** on the targeted slices (test pairs, top-1 states, near-tie/adjacent/small-margin, low-budget presence, boundary-eligible support).
2. **Method differences are now somewhat more visible**, especially pairwise boundary > broad/aligned > anchor and aligned top1 > broad top1.
3. **Broad vs aligned pairwise still tie**; only top-1 differs here (aligned +0.1111).
4. **Boundary remains mostly diagnostic** for top-1 (no top-1 state flips), though pairwise boundary is strongest on this run.
5. **Exact-promoted support is improved but still small** (`n=2`), so claims about that slice remain weak.

## 7) Math-Shepherd readiness
Still wait. This pass materially improved evidence quality and slice coverage, but broad-vs-aligned separation is still limited and exact-promoted/lowest-budget slices remain small.

## Files added/modified
- Added: `docs/CANONICAL_EXTERNAL_SUPERVISION_PRM800K_LOW_BUDGET_EXACT_PROMOTED_SUPPORT_EXPANSION_PASS_2026_04_16.md`
- Added: `docs/canonical_external_supervision_prm800k_low_budget_exact_promoted_support_expansion_pass_2026_04_16_summary.json`

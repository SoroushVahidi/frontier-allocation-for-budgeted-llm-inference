# Canonical external-supervision pass: PRM800K exact-promoted coverage (2026-04-16)

## Objective
Create one provenance-safe canonical regime with non-zero **held-out exact-promoted** support, then rerun the matched PRM800K comparison (anchor vs broad vs aligned vs boundary) without changing architecture, task definition, or external dataset family.

## What changed in this pass

### 1) Exact-promoted-aware regime construction
We kept the existing internal hard-region promotion workflow and fixed one provenance metadata gap so exact-promoted rows are explicitly marked as replacements:

- `scripts/build_bruteforce_target_regimes.py`
  - promoted exact rows now set `replaced_approx_label=true`
  - promoted exact rows now set `pair_mode_provenance="exact"`
  - non-promoted rows set `replaced_approx_label=false`

This preserves task semantics and only improves canonical slice observability.

### 2) Canonical corpus path for this pass
- `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_harder_exactpromoted_v1`

### 3) External artifact path (unchanged name)
- `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`

## Exact commands run

```bash
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id epcov_gsm8k_approx_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 17 --max-frontier-states 24 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 4
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id epcov_math500_approx_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 17 --max-frontier-states 24 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 4
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id epcov_gsm8k_exact_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 29 --max-frontier-states 10 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 2 --max-remaining-budget 3 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 3 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 2
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id epcov_math500_exact_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 29 --max-frontier-states 10 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 2 --max-remaining-budget 3 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 3 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 2
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/epcov_approx_runs.txt --output-dir outputs/branch_label_bruteforce_merged --run-id epcov_multi_dataset_merged_20260416_v1 --near-tie-margin 0.04
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/epcov_exact_runs.txt --output-dir outputs/branch_label_bruteforce_merged --run-id epcov_exact_merged_20260416_v1 --near-tie-margin 0.04
python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce_merged/epcov_multi_dataset_merged_20260416_v1 --output-dir outputs/branch_label_bruteforce_targets --run-id epcov_target_regimes_20260416 --pair-strategies all_pairs,adjacent_rank,top_vs_rest,uncertainty_filtered --near-tie-margin 0.04 --high-margin-threshold 0.10 --max-pair-std 0.08 --exact-labels-dir outputs/branch_label_bruteforce_merged/epcov_exact_merged_20260416_v1 --promote-exact-over-approx --tie-abs-margin-threshold 0.04 --tie-relative-margin-threshold 0.20 --tie-std-threshold 0.08 --tie-use-near-tie-flag --tie-include-approx
python scripts/build_canonical_branch_learning_corpus.py --base-labels-dir outputs/branch_label_bruteforce_merged/epcov_multi_dataset_merged_20260416_v1 --regime-root-dir outputs/branch_label_bruteforce_targets/epcov_target_regimes_20260416 --output-root outputs/branch_learning_corpora --run-id real_branch_learning_corpus_20260416_harder_exactpromoted_v1 --split-seed 4 --train-ratio 0.75 --val-ratio 0.10 --near-tie-margin 0.04 --small-margin-threshold 0.10
python scripts/build_external_prm_mathshepherd_apps_corpus.py --output-root outputs/branch_learning_corpora_external --run-id external_prm_mathshepherd_apps_20260416 --max-rows-per-dataset 128
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_harder_exactpromoted_v1 --output-root outputs/canonical_branch_learning_pass --run-id exactpromoted_transfer_alignment_20260416 --seed 17 --near-tie-margin 0.04 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_uncertainty_gated_blend --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_harder_exactpromoted_v1 --output-root outputs/canonical_branch_learning_pass --run-id exactpromoted_boundary_20260416 --seed 17 --near-tie-margin 0.04 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_comparator_boundary_tiebreak --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02
```

## Support counts (first-class)

### Corpus-level support (`real_branch_learning_corpus_20260416_harder_exactpromoted_v1`)
- pairwise rows: 194
- pairwise split counts: train 129 / val 36 / test 29
- exact-promoted pairs: 16 (**non-zero**)
- near-tie pairs: 58
- small-margin pairs: 140
- adjacent-rank pairs: 110

### Held-out matched evaluation support (runner test slice)
- total test pairs: 18
- total top-1 states: 4
- near-tie: 5
- small-margin: 14
- adjacent-rank: 10
- exact-promoted: 1 (**non-zero**)
- exact-only: 1
- approx-only: 17
- dataset slices:
  - `HuggingFaceH4/MATH-500`: 6
  - `openai/gsm8k`: 12
- budget slices:
  - budget 2: 6
  - budget 3: 6
  - budget 4: 6

## Matched anchor vs broad vs aligned vs boundary

Methods:
- anchor: `intervention::pointwise`
- broad: `external::prm800k_pointwise_blend_from_reweighted_pointwise`
- aligned: `external::prm800k_uncertainty_gated_blend_from_reweighted_pointwise`
- boundary: `external::prm800k_comparator_boundary_tiebreak_from_reweighted_pointwise`

| Method | Pairwise acc (n=18) | Top-1 acc | Near-tie acc (n=5) | Small-margin acc (n=14) | Adjacent-rank acc (n=10) | Exact-promoted acc (n=1) |
|---|---:|---:|---:|---:|---:|---:|
| Anchor | 0.4444 | 0.0000 | 0.4000 | 0.3571 | 0.5000 | 0.0000 |
| Broad | 0.5556 | 0.0000 | 0.6000 | 0.4286 | 0.5000 | 1.0000 |
| Aligned | 0.5556 | 0.0000 | 0.6000 | 0.4286 | 0.5000 | 1.0000 |
| Boundary | 0.5556 | 0.0000 | 0.6000 | 0.4286 | 0.5000 | 1.0000 |

Boundary diagnostics:
- eligible boundary pairs: 6 / 18 (33.33%)
- changed pairs: 2 (both helpful pairwise)
- changed top-1 states: 0 / 4

## Conservative interpretation

1. **Coverage quality improved**: held-out exact-promoted support is now measurable (`n=1`) instead of zero.
2. **Broad still ties aligned** on every reported metric in this pass.
3. **Boundary remains diagnostic**: it produces helpful pairwise flips but still does not improve top-1 in this run.
4. **External supervision signal on exact-promoted is suggestive but weak**: broad/aligned/boundary are correct on the single exact-promoted test pair while anchor misses it, but `n=1` is too sparse for strong claims.
5. This pass improves evaluation evidence quality but does **not** yet establish a robust method winner on exact-promoted behavior.

## Is Math-Shepherd justified now?
Not yet. This pass repaired the primary blind spot (exact-promoted held-out support > 0), but the measured slice is still too small (`n=1`) and broad/aligned remain tied. One more matched pass should increase exact-promoted held-out support before introducing a new external dataset family.

## Files added/modified in this pass
- Modified: `scripts/build_bruteforce_target_regimes.py`
- Added: `docs/CANONICAL_EXTERNAL_SUPERVISION_PRM800K_EXACT_PROMOTED_COVERAGE_PASS_2026_04_16.md`
- Added: `docs/canonical_external_supervision_prm800k_exact_promoted_coverage_pass_2026_04_16_summary.json`

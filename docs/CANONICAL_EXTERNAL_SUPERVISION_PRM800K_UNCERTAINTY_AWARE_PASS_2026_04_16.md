# Canonical external-supervision pass: PRM800K uncertainty-aware supervision (2026-04-16)

## Objective
Test one bounded uncertainty-aware supervision strategy that keeps the same branch-priority / next-step allocation setting and same method family, to see whether uncertainty-aware supervision makes external PRM signal more decision-aligned on hard slices.

## Uncertainty/provenance signals already available (no new model family)

### Canonical internal corpus signals
From canonical candidate/pairwise rows:
- candidate uncertainty proxy: `allocation_value_std`
- pair uncertainty proxy: `pair_uncertainty_std_mean`
- ambiguity/hardness flags: `near_tie_flag`, `small_margin_flag`, `margin_abs`, `relative_margin`, `pair_type` (adjacent-rank)
- provenance/supervision type: `is_exact_label`, `is_approx_label`, `label_source`
- exact-promoted provenance: `replaced_approx_label`
- budget-aware slicing: `remaining_budget`

### External PRM signals
From external PRM candidate rows:
- supervision score: `quality_score`
- provenance keys: `source_dataset_key`, `source_split`, `supervision_origin`
- budget field: `remaining_budget`

No native external variance field is stored, so this pass uses the already-implemented derived uncertainty proxy used in feature mapping:
- `derived_external_uncertainty_std = quality_score * (1 - quality_score)`

## Chosen strategy (single bounded intervention)
**External PRM uncertainty filtering before prior fit**:
- Keep only external PRM rows with `derived_external_uncertainty_std <= 0.05` when fitting external prior.
- Everything else stays matched (same corpus, same internal anchor, same broad/aligned/boundary family, same thresholds and blend alpha).

Implementation change:
- `scripts/run_canonical_branch_learning_pass.py`
  - added `--external-prm-max-uncertainty-std` (default `1.0`, no-op)
  - external prior fitting now filters candidate rows by derived uncertainty threshold before training external ridge prior
  - metadata now records `external_prm_max_uncertainty_std`, plus `prior_fit.n_prefilter` and filtered `prior_fit.n`

## Exact artifact paths used
- Canonical corpus:
  - `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_harder_uncertainty_v1`
- External PRM artifact (kept path):
  - `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`
- Control matched runs:
  - `outputs/canonical_branch_learning_pass/ua_control_transfer_alignment_20260416`
  - `outputs/canonical_branch_learning_pass/ua_control_boundary_20260416`
- Uncertainty-filtered matched runs:
  - `outputs/canonical_branch_learning_pass/ua_filtered_transfer_alignment_20260416`
  - `outputs/canonical_branch_learning_pass/ua_filtered_boundary_20260416`

## Exact commands run
```bash
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id ua_gsm8k_approx_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 17 --max-frontier-states 24 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 4
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id ua_math500_approx_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 17 --max-frontier-states 24 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 4
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id ua_gsm8k_exact_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 29 --max-frontier-states 10 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 2 --max-remaining-budget 3 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 3 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 2
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id ua_math500_exact_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 29 --max-frontier-states 10 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 2 --max-remaining-budget 3 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 3 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 2
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/ua_approx_runs.txt --output-dir outputs/branch_label_bruteforce_merged --run-id ua_multi_dataset_merged_20260416_v1 --near-tie-margin 0.04
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/ua_exact_runs.txt --output-dir outputs/branch_label_bruteforce_merged --run-id ua_exact_merged_20260416_v1 --near-tie-margin 0.04
python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce_merged/ua_multi_dataset_merged_20260416_v1 --output-dir outputs/branch_label_bruteforce_targets --run-id ua_target_regimes_20260416 --pair-strategies all_pairs,adjacent_rank,top_vs_rest,uncertainty_filtered --near-tie-margin 0.04 --high-margin-threshold 0.10 --max-pair-std 0.08 --exact-labels-dir outputs/branch_label_bruteforce_merged/ua_exact_merged_20260416_v1 --promote-exact-over-approx --tie-abs-margin-threshold 0.04 --tie-relative-margin-threshold 0.20 --tie-std-threshold 0.08 --tie-use-near-tie-flag --tie-include-approx
python scripts/build_canonical_branch_learning_corpus.py --base-labels-dir outputs/branch_label_bruteforce_merged/ua_multi_dataset_merged_20260416_v1 --regime-root-dir outputs/branch_label_bruteforce_targets/ua_target_regimes_20260416 --output-root outputs/branch_learning_corpora --run-id real_branch_learning_corpus_20260416_harder_uncertainty_v1 --split-seed 4 --train-ratio 0.75 --val-ratio 0.10 --near-tie-margin 0.04 --small-margin-threshold 0.10
python scripts/build_external_prm_mathshepherd_apps_corpus.py --output-root outputs/branch_learning_corpora_external --run-id external_prm_mathshepherd_apps_20260416 --max-rows-per-dataset 128
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_harder_uncertainty_v1 --output-root outputs/canonical_branch_learning_pass --run-id ua_control_transfer_alignment_20260416 --seed 17 --near-tie-margin 0.04 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_uncertainty_gated_blend --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-prm-max-uncertainty-std 1.0
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_harder_uncertainty_v1 --output-root outputs/canonical_branch_learning_pass --run-id ua_control_boundary_20260416 --seed 17 --near-tie-margin 0.04 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_comparator_boundary_tiebreak --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02 --external-prm-max-uncertainty-std 1.0
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_harder_uncertainty_v1 --output-root outputs/canonical_branch_learning_pass --run-id ua_filtered_transfer_alignment_20260416 --seed 17 --near-tie-margin 0.04 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_uncertainty_gated_blend --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-prm-max-uncertainty-std 0.05
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_harder_uncertainty_v1 --output-root outputs/canonical_branch_learning_pass --run-id ua_filtered_boundary_20260416 --seed 17 --near-tie-margin 0.04 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_comparator_boundary_tiebreak --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02 --external-prm-max-uncertainty-std 0.05
```

## Support counts (first-class)

### Corpus-level (`real_branch_learning_corpus_20260416_harder_uncertainty_v1`)
- pairwise rows: 194
- split pairwise rows: train 129 / val 36 / test 29
- near-tie: 58
- adjacent-rank: 110
- small-margin: 140
- exact-promoted: 16

### Held-out matched evaluation support (same for control + filtered)
- total test pairs: 18
- total top-1 states: 4
- near-tie: 5
- adjacent-rank: 10
- small-margin: 14
- exact-promoted: 1 (**too small**)
- exact-only: 1 (**too small**)
- approx-only: 17
- dataset slices:
  - `HuggingFaceH4/MATH-500`: 6
  - `openai/gsm8k`: 12
- budget slices:
  - budget 2: 6
  - budget 3: 6
  - budget 4: 6

## Strategy effect on external prior data
- control (`external_prm_max_uncertainty_std=1.0`): retained 6616 / 6616 rows
- filtered (`external_prm_max_uncertainty_std=0.05`): retained 5237 / 6616 rows
- dropped as high-uncertainty: 1379 rows (20.84%)

## Matched comparison (anchor vs broad vs aligned vs boundary)

### Control (no external uncertainty filter)
- anchor: pairwise 0.4444, top-1 0.0000
- broad: pairwise 0.5556, top-1 0.0000
- aligned: pairwise 0.5556, top-1 0.0000
- boundary: pairwise 0.5556, top-1 0.0000
- broad vs aligned: **tied**

### Uncertainty-filtered external prior (`<=0.05`)
- anchor: pairwise 0.4444, top-1 0.0000
- broad: pairwise 0.5000, top-1 0.2500
- aligned: pairwise 0.5000, top-1 0.2500
- boundary: pairwise 0.5000, top-1 0.0000
- broad vs aligned: **still tied**

### Hard-slice + provenance deltas (filtered vs control)
- near-tie (n=5): broad/aligned 0.60 -> 0.40 (worse)
- adjacent-rank (n=10): broad/aligned 0.50 -> 0.40 (worse)
- small-margin (n=14): broad/aligned 0.4286 -> 0.3571 (worse)
- exact-promoted (n=1): broad/aligned 1.0 -> 0.0 (worse, but tiny support)
- approx-only (n=17): broad/aligned unchanged 0.5294
- boundary diagnostics: changed pairs 2 -> 1, no top-1 state changes in either run

### Budget slices (broad; aligned identical)
- budget 2 (n=6): 0.50 -> 0.50 (flat)
- budget 3 (n=6): 0.6667 -> 0.50 (worse)
- budget 4 (n=6): 0.50 -> 0.50 (flat)

## Conservative interpretation
1. This pass improved **control over supervision filtering** (we can now bound external supervision by an explicit uncertainty threshold) and improved **evidence quality** around that intervention.
2. It did **not** reduce the core bottleneck in this run: hard-slice pairwise metrics generally worsened under filtering.
3. Broad and aligned are still tied (no separation emerged).
4. Boundary remains diagnostic; it does not become top-1 useful here.
5. Exact-promoted held-out support is measurable but still too small (`n=1`) for strong conclusions.

## Recommendation on Math-Shepherd
Still wait. This bounded uncertainty-aware filtering pass did not materially improve broad-vs-aligned separation or hard-slice reliability, so evidence quality improved operationally, but not enough to justify shifting to Math-Shepherd yet.

## Files added/modified
- Modified: `scripts/run_canonical_branch_learning_pass.py`
- Added: `docs/CANONICAL_EXTERNAL_SUPERVISION_PRM800K_UNCERTAINTY_AWARE_PASS_2026_04_16.md`
- Added: `docs/canonical_external_supervision_prm800k_uncertainty_aware_pass_2026_04_16_summary.json`

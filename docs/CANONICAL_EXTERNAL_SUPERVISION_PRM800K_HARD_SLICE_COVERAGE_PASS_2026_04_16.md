# Canonical hard-slice coverage pass (PRM800K) — 2026-04-16

## Objective

Build one harder, provenance-safe canonical evaluation corpus where hard slices are better represented, then re-run the same matched method family:
- internal anchor,
- broad PRM blend,
- aligned PRM blend,
- boundary PRM variant.

No new architecture or new external dataset was introduced.

## Harder-corpus strategy (conservative)

Used existing internal pipeline only:
1. rebuild base merged internal labels,
2. build an exact-labeled merged set for promotion attempts,
3. construct hard target-regime views (including adjacent-rank and uncertainty-filtered structure),
4. build one canonical corpus using base labels + regime root.

Chosen harder-corpus artifact:
- `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_harder_v1`

External artifact path (unchanged):
- `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`

## Exact commands run

```bash
# Rebuild base internal runs + merged base labels
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id recover_gsm8k_approx_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 17 --max-frontier-states 30 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 2 --max-remaining-budget 5 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 5
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id recover_math500_approx_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 17 --max-frontier-states 30 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 2 --max-remaining-budget 5 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 5
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id recover_gsm8k_exact_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 29 --max-frontier-states 12 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 4 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 3
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id recover_math500_exact_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 29 --max-frontier-states 12 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 4 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 3
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/recover_run_ids.txt --output-dir outputs/branch_label_bruteforce_merged --run-id recover_multi_dataset_merged_20260416_v2 --near-tie-margin 0.03

# Build exact-labeled merged set used for promotion attempt inside regimes
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id hard_exactmatch_gsm8k_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 17 --max-frontier-states 20 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 2 --max-remaining-budget 5 --init-branches 4 --max-branches-per-state 5 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 5 --rollout-samples-per-candidate 16 --max-allocation-samples 64 --progress-every 4
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id hard_exactmatch_math500_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 17 --max-frontier-states 20 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 2 --max-remaining-budget 5 --init-branches 4 --max-branches-per-state 5 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 5 --rollout-samples-per-candidate 16 --max-allocation-samples 64 --progress-every 4
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/hard_exact_run_ids.txt --output-dir outputs/branch_label_bruteforce_merged --run-id harder_exact_merged_20260416_v1 --near-tie-margin 0.03

# Build hard target regimes + canonical harder corpus
python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce_merged/recover_multi_dataset_merged_20260416_v2 --output-dir outputs/branch_label_bruteforce_targets --run-id harder_target_regimes_20260416 --pair-strategies all_pairs,adjacent_rank,top_vs_rest,uncertainty_filtered --near-tie-margin 0.04 --high-margin-threshold 0.10 --max-pair-std 0.08 --exact-labels-dir outputs/branch_label_bruteforce_merged/harder_exact_merged_20260416_v1 --promote-exact-over-approx --tie-abs-margin-threshold 0.04 --tie-relative-margin-threshold 0.20 --tie-std-threshold 0.08 --tie-use-near-tie-flag --tie-include-approx
python scripts/build_canonical_branch_learning_corpus.py --base-labels-dir outputs/branch_label_bruteforce_merged/recover_multi_dataset_merged_20260416_v2 --regime-root-dir outputs/branch_label_bruteforce_targets/harder_target_regimes_20260416 --output-root outputs/branch_learning_corpora --run-id real_branch_learning_corpus_20260416_harder_v1 --split-seed 17 --train-ratio 0.75 --val-ratio 0.10 --near-tie-margin 0.04 --small-margin-threshold 0.10

# External artifact (fixed path)
python scripts/build_external_prm_mathshepherd_apps_corpus.py --output-root outputs/branch_learning_corpora_external --run-id external_prm_mathshepherd_apps_20260416 --max-rows-per-dataset 128

# Matched PRM comparisons on harder corpus
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_harder_v1 --output-root outputs/canonical_branch_learning_pass --run-id harder_transfer_alignment_20260416 --seed 17 --near-tie-margin 0.04 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_uncertainty_gated_blend --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04
python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_harder_v1 --output-root outputs/canonical_branch_learning_pass --run-id harder_boundary_20260416 --seed 17 --near-tie-margin 0.04 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_comparator_boundary_tiebreak --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02
```

## Support counts (harder regime)

### Corpus-level support (`real_branch_learning_corpus_20260416_harder_v1`)
- pairwise rows: 290
- candidate rows: 216
- split pairwise test rows: 23
- near-tie pairs: 108
- small-margin pairs: 195
- adjacent-rank pairs: 163
- exact-promoted pairs: 0
- pairwise exact vs approx: exact=208, approx=82
- dataset counts: MATH-500=145, GSM8K=145
- budget counts: b2=40, b3=64, b4=88, b5=98

### Evaluation test support (anchor slices)
- total test pairs: 42
- total top-1 test states: 8
- near-tie n: 14
- adjacent-rank n: 23
- small-margin n: 29
- exact-promoted n: 0
- exact-only n: 27
- approx-only n: 15
- dataset test n: MATH-500=30, GSM8K=12
- budget test n: b2=1, b3=2, b4=17, b5=22

## Matched comparison results on harder corpus

| Method | Pairwise acc (n=42) | Top-1 acc | Near-tie acc (n=14) | Adjacent-rank acc (n=23) | Small-margin acc (n=29) |
|---|---:|---:|---:|---:|---:|
| Anchor (`reweighted::pointwise`) | 0.5238 | 0.0000 | 0.6429 | 0.4348 | 0.5517 |
| Broad PRM blend | 0.5238 | 0.1250 | 0.5714 | 0.4783 | 0.5517 |
| Aligned PRM blend | 0.5238 | 0.1250 | 0.5714 | 0.4783 | 0.5517 |
| Boundary PRM variant | 0.5476 | 0.0000 | 0.6429 | 0.5217 | 0.5862 |

### Broad vs aligned distinguishability
- Broad and aligned are still tied on aggregate pairwise accuracy.
- Broad and aligned are also tied on near-tie, adjacent-rank, and small-margin in this run.
- Aligned activity is behaviorally active (candidate changes and pair decision changes exist), but not distinguishable from broad on the measured metrics here.

### Boundary diagnostics
- eligible boundary pairs: 22 / 42
- changed pair decisions: 3 (helpful=2, harmful=1, net=+1)
- changed hard-slice pairs: 2
- top-1 changed states: 0 / 8

## Conservative diagnosis

1. This pass successfully built a clearly harder internal regime with substantial adjacent-rank and small-margin support and a non-trivial exact-vs-approx mix.
2. Broad vs aligned PRM usage still did **not** separate on metrics in this harder run.
3. Boundary remains useful diagnostically and is now slightly better than anchor on aggregate pairwise here, but still no top-1 benefit.
4. Exact-promoted coverage remains zero in this regime, so one key slice is still missing.
5. The repo is **not yet** in a position to justify moving to Math-Shepherd.

## Files added/modified

- `docs/CANONICAL_EXTERNAL_SUPERVISION_PRM800K_HARD_SLICE_COVERAGE_PASS_2026_04_16.md`
- `docs/canonical_external_supervision_prm800k_hard_slice_coverage_pass_2026_04_16_summary.json`

## Recommendation for next pass

Keep method family fixed and run one bounded exact-promoted coverage pass (same pipeline, explicit promoted-exact overlap targets) so that broad vs aligned can be tested on non-zero exact-promoted support before any Math-Shepherd decision.

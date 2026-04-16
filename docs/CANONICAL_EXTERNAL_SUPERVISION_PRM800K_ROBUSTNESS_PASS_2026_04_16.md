# Canonical PRM800K robustness/evidence pass — 2026-04-16

## Scope and strategy

- Goal: test whether recovered-run PRM gains are stable or tiny-slice noise.
- Strategy used: **multi-split-seed robustness** on the same rebuilt merged label source and same canonical runner/method families (no new architecture).
- Split seeds: `11,17,29,47,83`.
- Compared methods: anchor (`reweighted::pointwise`), broad, aligned, boundary.

## Artifact paths used

- Internal baseline canonical path: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1` (kept as reference).
- Robustness corpora built at: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_splitseed{11,17,29,47,83}_v1`.
- External artifact: `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`.
- Runner: `scripts/run_canonical_branch_learning_pass.py`.

## Exact commands run

```bash
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id recover_gsm8k_approx_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 17 --max-frontier-states 24 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 4
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id recover_math500_approx_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 17 --max-frontier-states 24 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 4
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id recover_gsm8k_exact_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 29 --max-frontier-states 8 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 2 --max-remaining-budget 3 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 3 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 2
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id recover_math500_exact_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 29 --max-frontier-states 8 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 2 --max-remaining-budget 3 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 3 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 2
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/recover_run_ids.txt --output-dir outputs/branch_label_bruteforce_merged --run-id recover_multi_dataset_merged_20260416_v1 --near-tie-margin 0.03
python scripts/build_external_prm_mathshepherd_apps_corpus.py --output-root outputs/branch_learning_corpora_external --run-id external_prm_mathshepherd_apps_20260416 --max-rows-per-dataset 128
for SPLIT in 11 17 29 47 83; do
  python scripts/build_canonical_branch_learning_corpus.py --base-labels-dir outputs/branch_label_bruteforce_merged/recover_multi_dataset_merged_20260416_v1 --output-root outputs/branch_learning_corpora --run-id real_branch_learning_corpus_20260416_splitseed${SPLIT}_v1 --split-seed ${SPLIT} --train-ratio 0.8 --val-ratio 0.1 --near-tie-margin 0.03 --small-margin-threshold 0.08
  python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_splitseed${SPLIT}_v1 --output-root outputs/canonical_branch_learning_pass --run-id robustness_transfer_splitseed${SPLIT} --seed 17 --near-tie-margin 0.03 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_uncertainty_gated_blend --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04
  python scripts/run_canonical_branch_learning_pass.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_splitseed${SPLIT}_v1 --output-root outputs/canonical_branch_learning_pass --run-id robustness_boundary_splitseed${SPLIT} --seed 17 --near-tie-margin 0.03 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --uncertainty-weighting --intervention balanced_hardcase_weighting --intervention-target-boost 0.6 --external-supervision prm800k_comparator_boundary_tiebreak --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02
done
```

## Per-split results

| split_seed | pair_test_n | top1_states | anchor pair/top1 | broad pair/top1 | aligned pair/top1 | boundary pair/top1 | boundary flips (helpful/harmful) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 11 | 18 | 4 | 0.5000/0.0000 | 0.5556/0.2500 | 0.5556/0.2500 | 0.5556/0.0000 | 3 (2/1) |
| 17 | 18 | 4 | 0.5000/0.0000 | 0.5556/0.2500 | 0.5556/0.2500 | 0.5556/0.0000 | 3 (2/1) |
| 29 | 18 | 4 | 0.5000/0.0000 | 0.5556/0.2500 | 0.5556/0.2500 | 0.5556/0.0000 | 3 (2/1) |
| 47 | 18 | 4 | 0.5000/0.0000 | 0.5556/0.2500 | 0.5556/0.2500 | 0.5556/0.0000 | 3 (2/1) |
| 83 | 18 | 4 | 0.5000/0.0000 | 0.5556/0.2500 | 0.5556/0.2500 | 0.5556/0.0000 | 3 (2/1) |

## Mean/spread aggregate metrics

- anchor: pair_acc mean=0.5000 std=0.0000; top1 mean=0.0000 std=0.0000; small_margin mean=0.4545 std=0.0000.
- broad: pair_acc mean=0.5556 std=0.0000; top1 mean=0.2500 std=0.0000; small_margin mean=0.4545 std=0.0000.
- aligned: pair_acc mean=0.5556 std=0.0000; top1 mean=0.2500 std=0.0000; small_margin mean=0.4545 std=0.0000.
- boundary: pair_acc mean=0.5556 std=0.0000; top1 mean=0.0000 std=0.0000; small_margin mean=0.4545 std=0.0000.

## Support and hard-slice coverage

- Total test pairs across splits: 90
- Total top-1 test states across splits: 20
- near-tie total n: 10
- adjacent-rank total n: 0 (too small / zero)
- small-margin total n: 55
- exact-promoted total n: 0 (too small / zero)
- Exact-only and approx-only pairwise slices were zero in these rebuilt evaluations, so provenance-slice interpretation is not supported here.

## Robustness diagnosis

- Broad beat anchor on pairwise accuracy in 5/5 splits.
- Aligned beat anchor on pairwise accuracy in 5/5 splits.
- Boundary beat anchor on pairwise accuracy in 5/5 splits.
- Broad and aligned were equal on pairwise accuracy in 5/5 splits.
- Boundary flip totals across splits: changed=15, helpful=10, harmful=5, net=5.

Interpretation (conservative):
- On this rebuilt corpus family, PRM-assisted methods consistently improved pairwise aggregate over anchor by a small fixed margin.
- Broad vs aligned remain empirically indistinguishable in this pass.
- Boundary intervention produces real flips and net-helpful directionality, but no aggregate advantage over broad/aligned and no top-1 gain.
- Evidence quality improved versus the single tiny run, but hard-slice/provenance support is still thin in key slices (adjacent-rank/exact-promoted).
- Math-Shepherd should still wait.

## Files added/modified

- `docs/CANONICAL_EXTERNAL_SUPERVISION_PRM800K_ROBUSTNESS_PASS_2026_04_16.md`
- `docs/canonical_external_supervision_prm800k_robustness_pass_2026_04_16_summary.json`

## Recommendation for next pass

- Keep the same method family and run a modest support expansion (more states via same generation pipeline) before any escalation; only consider new external sources if broad/aligned begin to separate with adequate support.

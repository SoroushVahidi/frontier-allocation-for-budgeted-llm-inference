# Canonical exact-promoted-near-boundary support pass (2026-04-16)

## Objective
Run one narrow support-expansion pass focused on the two remaining bottleneck protected strata:
- exact-promoted / near-boundary
- extreme-low-budget / boundary-eligible

while keeping the task, method family, external PRM path, and boundary-sensitive protocol fixed.

## 1) Remaining underpowered strata before this pass
Using the previous best expanded holdout (from the prior protected-strata pass), current support was:
- exact-promoted / near-boundary: **1**
- exact-promoted / non-boundary: **1**
- low-budget / near-boundary: **6**
- extreme-low-budget / boundary-eligible: **0**
- exact-only: **2**
- approx-only: **39**
- boundary-eligible overall: **16**
- pivot-boundary eligible states: **6**

Why still underpowered for strong conclusions:
- exact-promoted-near-boundary had only one row (single-example fragility).
- extreme-low-budget-boundary remained zero (unmeasurable stratum).
- broad vs aligned were tied on aggregate and hard slices, so targeted strata remained the key differentiator needed for interpretation.

## 2) Bounded strategy used (single strategy)

### Strategy
**Targeted low-budget exact-overlap expansion**:
1. Add bounded new b1/b2-focused approx + exact generation runs.
2. Merge with the recovered base low-budget/exact-promoted family.
3. Rebuild exact-promoted target regimes.
4. Rebuild one targeted canonical corpus.
5. Run protected-strata holdout expansion + freeze (same script family, no model changes).

This directly targets exact-promotion opportunities in low-budget states likely to produce comparator-boundary rows.

## 3) Exact commands run
```bash
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_targeted_gsm8k_approx_b1_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 41 --max-frontier-states 28 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 1 --max-remaining-budget 2 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 4
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_targeted_math500_approx_b1_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 41 --max-frontier-states 28 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 1 --max-remaining-budget 2 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 4
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_targeted_gsm8k_exact_b1_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 73 --max-frontier-states 18 --episodes-per-example 1 --frontier-budget 4 --min-remaining-budget 1 --max-remaining-budget 2 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 2 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 3
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_targeted_math500_exact_b1_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 73 --max-frontier-states 18 --episodes-per-example 1 --frontier-budget 4 --min-remaining-budget 1 --max-remaining-budget 2 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 2 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 3

python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/lbep_targeted_approx_runs.txt --output-dir outputs/branch_label_bruteforce_merged --run-id lbep_targeted_multi_dataset_merged_20260416_v2 --near-tie-margin 0.05
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/lbep_targeted_exact_runs.txt --output-dir outputs/branch_label_bruteforce_merged --run-id lbep_targeted_exact_merged_20260416_v2 --near-tie-margin 0.05

python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce_merged/lbep_targeted_multi_dataset_merged_20260416_v2 --output-dir outputs/branch_label_bruteforce_targets --run-id lbep_targeted_target_regimes_20260416_v2 --pair-strategies all_pairs,adjacent_rank,top_vs_rest,uncertainty_filtered --near-tie-margin 0.05 --high-margin-threshold 0.10 --max-pair-std 0.08 --exact-labels-dir outputs/branch_label_bruteforce_merged/lbep_targeted_exact_merged_20260416_v2 --promote-exact-over-approx --tie-abs-margin-threshold 0.05 --tie-relative-margin-threshold 0.20 --tie-std-threshold 0.08 --tie-use-near-tie-flag --tie-include-approx
python scripts/build_canonical_branch_learning_corpus.py --base-labels-dir outputs/branch_label_bruteforce_merged/lbep_targeted_multi_dataset_merged_20260416_v2 --regime-root-dir outputs/branch_label_bruteforce_targets/lbep_targeted_target_regimes_20260416_v2 --output-root outputs/branch_learning_corpora --run-id real_branch_learning_corpus_20260416_lowbudget_exactpromoted_targeted_v2 --split-seed 51 --train-ratio 0.70 --val-ratio 0.10 --near-tie-margin 0.05 --small-margin-threshold 0.10
python scripts/build_external_prm_mathshepherd_apps_corpus.py --output-root outputs/branch_learning_corpora_external --run-id external_prm_mathshepherd_apps_20260416 --max-rows-per-dataset 128

python scripts/run_protected_strata_holdout_expansion.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_targeted_v2 --output-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_exactpromoted_boundary_targeted_holdout_v3 --output-manifest-json outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_targeted_v3_manifest.json --output-holdout-jsonl outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_targeted_v3_holdout.jsonl --output-audit-json outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_targeted_v3_audit.json --baseline-seed 17 --seed-min 1 --seed-max 128 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0

python scripts/run_canonical_boundary_sensitive_evaluation.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_exactpromoted_boundary_targeted_holdout_v3 --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --output-json outputs/canonical_branch_learning_pass/boundary_sensitive_eval_20260416_targeted_v3_seed37.json --seed 37 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --intervention-target-boost 0.6 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02 --external-prm-max-uncertainty-std 1.0 --bootstrap-samples 2000
```

## 4) Canonical identity, frozen holdout, and artifacts

### Artifact paths
- Start corpus family: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1`
- Targeted rebuilt corpus: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_targeted_v2`
- Expanded/frozen corpus: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_exactpromoted_boundary_targeted_holdout_v3`
- External PRM artifact (fixed): `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`
- Frozen holdout manifest JSONL: `outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_targeted_v3_holdout.jsonl`
- Holdout expansion audit: `outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_targeted_v3_audit.json`
- Holdout expansion manifest: `outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_targeted_v3_manifest.json`
- Evaluation JSON: `outputs/canonical_branch_learning_pass/boundary_sensitive_eval_20260416_targeted_v3_seed37.json`

Selected holdout seed: **37**.

The frozen holdout includes:
- stratum assignment,
- provenance flags (`is_exact_label`, `replaced_approx_label`, etc.),
- budget buckets,
- boundary-eligibility indicators,
- pivot/group metadata.

## 5) Old vs new support counts (first-class)
Old = previous pass expanded holdout; New = this targeted pass.

- total test pairs: **41 → 72**
- total top-1 states: **12 → 17**
- near-tie: **23 → 32**
- adjacent-rank: **25 → 42**
- small-margin: **35 → 50**
- exact-promoted: **2 → 5**
- low-budget: **16 → 46**
- extreme-low-budget: **3 → 4**
- boundary-eligible: **16 → 27**
- exact-promoted / near-boundary: **1 → 2**
- extreme-low-budget / boundary-eligible: **0 → 0**

Additional targeted strata:
- exact-promoted / non-boundary: **1 → 3**
- low-budget / near-boundary: **6 → 16**
- exact-only / approx-only: **2/39 → 5/67**

## 6) Boundary-sensitive metrics and uncertainty

### Aggregate
- old: anchor 0.8049, broad 0.7805, aligned 0.7805, boundary 0.7805
- new: anchor 0.6667, broad 0.6806, aligned 0.6806, boundary 0.6806

### Hard slices (new)
- near-tie (`n=32`): anchor 0.7188, broad 0.6875, aligned 0.6875, boundary 0.6875
- adjacent-rank (`n=42`): anchor 0.5476, broad 0.5000, aligned 0.5000, boundary 0.5238
- small-margin (`n=50`): anchor 0.7000, broad 0.6600, aligned 0.6600, boundary 0.6800

### Protected strata (new)
- exact-promoted-near-boundary (`n=2`): anchor/broad/aligned/boundary 0.5
- exact-promoted-non-boundary (`n=3`): anchor/broad/aligned/boundary 0.6667
- approx-near-boundary (`n=25`): anchor 0.6800, broad/aligned/boundary 0.7200
- approx-non-boundary (`n=42`): all methods 0.6667
- low-budget-near-boundary (`n=16`): all methods 0.8750
- low-budget-non-boundary (`n=30`): all methods 0.6000

### Pivot-boundary consistency
- old eligible states: 6; all methods 0.6667
- new eligible states: 6; all methods 0.5000

### Paired bootstrap CIs (new aggregate)
- anchor vs broad: +0.0139 (95% CI: -0.0694, +0.0972)
- anchor vs aligned: +0.0139 (95% CI: -0.0694, +0.0972)
- anchor vs boundary: +0.0139 (95% CI: -0.0417, +0.0698)

Targeted boundary-eligible paired CI (new):
- all three deltas = +0.0370 (95% CI: -0.1481, +0.2222)

## 7) Conservative diagnosis
1. **Support improved materially** on targeted exact-promoted-near-boundary and low-budget boundary slices.
2. **Exact-promoted-near-boundary is still small** (`n=2`), so gains remain fragile.
3. **Extreme-low-budget-boundary remains zero** (`n=0`), still unresolved.
4. **Broad vs aligned still tie** across aggregate and major slices in this run.
5. Improved support increases interpretability, but does not establish a robust method winner.

## 8) Math-Shepherd readiness
Still wait. This pass improved targeted support and interpretability, but the two hardest evidentiary constraints remain:
- extreme-low-budget-boundary still unmeasured,
- broad vs aligned still tied.

## Files added/modified
- Added: `docs/CANONICAL_EXACT_PROMOTED_NEAR_BOUNDARY_SUPPORT_PASS_2026_04_16.md`
- Added: `docs/canonical_exact_promoted_near_boundary_support_pass_2026_04_16_summary.json`

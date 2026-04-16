# Canonical exact-promoted-near-boundary support pass v4 (2026-04-16)

## Objective
Run one additional **narrow**, provenance-safe support-expansion pass for branch-priority/next-step allocation under fixed budget, with method family and evaluation protocol unchanged, to increase held-out support in:
- exact-promoted / near-boundary
- extreme-low-budget / boundary-eligible

Fixed assets and protocols retained:
- Canonical starting family: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1`
- External PRM artifact: `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`
- Protected-strata workflow: `scripts/run_protected_strata_holdout_expansion.py`
- Boundary-sensitive evaluation: `scripts/run_canonical_boundary_sensitive_evaluation.py`
- Method family only: internal anchor, broad PRM blend, aligned PRM blend, boundary PRM variant.

---

## 1) Underpowered strata audit (pre-pass and why this still blocked claims)

Pre-pass reference (old baseline here = recovered canonical v1 evaluated at seed 17):
- exact-promoted / near-boundary: **0**
- exact-promoted / non-boundary: **1**
- low-budget / near-boundary: **1**
- extreme-low-budget / boundary-eligible: **0**
- exact-only / approx-only: **1 / 8**
- boundary-eligible overall: **1**
- pivot-group boundary counts: `openai/gsm8k|budget_2: 1`

Why this blocked strong conclusions:
1. exact-promoted-near-boundary had no support (unidentifiable targeted effect).
2. extreme-low-budget-boundary-eligible remained unmeasured (zero-count stratum).
3. broad vs aligned tied with tiny support, so the tie could not be interpreted as robust equivalence.

---

## 2) Single bounded strategy selected (and only strategy used)

### Strategy: extreme-low-budget exact-overlap mining
A single targeted intervention was used:
- Add **budget=1-only** (`min-remaining-budget=1`, `max-remaining-budget=1`) approx+exact generation runs on the same datasets.
- Merge those runs with the recovered v1 family.
- Rebuild the same regime/corpus family and run protected-strata holdout expansion to freeze a reusable holdout.

This strategy is intentionally narrow: it boosts exact-vs-approx overlap where boundary cases are most plausible (extreme low budget), without changing task, model family, comparator semantics, or evaluation protocol.

---

## 3) Exact commands run

```bash
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_base_gsm8k_approx_20260416_v1 --dataset-name openai/gsm8k --dataset-split test --seed 17 --max-frontier-states 20 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 1 --max-remaining-budget 3 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 20 --max-allocation-samples 56 --progress-every 5
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_base_math500_approx_20260416_v1 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 19 --max-frontier-states 20 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 1 --max-remaining-budget 3 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 20 --max-allocation-samples 56 --progress-every 5
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_base_gsm8k_exact_20260416_v1 --dataset-name openai/gsm8k --dataset-split test --seed 23 --max-frontier-states 14 --episodes-per-example 1 --frontier-budget 4 --min-remaining-budget 1 --max-remaining-budget 2 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 2 --rollout-samples-per-candidate 14 --max-allocation-samples 42 --progress-every 4
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_base_math500_exact_20260416_v1 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 29 --max-frontier-states 14 --episodes-per-example 1 --frontier-budget 4 --min-remaining-budget 1 --max-remaining-budget 2 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 2 --rollout-samples-per-candidate 14 --max-allocation-samples 42 --progress-every 4

python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_epnb_extreme_gsm8k_approx_b1_20260416_v4 --dataset-name openai/gsm8k --dataset-split test --seed 41 --max-frontier-states 30 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 1 --max-remaining-budget 1 --init-branches 5 --max-branches-per-state 6 --rollout-samples-per-candidate 28 --max-allocation-samples 72 --progress-every 5
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_epnb_extreme_math500_approx_b1_20260416_v4 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 43 --max-frontier-states 30 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 1 --max-remaining-budget 1 --init-branches 5 --max-branches-per-state 6 --rollout-samples-per-candidate 28 --max-allocation-samples 72 --progress-every 5
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_epnb_extreme_gsm8k_exact_b1_20260416_v4 --dataset-name openai/gsm8k --dataset-split test --seed 47 --max-frontier-states 22 --episodes-per-example 1 --frontier-budget 4 --min-remaining-budget 1 --max-remaining-budget 1 --init-branches 4 --max-branches-per-state 5 --exact-mode --max-exact-branches 5 --max-exact-remaining-budget 1 --rollout-samples-per-candidate 18 --max-allocation-samples 52 --progress-every 4
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_epnb_extreme_math500_exact_b1_20260416_v4 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 53 --max-frontier-states 22 --episodes-per-example 1 --frontier-budget 4 --min-remaining-budget 1 --max-remaining-budget 1 --init-branches 4 --max-branches-per-state 5 --exact-mode --max-exact-branches 5 --max-exact-remaining-budget 1 --rollout-samples-per-candidate 18 --max-allocation-samples 52 --progress-every 4

python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/lbep_base_approx_runs_v1.txt --output-dir outputs/branch_label_bruteforce_merged --run-id lbep_multi_dataset_merged_20260416_v1 --near-tie-margin 0.05
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/lbep_base_exact_runs_v1.txt --output-dir outputs/branch_label_bruteforce_merged --run-id lbep_exact_merged_20260416_v1 --near-tie-margin 0.05
python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce_merged/lbep_multi_dataset_merged_20260416_v1 --output-dir outputs/branch_label_bruteforce_targets --run-id lbep_target_regimes_20260416_v1 --pair-strategies all_pairs,adjacent_rank,top_vs_rest,uncertainty_filtered --near-tie-margin 0.05 --high-margin-threshold 0.10 --max-pair-std 0.08 --exact-labels-dir outputs/branch_label_bruteforce_merged/lbep_exact_merged_20260416_v1 --promote-exact-over-approx --tie-abs-margin-threshold 0.05 --tie-relative-margin-threshold 0.20 --tie-std-threshold 0.08 --tie-use-near-tie-flag --tie-include-approx
python scripts/build_canonical_branch_learning_corpus.py --base-labels-dir outputs/branch_label_bruteforce_merged/lbep_multi_dataset_merged_20260416_v1 --regime-root-dir outputs/branch_label_bruteforce_targets/lbep_target_regimes_20260416_v1 --output-root outputs/branch_learning_corpora --run-id real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1 --split-seed 51 --train-ratio 0.70 --val-ratio 0.10 --near-tie-margin 0.05 --small-margin-threshold 0.10

python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/lbep_epnb_approx_runs_v4.txt --output-dir outputs/branch_label_bruteforce_merged --run-id lbep_epnb_extreme_targeted_multi_dataset_merged_20260416_v4 --near-tie-margin 0.05
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/lbep_epnb_exact_runs_v4.txt --output-dir outputs/branch_label_bruteforce_merged --run-id lbep_epnb_extreme_targeted_exact_merged_20260416_v4 --near-tie-margin 0.05
python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce_merged/lbep_epnb_extreme_targeted_multi_dataset_merged_20260416_v4 --output-dir outputs/branch_label_bruteforce_targets --run-id lbep_epnb_extreme_target_regimes_20260416_v4 --pair-strategies all_pairs,adjacent_rank,top_vs_rest,uncertainty_filtered --near-tie-margin 0.05 --high-margin-threshold 0.10 --max-pair-std 0.08 --exact-labels-dir outputs/branch_label_bruteforce_merged/lbep_epnb_extreme_targeted_exact_merged_20260416_v4 --promote-exact-over-approx --tie-abs-margin-threshold 0.05 --tie-relative-margin-threshold 0.20 --tie-std-threshold 0.08 --tie-use-near-tie-flag --tie-include-approx
python scripts/build_canonical_branch_learning_corpus.py --base-labels-dir outputs/branch_label_bruteforce_merged/lbep_epnb_extreme_targeted_multi_dataset_merged_20260416_v4 --regime-root-dir outputs/branch_label_bruteforce_targets/lbep_epnb_extreme_target_regimes_20260416_v4 --output-root outputs/branch_learning_corpora --run-id real_branch_learning_corpus_20260416_lowbudget_exactpromoted_epnb_v4 --split-seed 51 --train-ratio 0.70 --val-ratio 0.10 --near-tie-margin 0.05 --small-margin-threshold 0.10

python scripts/run_protected_strata_holdout_expansion.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_epnb_v4 --output-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_exactpromoted_boundary_epnb_holdout_v4 --output-manifest-json outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_epnb_v4_manifest.json --output-holdout-jsonl outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_epnb_v4_holdout.jsonl --output-audit-json outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_epnb_v4_audit.json --baseline-seed 17 --seed-min 1 --seed-max 128 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0

python scripts/build_external_prm_mathshepherd_apps_corpus.py --output-root outputs/branch_learning_corpora_external --run-id external_prm_mathshepherd_apps_20260416 --max-rows-per-dataset 128
python scripts/run_canonical_boundary_sensitive_evaluation.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1 --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --output-json outputs/canonical_branch_learning_pass/boundary_sensitive_eval_20260416_epnb_old_v1_seed17.json --seed 17 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --intervention-target-boost 0.6 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02 --external-prm-max-uncertainty-std 1.0 --bootstrap-samples 2000
python scripts/run_canonical_boundary_sensitive_evaluation.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_exactpromoted_boundary_epnb_holdout_v4 --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --output-json outputs/canonical_branch_learning_pass/boundary_sensitive_eval_20260416_epnb_new_v4_seed35.json --seed 35 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --intervention-target-boost 0.6 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02 --external-prm-max-uncertainty-std 1.0 --bootstrap-samples 2000
```

---

## 4) Frozen holdout and canonical artifact paths

- Expanded corpus: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_exactpromoted_boundary_epnb_holdout_v4`
- Holdout manifest: `outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_epnb_v4_manifest.json`
- Holdout JSONL: `outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_epnb_v4_holdout.jsonl`
- Holdout audit: `outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_epnb_v4_audit.json`
- Support audit (old/new): `outputs/canonical_branch_learning_pass/epnb_support_audit_old_new_v4.json`
- Evaluation old/new:
  - `outputs/canonical_branch_learning_pass/boundary_sensitive_eval_20260416_epnb_old_v1_seed17.json`
  - `outputs/canonical_branch_learning_pass/boundary_sensitive_eval_20260416_epnb_new_v4_seed35.json`

Selected frozen holdout seed: **35**.

The frozen JSONL rows include:
- explicit protected strata assignments,
- provenance flags,
- budget buckets,
- boundary-eligibility indicators,
- pivot branch id and group metadata.

---

## 5) Old vs new support counts (first-class)

Old = recovered canonical v1 test split (seed 17).
New = expanded + frozen v4 holdout corpus (seed 35).

- total test pairs: **9 → 27**
- top-1 states: **2 → 10**
- near-tie: **3 → 10**
- adjacent-rank: **5 → 18**
- small-margin: **6 → 19**
- exact-promoted: **1 → 6**
- low-budget (≤2): **3 → 17**
- extreme-low-budget (≤1): **0 → 8**
- boundary-eligible overall: **1 → 14**
- exact-promoted / near-boundary: **0 → 3**
- extreme-low-budget / boundary-eligible: **0 → 0**
- exact-promoted / non-boundary: **1 → 3**
- exact-only / approx-only: **1/8 → 6/21**

Pivot-group boundary counts (new):
- `HuggingFaceH4/MATH-500|budget_3`: 6
- `openai/gsm8k|budget_2`: 4
- `openai/gsm8k|budget_3`: 3
- `HuggingFaceH4/MATH-500|budget_2`: 1

---

## 6) Boundary-sensitive evaluation and paired uncertainty

### Aggregate (`all`)
- old (`n=9`): anchor 0.3333, broad 0.3333, aligned 0.3333, boundary 0.3333
- new (`n=27`): anchor 0.4815, broad 0.5185, aligned 0.5185, boundary 0.5185

### Hard slices (new)
- near-tie (`n=10`): anchor/broad/aligned/boundary all 0.4000
- adjacent-rank (`n=18`): anchor 0.4444, broad 0.5000, aligned 0.5000, boundary 0.5000
- small-margin (`n=19`): anchor 0.3158, broad 0.3684, aligned 0.3684, boundary 0.3684

### Protected strata (new)
- exact-promoted-near-boundary (`n=3`): anchor 0.3333, broad/aligned/boundary 0.6667
- exact-promoted-non-boundary (`n=3`): anchor/broad/aligned/boundary all 0.6667
- approx-near-boundary (`n=11`): anchor 0.3636, broad/aligned/boundary 0.3636
- approx-non-boundary (`n=10`): anchor/broad/aligned/boundary 0.6000
- low-budget-near-boundary (`n=5`): anchor/broad/aligned/boundary 0.2000
- low-budget-non-boundary (`n=12`): anchor/broad/aligned/boundary all 0.5000

### Pivot-boundary consistency (new)
- eligible states: 5
- anchor: 0.4
- broad: 0.4
- aligned: 0.4
- boundary: 0.4

### Paired bootstrap CIs (new)
Aggregate (`all`):
- anchor vs broad: +0.0370 (95% CI: 0.0000, 0.1111)
- anchor vs aligned: +0.0370 (95% CI: 0.0000, 0.1111)
- anchor vs boundary: +0.0370 (95% CI: 0.0000, 0.1111)

Boundary-eligible slice:
- anchor vs broad: +0.0714 (95% CI: -0.0714, 0.2143)
- anchor vs aligned: +0.0714 (95% CI: -0.0714, 0.2143)
- anchor vs boundary: +0.0714 (95% CI: -0.0714, 0.2143)

---

## 7) Conservative diagnosis

1. **Support quality improved materially** in one of the two target strata: exact-promoted-near-boundary increased from 0 to 3.
2. **Interpretability improved** because boundary-eligible support increased from 1 to 14 and low-budget-near-boundary grew from 1 to 5.
3. **Extreme-low-budget boundary-eligible remains zero**, so that protected stratum is still unresolved.
4. **Broad vs aligned still tie everywhere checked** in this pass.
5. Evidence is better but still not sufficient to claim robust method superiority among broad/aligned/boundary.

---

## 8) Recommendation on Math-Shepherd pass readiness

**Math-Shepherd should still wait.**

Rationale:
- We improved targeted support and boundary-sensitive interpretability.
- However, one critical protected stratum remains unmeasured (`extreme_low_budget_boundary_eligible = 0`), and broad vs aligned remains tied.
- Another narrow support-expansion pass focused specifically on generating boundary-eligible rows at remaining budget 1 is still higher value than changing model family or adding new external-data complexity.

## Files added/modified in this pass
- Added: `docs/CANONICAL_EXACT_PROMOTED_NEAR_BOUNDARY_SUPPORT_PASS_2026_04_16_V4.md`
- Added: `docs/canonical_exact_promoted_near_boundary_support_pass_2026_04_16_v4_summary.json`

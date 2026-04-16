# Canonical extreme-low-budget boundary support pass v5 (2026-04-16)

## Objective
Run one bounded support-expansion pass focused on the remaining blind spot:
- **extreme-low-budget / boundary-eligible**

while keeping fixed:
- task (branch-priority / next-step allocation under fixed budget),
- method family (anchor, broad, aligned, boundary),
- external PRM artifact path,
- protected-strata holdout workflow,
- boundary-sensitive evaluation protocol.

## 1) Remaining blind-spot audit before this pass (old = v4 frozen setup)

Using `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_exactpromoted_boundary_epnb_holdout_v4` at seed 35:

- extreme-low-budget / boundary-eligible: **0**
- extreme-low-budget / non-boundary: **8**
- low-budget / boundary-eligible: **5**
- exact-promoted / near-boundary: **3**
- exact-promoted / non-boundary: **3**
- boundary-eligible overall: **14**
- total top-1 states: **10**
- boundary pivot/group counts:
  - `HuggingFaceH4/MATH-500|budget_3`: 6
  - `openai/gsm8k|budget_2`: 4
  - `openai/gsm8k|budget_3`: 3
  - `HuggingFaceH4/MATH-500|budget_2`: 1

Why this still blocked strong conclusions:
- The targeted stratum remained **unmeasured** (`n=0`), so method differences at the exact decision-critical corner (`remaining_budget=1`, near comparator boundary) could not be tested.
- Broad vs aligned continued to tie in prior passes, so this missing stratum remained the highest-value unresolved evidentiary gap.

## 2) Single bounded strategy used

### Strategy: remaining-budget-1 small-margin conflict mining
One strategy only:
1. Generate additional approx + exact runs constrained to `remaining_budget=1`.
2. Use higher branch fanout and lower rollout samples to increase small-margin/uncertainty conflict exposure specifically at budget=1.
3. Merge with existing v4-targeted family, rebuild regimes and corpus, then run the same holdout expansion/freeze workflow.

No task change, no new learner family, no comparator feature tweak, and no external dataset change.

## 3) Exact commands run

```bash
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_elb_boundary_gsm8k_approx_b1_20260416_v5 --dataset-name openai/gsm8k --dataset-split test --seed 61 --max-frontier-states 42 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 1 --max-remaining-budget 1 --init-branches 6 --max-branches-per-state 7 --rollout-samples-per-candidate 10 --max-allocation-samples 36 --progress-every 6
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_elb_boundary_math500_approx_b1_20260416_v5 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 67 --max-frontier-states 42 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 1 --max-remaining-budget 1 --init-branches 6 --max-branches-per-state 7 --rollout-samples-per-candidate 10 --max-allocation-samples 36 --progress-every 6
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_elb_boundary_gsm8k_exact_b1_20260416_v5 --dataset-name openai/gsm8k --dataset-split test --seed 71 --max-frontier-states 30 --episodes-per-example 1 --frontier-budget 4 --min-remaining-budget 1 --max-remaining-budget 1 --init-branches 5 --max-branches-per-state 6 --exact-mode --max-exact-branches 6 --max-exact-remaining-budget 1 --rollout-samples-per-candidate 10 --max-allocation-samples 32 --progress-every 5
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_elb_boundary_math500_exact_b1_20260416_v5 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 73 --max-frontier-states 30 --episodes-per-example 1 --frontier-budget 4 --min-remaining-budget 1 --max-remaining-budget 1 --init-branches 5 --max-branches-per-state 6 --exact-mode --max-exact-branches 6 --max-exact-remaining-budget 1 --rollout-samples-per-candidate 10 --max-allocation-samples 32 --progress-every 5

python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/lbep_elb_v5_approx_runs.txt --output-dir outputs/branch_label_bruteforce_merged --run-id lbep_elb_boundary_targeted_multi_dataset_merged_20260416_v5 --near-tie-margin 0.05
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/lbep_elb_v5_exact_runs.txt --output-dir outputs/branch_label_bruteforce_merged --run-id lbep_elb_boundary_targeted_exact_merged_20260416_v5 --near-tie-margin 0.05
python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce_merged/lbep_elb_boundary_targeted_multi_dataset_merged_20260416_v5 --output-dir outputs/branch_label_bruteforce_targets --run-id lbep_elb_boundary_target_regimes_20260416_v5 --pair-strategies all_pairs,adjacent_rank,top_vs_rest,uncertainty_filtered --near-tie-margin 0.05 --high-margin-threshold 0.10 --max-pair-std 0.10 --exact-labels-dir outputs/branch_label_bruteforce_merged/lbep_elb_boundary_targeted_exact_merged_20260416_v5 --promote-exact-over-approx --tie-abs-margin-threshold 0.05 --tie-relative-margin-threshold 0.20 --tie-std-threshold 0.10 --tie-use-near-tie-flag --tie-include-approx
python scripts/build_canonical_branch_learning_corpus.py --base-labels-dir outputs/branch_label_bruteforce_merged/lbep_elb_boundary_targeted_multi_dataset_merged_20260416_v5 --regime-root-dir outputs/branch_label_bruteforce_targets/lbep_elb_boundary_target_regimes_20260416_v5 --output-root outputs/branch_learning_corpora --run-id real_branch_learning_corpus_20260416_lowbudget_exactpromoted_elb_v5 --split-seed 51 --train-ratio 0.70 --val-ratio 0.10 --near-tie-margin 0.05 --small-margin-threshold 0.10

python scripts/run_protected_strata_holdout_expansion.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_elb_v5 --output-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_exactpromoted_boundary_elb_holdout_v5 --output-manifest-json outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_elb_v5_manifest.json --output-holdout-jsonl outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_elb_v5_holdout.jsonl --output-audit-json outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_elb_v5_audit.json --baseline-seed 35 --seed-min 1 --seed-max 192 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0

python scripts/run_canonical_boundary_sensitive_evaluation.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_exactpromoted_boundary_epnb_holdout_v4 --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --output-json outputs/canonical_branch_learning_pass/boundary_sensitive_eval_20260416_elb_old_v4_seed35.json --seed 35 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --intervention-target-boost 0.6 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02 --external-prm-max-uncertainty-std 1.0 --bootstrap-samples 2000
python scripts/run_canonical_boundary_sensitive_evaluation.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_exactpromoted_boundary_elb_holdout_v5 --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --output-json outputs/canonical_branch_learning_pass/boundary_sensitive_eval_20260416_elb_new_v5_seed87.json --seed 87 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --intervention-target-boost 0.6 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02 --external-prm-max-uncertainty-std 1.0 --bootstrap-samples 2000
```

## 4) Canonical identity + frozen holdout artifacts

- Start (old) frozen corpus: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_exactpromoted_boundary_epnb_holdout_v4`
- Targeted rebuilt corpus: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_elb_v5`
- New frozen corpus: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_exactpromoted_boundary_elb_holdout_v5`
- External PRM corpus (fixed): `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`
- Holdout manifest: `outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_elb_v5_manifest.json`
- Holdout JSONL (with strata/provenance/budget/boundary/pivot metadata): `outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_elb_v5_holdout.jsonl`
- Holdout audit: `outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_elb_v5_audit.json`
- Support audit old-vs-new: `outputs/canonical_branch_learning_pass/elb_support_audit_old_v4_new_v5.json`
- Eval old/new JSON:
  - `outputs/canonical_branch_learning_pass/boundary_sensitive_eval_20260416_elb_old_v4_seed35.json`
  - `outputs/canonical_branch_learning_pass/boundary_sensitive_eval_20260416_elb_new_v5_seed87.json`

Selected holdout seed: **87**.

## 5) Old vs new support counts (first-class)

Old = v4 frozen holdout setup (seed 35), New = v5 frozen holdout setup (seed 87).

- total test pairs: **27 → 76**
- top-1 states: **10 → 12**
- near-tie: **10 → 28**
- adjacent-rank: **18 → 38**
- small-margin: **19 → 47**
- exact-promoted: **6 → 14**
- low-budget: **17 → 60**
- extreme-low-budget: **8 → 45**
- boundary-eligible overall: **14 → 11**
- extreme-low-budget / boundary-eligible: **0 → 0**
- exact-promoted / near-boundary: **3 → 7**
- extreme-low-budget / non-boundary: **8 → 45**
- low-budget / boundary-eligible: **5 → 4**
- exact-promoted / non-boundary: **3 → 7**

New pivot/group boundary counts:
- `openai/gsm8k|budget_3`: 4
- `HuggingFaceH4/MATH-500|budget_2`: 3
- `HuggingFaceH4/MATH-500|budget_3`: 3
- `openai/gsm8k|budget_2`: 1

## 6) Boundary-sensitive metrics + paired uncertainty

### Aggregate
- old (`n=27`): anchor 0.4815, broad 0.5185, aligned 0.5185, boundary 0.5185
- new (`n=76`): anchor 0.5921, broad 0.5526, aligned 0.5526, boundary 0.5658

### Hard slices (new)
- near-tie (`n=28`): anchor/broad/aligned/boundary all 0.6429
- adjacent-rank (`n=38`): anchor 0.5526, broad 0.4737, aligned 0.4737, boundary 0.5000
- small-margin (`n=47`): anchor 0.6383, broad 0.6170, aligned 0.6170, boundary 0.6383

### Protected strata (new)
- exact-promoted-near-boundary (`n=7`): anchor 0.5714, broad/aligned/boundary 0.2857
- exact-promoted-non-boundary (`n=7`): all methods 0.5714
- low-budget-near-boundary (`n=4`): all methods 0.5000
- low-budget-non-boundary (`n=56`): all methods 0.6429

### Targeted stratum status
- extreme-low-budget / boundary-eligible: **still 0** (no direct method comparison possible in the intended slice).

### Pivot-boundary consistency
- old: eligible states 5; all methods consistency 0.4
- new: eligible states 5; all methods consistency 0.4

### Paired bootstrap CIs (new)
Aggregate:
- anchor vs broad: -0.0395 (95% CI: -0.0921, 0.0000)
- anchor vs aligned: -0.0395 (95% CI: -0.0921, 0.0000)
- anchor vs boundary: -0.0263 (95% CI: -0.0658, 0.0000)

Boundary-eligible:
- anchor vs broad: -0.1818 (95% CI: -0.4545, 0.0000)
- anchor vs aligned: -0.1818 (95% CI: -0.4545, 0.0000)
- anchor vs boundary: -0.1818 (95% CI: -0.4545, 0.0000)

## 7) Conservative diagnosis

1. **Support increased strongly** in overall low-budget and extreme-low-budget rows, and in exact-promoted-near-boundary rows.
2. **Interpretability improved partially** (more total support), but the targeted slice is still unresolved.
3. **Main success condition not met**: extreme-low-budget / boundary-eligible remained zero.
4. **Broad vs aligned still tie** in aggregate and inspected slices.
5. Apparent aggregate movement in anchor vs others is still tied to non-target slices and should not be over-claimed as method improvement.

## 8) Math-Shepherd readiness recommendation

Still wait.

Reason: this pass did not create measurable held-out support in the final unresolved stratum (`extreme-low-budget / boundary-eligible`), so evidence quality is still insufficient to justify escalating to a Math-Shepherd expansion.

## Files added/modified
- Added: `docs/CANONICAL_EXTREME_LOW_BUDGET_BOUNDARY_SUPPORT_PASS_2026_04_16_V5.md`
- Added: `docs/canonical_extreme_low_budget_boundary_support_pass_2026_04_16_v5_summary.json`

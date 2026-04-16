# Canonical protected-strata artifact-recovery + execution pass (2026-04-16)

## Objective
Recover missing canonical corpus artifacts, execute the protected-strata holdout expansion workflow, freeze a reusable holdout definition, and rerun boundary-sensitive evaluation on the expanded holdout with fixed method family.

## 1) Blocker diagnosis (evidence-based)

### Findings
1. The intended canonical corpus path was missing at pass start:
   - `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1`
2. No canonical row files existed anywhere in `/workspace` at start (`candidate_rows.jsonl`, `pairwise_rows.jsonl`, `outside_option_rows.jsonl` search returned nothing).
3. `outputs/*` is gitignored, including both canonical corpora and external PRM corpus files.
4. Therefore the blocker was **artifact non-materialization in this workspace (plus outputs ignore policy)**, not a method/protocol regression.

## 2) Artifact recovery / rebuild steps

Because no previously materialized corpus artifacts were present, I rebuilt the intended canonical corpus from the recorded low-budget/exact-promoted pipeline and recovered the canonical identity path exactly.

### Recovered canonical identity
- `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1`

### External PRM artifact path (kept fixed)
- `outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416`

### Exact commands run
```bash
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_gsm8k_approx_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 17 --max-frontier-states 40 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 1 --max-remaining-budget 4 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 5
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_math500_approx_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 17 --max-frontier-states 40 --episodes-per-example 1 --frontier-budget 6 --min-remaining-budget 1 --max-remaining-budget 4 --init-branches 4 --max-branches-per-state 5 --rollout-samples-per-candidate 24 --max-allocation-samples 64 --progress-every 5
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_gsm8k_exact_20260416 --dataset-name openai/gsm8k --dataset-split test --seed 29 --max-frontier-states 20 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 1 --max-remaining-budget 3 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 3 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 3
python scripts/run_bruteforce_branch_label_generator.py --output-dir outputs/branch_label_bruteforce --run-id lbep_math500_exact_20260416 --dataset-name HuggingFaceH4/MATH-500 --dataset-split test --seed 29 --max-frontier-states 20 --episodes-per-example 1 --frontier-budget 5 --min-remaining-budget 1 --max-remaining-budget 3 --init-branches 3 --max-branches-per-state 4 --exact-mode --max-exact-branches 4 --max-exact-remaining-budget 3 --rollout-samples-per-candidate 16 --max-allocation-samples 48 --progress-every 3

python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/lbep_approx_runs.txt --output-dir outputs/branch_label_bruteforce_merged --run-id lbep_multi_dataset_merged_20260416_v1 --near-tie-margin 0.05
python scripts/merge_bruteforce_branch_label_runs.py --runs-root outputs/branch_label_bruteforce --run-ids-file /tmp/lbep_exact_runs.txt --output-dir outputs/branch_label_bruteforce_merged --run-id lbep_exact_merged_20260416_v1 --near-tie-margin 0.05
python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce_merged/lbep_multi_dataset_merged_20260416_v1 --output-dir outputs/branch_label_bruteforce_targets --run-id lbep_target_regimes_20260416 --pair-strategies all_pairs,adjacent_rank,top_vs_rest,uncertainty_filtered --near-tie-margin 0.05 --high-margin-threshold 0.10 --max-pair-std 0.08 --exact-labels-dir outputs/branch_label_bruteforce_merged/lbep_exact_merged_20260416_v1 --promote-exact-over-approx --tie-abs-margin-threshold 0.05 --tie-relative-margin-threshold 0.20 --tie-std-threshold 0.08 --tie-use-near-tie-flag --tie-include-approx
python scripts/build_canonical_branch_learning_corpus.py --base-labels-dir outputs/branch_label_bruteforce_merged/lbep_multi_dataset_merged_20260416_v1 --regime-root-dir outputs/branch_label_bruteforce_targets/lbep_target_regimes_20260416 --output-root outputs/branch_learning_corpora --run-id real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1 --split-seed 51 --train-ratio 0.70 --val-ratio 0.10 --near-tie-margin 0.05 --small-margin-threshold 0.10
python scripts/build_external_prm_mathshepherd_apps_corpus.py --output-root outputs/branch_learning_corpora_external --run-id external_prm_mathshepherd_apps_20260416 --max-rows-per-dataset 128
```

## 3) Corpus validation
Validated canonical corpus contract before holdout expansion:
- rows/candidate_rows.jsonl
- rows/pairwise_rows.jsonl
- rows/outside_option_rows.jsonl
- manifest.json
- summaries/corpus_summary.json
- summaries/slice_stats.json
- meta/checksums.json
- meta/schema.json
- meta/source_artifacts.json

Validation result: all required files present.

## 4) Protected-strata expansion execution

### Expansion command (successful)
```bash
python scripts/run_protected_strata_holdout_expansion.py \
  --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1 \
  --output-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_protected_strata_holdout_v1 \
  --output-manifest-json outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_manifest.json \
  --output-holdout-jsonl outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_holdout.jsonl \
  --output-audit-json outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_audit.json \
  --baseline-seed 17 --seed-min 1 --seed-max 128 \
  --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0
```

Selected seed: `56`.

### Expanded artifacts produced
- Expanded split-frozen corpus: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_protected_strata_holdout_v1`
- Frozen holdout rows: `outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_holdout.jsonl`
- Expansion audit: `outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_audit.json`
- Expansion manifest: `outputs/canonical_branch_learning_pass/protected_strata_holdout_expansion_20260416_manifest.json`

## 5) Boundary-sensitive evaluation rerun

### Baseline (old) protocol run
```bash
python scripts/run_canonical_boundary_sensitive_evaluation.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_lowbudget_exactpromoted_v1 --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --output-json outputs/canonical_branch_learning_pass/boundary_sensitive_eval_20260416_recovered_baseline.json --seed 17 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --intervention-target-boost 0.6 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02 --external-prm-max-uncertainty-std 1.0 --bootstrap-samples 2000
```

### Expanded holdout protocol run
```bash
python scripts/run_canonical_boundary_sensitive_evaluation.py --canonical-corpus-dir outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_protected_strata_holdout_v1 --external-prm-corpus-dir outputs/branch_learning_corpora_external/external_prm_mathshepherd_apps_20260416 --output-json outputs/canonical_branch_learning_pass/boundary_sensitive_eval_20260416_protected_strata_expanded_seed56.json --seed 56 --near-tie-margin 0.05 --feature-set v2 --hard-case-mult 1.75 --exact-promoted-mult 2.0 --intervention-target-boost 0.6 --external-source-key prm800k --external-source-split train --external-pointwise-blend-alpha 0.2 --external-gate-uncertainty-std-threshold 0.03 --external-gate-top-gap-threshold 0.04 --external-boundary-pair-margin-threshold 0.02 --external-boundary-pair-uncertainty-std-threshold 0.02 --external-prm-max-uncertainty-std 1.0 --bootstrap-samples 2000
```

## 6) Old vs new support counts (first-class)

Old = baseline seed 17; New = expanded selected seed 56.

- total test pairs: 30 → 41
- total top-1 states: 9 → 12
- near-tie: 12 → 23
- adjacent-rank: 18 → 25
- small-margin: 22 → 35
- exact-promoted: 2 → 2
- exact-only: 2 → 2
- approx-only: 28 → 39
- low-budget (<=2): 8 → 16
- extreme low-budget (<=1): 2 → 3
- boundary-eligible: 4 → 16

### Protected strata
- exact-promoted / near-boundary: 1 → 1
- exact-promoted / non-boundary: 1 → 1
- approximate / near-boundary: 3 → 15
- approximate / non-boundary: 25 → 24
- low-budget / near-boundary: 1 → 6
- low-budget / non-boundary: 7 → 10
- extreme low-budget / boundary-eligible: 0 → 0 (still unresolved)

## 7) Metrics and uncertainty

### Aggregate pairwise accuracy
- old: anchor 0.5333, broad 0.6000, aligned 0.6000, boundary 0.6333
- new: anchor 0.8049, broad 0.7805, aligned 0.7805, boundary 0.7805

### Hard slices
- near-tie (n: 12 → 23):
  - old: anchor 0.4167, broad 0.4167, aligned 0.4167, boundary 0.5000
  - new: anchor 0.7391, broad 0.7391, aligned 0.7391, boundary 0.7391
- adjacent-rank (n: 18 → 25):
  - old: anchor 0.5556, broad 0.5000, aligned 0.5000, boundary 0.5556
  - new: anchor 0.7600, broad 0.6800, aligned 0.6800, boundary 0.6800
- small-margin (n: 22 → 35):
  - old: anchor 0.4545, broad 0.5000, aligned 0.5000, boundary 0.5455
  - new: anchor 0.8000, broad 0.7714, aligned 0.7714, boundary 0.7714

### Protected-strata metrics (new)
- exact-promoted-near-boundary (n=1): all 1.0
- exact-promoted-non-boundary (n=1): all 1.0
- approx-near-boundary (n=15): anchor 0.8000, broad/aligned/boundary 0.7333
- approx-non-boundary (n=24): all 0.7917
- low-budget-near-boundary (n=6): all 0.8333
- low-budget-non-boundary (n=10): all 0.8000

### Pivot-boundary consistency
- old eligible states: 4; anchor 0.25, broad/aligned/boundary 0.50
- new eligible states: 6; all methods 0.6667

### Paired bootstrap CIs (aggregate)
- old: anchor→broad +0.0667 (CI [-0.0667, +0.2000]); anchor→aligned +0.0667 (same); anchor→boundary +0.1000 (CI [0.0000, +0.2333])
- new: anchor→broad -0.0244 (CI [-0.1463, +0.0976]); anchor→aligned -0.0244 (same); anchor→boundary -0.0244 (same)

## 8) Conservative diagnosis
1. **Artifact recovery:** succeeded (canonical + external artifacts rebuilt at intended paths).
2. **Protected-strata expansion execution:** succeeded technically (selected seed, frozen holdout, audit + manifest).
3. **Support quality:** materially improved for near-boundary and low-budget-near-boundary, but **exact-promoted support did not increase** (still n=2 total; 1/1 split across boundary/non-boundary).
4. **Interpretability:** improved due larger boundary-eligible and low-budget-near-boundary support; pivot-boundary consistency sample increased.
5. **Method improvement evidence:** no robust broad/aligned/boundary gain claim; broad and aligned still tie throughout major slices in the expanded run.
6. **Extreme-low-budget boundary stratum:** remains zero and still underpowered.

## 9) Recommendation on Math-Shepherd
Still wait. Evidence quality improved for several protected strata, but exact-promoted and extreme-low-budget-boundary strata remain too sparse, and broad vs aligned remains tied.

## Files added/modified in this pass
- Modified: `scripts/run_protected_strata_holdout_expansion.py`
- Added: `docs/CANONICAL_PROTECTED_STRATA_ARTIFACT_RECOVERY_EXECUTION_PASS_2026_04_16.md`
- Added: `docs/canonical_protected_strata_artifact_recovery_execution_pass_2026_04_16_summary.json`

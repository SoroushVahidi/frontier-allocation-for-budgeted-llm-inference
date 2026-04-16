# Current branch-learning dataset readiness (2026-04-16)

This note is the canonical processed-dataset readiness report for the branch-allocation learning pipeline.

Project framing preserved:
- canonical objective remains **fixed-budget next-step branch allocation**;
- this data layer is for learning branch-comparison / branch-priority decisions;
- supervision-target quality remains a central bottleneck (not solved by integration alone).

## 1) Code-path audit summary (processing + labels)

Audited code paths feeding branch-allocation learning:

1. Label generation and raw supervision artifacts:
   - `experiments/bruteforce_branch_labels.py`
   - `scripts/run_bruteforce_branch_label_generator.py`

2. Merge/provenance layer:
   - `scripts/merge_bruteforce_branch_label_runs.py`

3. Target-regime construction and ambiguity annotations:
   - `scripts/build_bruteforce_target_regimes.py`
   - `scripts/build_exact_augmented_target_regimes.py`

4. Hard-region mining + exact augmentation:
   - `scripts/mine_bruteforce_hard_regions.py`
   - `scripts/expand_bruteforce_exact_hard_regions.py`

5. Learning consumers:
   - `experiments/bruteforce_branch_allocator.py`
   - `scripts/train_bruteforce_branch_allocator.py`

### Key audit observations (conservative)

- The repository already has strong generation/merge/regime tooling, but the processed-learning layer was spread across multiple artifact styles (`candidate_labels.jsonl`, `pairwise_labels.jsonl`, target-regime folders, exact-expansion folders) without one canonical row-schema contract.
- Pairwise rows contain rich hard-case signals in some regimes (`near_tie_flag`, `pair_type`, `ambiguous_tie_target`, `replaced_approx_label`) but these were not previously standardized in one canonical output package.
- Candidate/outside-option supervision existed implicitly (`branch_vs_outside_gap`) but lacked a canonical dedicated row type for downstream consumers.
- Duplication handling across base pairwise + regime pairwise + exact-promoted pairwise was not previously unified in one deterministic conflict-resolution pass.

## 2) Canonical processed corpus specification

Canonical schema version: `branch_learning_corpus_v1`.

Schema file:
- `configs/branch_learning_corpus_schema_v1.json`

### Row types

1. **candidate rows** (pointwise branch value / branch-vs-outside helper signal)
2. **pairwise rows** (main branch-comparison supervision for next-step allocation)
3. **outside_option rows** (explicit helper rows for stop-vs-act / outside-option calibration)

### Required field families

- Identity/provenance: `row_uid`, `state_id`, branch ids, source run/regime, source paths.
- Slice metadata: `dataset_name`, `remaining_budget`, deterministic `split`.
- Exact-vs-approx lineage: `mode`, `label_source`, `is_exact_label`, `is_approx_label`, `replaced_approx_label` (pairwise).
- Uncertainty/hard-case metadata:
  - candidate/outside: `allocation_value_std`, `branch_vs_outside_gap`
  - pairwise: `margin`, `margin_abs`, `relative_margin`, `pair_uncertainty_std_mean/max`, `near_tie_flag`, `small_margin_flag`, `adjacent_rank_flag`, `ambiguous_tie_target`, `ambiguous_tie_reasons`

## 3) Canonical output layout

Canonical processed corpus root:
- `outputs/branch_learning_corpora/<run_id>/`

Produced structure:
- `manifest.json`
- `rows/candidate_rows.jsonl`
- `rows/pairwise_rows.jsonl`
- `rows/outside_option_rows.jsonl`
- `summaries/corpus_summary.json`
- `summaries/slice_stats.json`
- `meta/schema.json`
- `meta/checksums.json`
- `meta/source_artifacts.json`
- `meta/duplicate_resolution_log.json`
- `report.md`

Interpretation policy:
- `outputs/branch_learning_corpora/*` are canonical processed-learning corpora.
- Existing `outputs/branch_label_bruteforce*` and `outputs/branch_label_bruteforce_targets*` remain source/exploratory/historical artifacts and are not deleted.

## 4) Builder implementation and behavior

New canonical builder script:
- `scripts/build_canonical_branch_learning_corpus.py`

It now provides:
- safe merge from base labels + optional target-regime roots + optional exact-expansion outputs;
- deterministic split assignment by `state_id` hash;
- exact/approx lineage flags preserved and standardized;
- hard-case slice flags made canonical;
- duplicate pairwise conflict resolution with precedence:
  - exact promoted/exact runner > exact > mixed > approx;
- machine-readable summaries and checksums.

## 5) Hardest useful supervision slices (now explicit)

Canonical pairwise rows now standardize direct flags for later upweighting:
- `near_tie_flag`
- `small_margin_flag`
- `adjacent_rank_flag`
- `ambiguous_tie_target`
- `replaced_approx_label` (exact-promoted hard-region pairs)
- `source_regime` (e.g., base vs promoted exact hard region)

This makes near-tie/adjacent/exact-promoted hard slices easier to isolate in one corpus-level query path.

## 6) Current readiness artifact generated in this pass

Builder smoke run (fixture-backed) produced:
- `outputs/branch_learning_corpora/test_fixture_canonical/`

Machine-readable summaries:
- `outputs/branch_learning_corpora/test_fixture_canonical/summaries/corpus_summary.json`
- `outputs/branch_learning_corpora/test_fixture_canonical/summaries/slice_stats.json`

Current fixture smoke confirms:
- canonical row writing works for all three row types;
- pairwise dedupe precedence works (exact-promoted can replace base approx);
- exact/approx and hard-slice counts are exposed in one summary JSON.

## 7) Remaining bottlenecks before next learning pass

Still unresolved (conservative):
1. supervision-target fidelity remains a core bottleneck (this pass improves data organization, not target truth);
2. real corpus quality depends on source run quality and exact-coverage breadth;
3. dataset/budget imbalance still needs active weighting/sampling policy at training time;
4. near-tie handling remains difficult and should be explicitly stress-tested in each learning run.

## 8) Recommended next learning pass

Use one canonical processed corpus run as training input and run matched learners with explicit hard-case reporting:
1. materialize corpus with `build_canonical_branch_learning_corpus.py` from latest merged + promoted regimes;
2. train pairwise + pointwise + outside-option helpers using canonical rows;
3. report metrics with explicit slices for near-tie, adjacent-rank, exact-promoted, dataset, and budget;
4. keep claims conservative: better readiness and auditability, not bottleneck closure.

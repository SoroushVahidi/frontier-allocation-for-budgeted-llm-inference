# Mistral Algorithm Improvement Diagnostic (2026-05-23)

**Scope:** offline diagnostic only; no policy promotion.

- **Provider/model:** Mistral / `mistral-small-latest`
- **Source run:** `outputs/mistral_frozen_agreement_only_2of3_validation_20260523T145416Z`
- **Processed result:** `outputs/mistral_frozen_agreement_only_2of3_live_result_20260523/`
- **Diagnostic bundle:** `outputs/mistral_algorithm_improvement_diagnostic_20260523/`
- **Active Cohere/Cerebras jobs:** left untouched.

## Main finding

Agreement-only loses to S1 mostly because it keeps frontier on no-majority cases and because it obeys wrong external majorities when L1/TALE line up against S1. The row-level audit finds **19** S1-correct / agreement-wrong cases on this fixed pool.

## Loss decomposition

- no external majority: 6
- external majority equals frontier: 2
- external majority excludes S1: 11
- S1 agreed with one source while agreement still lost: 0
- pooled-4 frontier/tie behavior blocked S1: 6

These counts overlap; they are diagnostic buckets, not a disjoint partition.

## S1 dominance is genuine

- S1 correct & frontier wrong: 42
- S1 correct & L1+TALE wrong: 30
- only S1 correct: 9
- S1 wrong while all others correct: 3
- parse failures: frontier=0, l1=0, s1=0, tale=0

The advantage is not parser-driven: all four methods have zero parse failures.

## Runtime-legal signals that help trust S1

Top signals by S1 lift are recorded in `outputs/mistral_algorithm_improvement_diagnostic_20260523/s1_runtime_feature_lift.csv`. The strongest recurring patterns are:

- S1 agrees with at least one external source.
- External majority is absent.
- S1 answer is short and cleanly numeric.
- External majority excludes S1 while the S1 answer remains short/clean.

## Best diagnostic policy variant

Best S1-aware diagnostic policy in this bundle: **provider_prior_weighted_selector_mistral_s1_prior** at **89.33%**.

Oracle over four sources is an upper bound at **93.33%**.

- Frontier baseline: 78.33%
- Agreement-only baseline: 85.33%
- S1 baseline: 89.67%
- Pooled-4 baseline: 83.67%

This best diagnostic variant improves over agreement-only, but it does **not** beat S1 on the fixed pool.

## Overfitting check

Best shallow model signal in the rule-search table: **external_majority_excludes_s1** (test accuracy 0.957). The split log is in `mistral_split_policy_selection_log.csv` and the summary is in `mistral_split_diagnostic_summary.csv`.

## Cohere comparison

Completed nonmatched Cohere shows a different ranking: frontier/S1 are closer, and S1 is not the dominant source there. On Mistral, S1 is clearly the best single source; on nonmatched Cohere it is not.

Comparison file: `outputs/mistral_algorithm_improvement_diagnostic_20260523/mistral_vs_cohere_nonmatched_source_ranking_comparison.csv`

## Safest algorithmic takeaway

The safest direction is a **provider-specific offline calibration study** that learns when to trust S1 on Mistral-like runs, but this should stay diagnostic/offline until validated on additional matched pools. Do not promote a new runtime rule from this single run.

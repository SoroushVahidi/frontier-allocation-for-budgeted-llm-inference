# Merged Repaired Cohere/Mistral Selector Replay (2026-05-24)

## Why merge was needed
Both reruns were originally frontier-only because missing-method rows were skipped during allowlist handling. To interpret selector behavior, we must merge original frontier rows with missing-method repair rows and verify complete 4-method coverage per example.

## Source files used
- Cohere original: `outputs/cohere_targeted_no_majority_fallback_rerun_20260523/cohere_real_model_cost_normalized_validation_20260523T235741Z/per_example_records.jsonl`
- Cohere repair: `outputs/repair_incomplete_cohere_mistral_runs_20260524/cohere_missing_methods_repair_20260524T003751Z/cohere_real_model_cost_normalized_validation_20260524T003905Z/per_example_records.jsonl`
- Mistral original: `outputs/mistral_full300_regime_selector_validation_20260523/cohere_real_model_cost_normalized_validation_20260523T233843Z/per_example_records.jsonl`
- Mistral repair: `outputs/repair_incomplete_cohere_mistral_runs_20260524/mistral_missing_methods_repair_20260524T003751Z/cohere_real_model_cost_normalized_validation_20260524T003905Z/per_example_records.jsonl`

## Merge integrity results
### Cohere targeted merge
- PASS
- Unique examples: 47
- Rows: 188/188
- Method counts:
  - frontier: 47
  - L1: 47
  - S1: 47
  - TALE: 47
- Duplicates: 0
- Missing rows: 0

### Mistral full300 merge
- PASS
- Unique examples: 300
- Rows: 1200/1200
- Method counts:
  - frontier: 300
  - L1: 300
  - S1: 300
  - TALE: 300
- Duplicate key groups: 1
- Missing rows after resolution: 0

## Mistral duplicate handling
One duplicate key existed: `(provider=mistral, dataset=openai/gsm8k, seed=71, budget=6, example_id=openai_gsm8k_32, method=external_l1_max)`.

Rows differed:
- one failed 429 row (`status=failed`, `scored=0`, empty answer),
- one later scored row (`status=scored`, `scored=1`, answer `16`, exact_match=1).

Applied documented deterministic rule: `prefer_scored_over_failed`.
- Kept the scored row.
- Dropped the failed/unscored duplicate row.
- Resolution recorded in `mistral_merge_duplicate_resolution.md`.

## Cohere targeted replay results (biased diagnostic set)
### Method accuracies (47 targeted examples)
- frontier: 19/47 = 40.43%
- L1: 18/47 = 38.30%
- S1: 19/47 = 40.43%
- TALE: 16/47 = 34.04%

### Selector results
- Best non-oracle cluster (tie): 21/47 = 44.68%
  - `pooled4_with_fallback`
  - `cv5_raw_spread_regime_selector`
  - `beta_shrinkage_regime_selector`
  - `dominant_source_veto`
  - `majority_requires_dominant_source_when_dominant`
- `agreement_only_2of3_against_frontier`: 20/47 = 42.55%
- `frontier_fallback_calibrated`: 18/47 = 38.30%
- `pooled4_with_calibrated_no_majority_fallback`: 20/47 = 42.55%

### No-majority fallback diagnostic (17 cases)
- frontier: 6/17 (35.29%)
- pooled4 fallback baseline: 6/17 (35.29%)
- agreement-only: 5/17 (29.41%)
- frontier_fallback_calibrated: 3/17 (17.65%)
- pooled4_with_calibrated_no_majority_fallback: 5/17 (29.41%)

Interpretation:
- On this targeted slice, calibrated fallback did **not** recover the primary no-majority failures and introduced net regressions vs frontier baseline behavior.
- Because this set is failure-targeted, all Cohere conclusions remain diagnostic only.

## Mistral full300 replay results (key validation)
### Method accuracies (300 examples)
- frontier: 236/300 = 78.67%
- L1: 218/300 = 72.67%
- S1: 274/300 = 91.33%
- TALE: 201/300 = 67.00%

### Selector accuracies
- `always_s1`: 274/300 = 91.33%
- `cv5_raw_spread_regime_selector`: 274/300 = 91.33%
- `beta_shrinkage_regime_selector`: 274/300 = 91.33%
- `dominant_source_veto`: 274/300 = 91.33%
- `pooled4_with_fallback`: 257/300 = 85.67%
- `agreement_only_2of3_against_frontier`: 254/300 = 84.67%
- `majority_requires_dominant_source_when_dominant`: 264/300 = 88.00%
- `pooled4_with_calibrated_no_majority_fallback`: 267/300 = 89.00%
- `frontier_fallback_calibrated`: 257/300 = 85.67%

### Regime-selector outcome
Across all CV folds, Mistral remained dominant-source regime:
- best train source each fold: S1
- spread each fold: ~0.114 to ~0.133 (>0.05)
- beta conservative dominance criterion true in each fold

Result:
- Regime selectors selected S1 behavior and clearly beat pooled-4/agreement-only.

### Statistical/paired diagnostics
- `cv5_raw_spread_regime_selector` vs pooled-4: +0.0567 accuracy; bootstrap CI [0.0300, 0.0867]
- `cv5_raw_spread_regime_selector` vs agreement-only: +0.0667 accuracy; bootstrap CI [0.0367, 0.1000]
- McNemar (cv5 spread vs pooled-4): b=19, c=2, chi2_cc=12.19

### Retry/rate-limit context
- Original Mistral run log mentions: 224 retries/429 mentions.
- Mistral repair log mentions: 382 retries/429 mentions.

## Original vs rerun consistency (Mistral)
Rerun preserves source ranking and dominant-source conclusion:
- Original ranking: S1 > frontier > L1 > TALE
- Rerun ranking: S1 > frontier > L1 > TALE

Compared with original headline values:
- frontier: +0.33pp
- L1: +0.33pp
- S1: +1.67pp
- TALE: +4.00pp
- agreement-only: -0.67pp
- pooled-4: +2.00pp
- always-S1: +1.67pp

Interpretation: quantitative shifts occurred, but qualitative ranking and dominant-source regime signal are stable.

## Calibrated fallback outcome
- Cohere targeted: calibrated fallback variants underperformed baseline fallback behavior.
- Mistral full300: pooled4+calibrated-no-majority improved over pooled-4/agreement-only, but still below S1/regime-S1 selectors.

## Does this support full Cohere validation?
- Yes, only as a **separate unbiased validation question** if testing a new fallback candidate is still desired.
- No evidence here supports promoting calibrated no-majority fallback as-is.

## Does this support learned/reliability-router direction?
Yes. Full Mistral replay strongly supports regime-dependent routing and dominant-source detection; this is aligned with moving toward reliability-aware routing with proper train/test separation.

## Active Cerebras job safety confirmation
A non-invasive process check was performed before and after this task. Active Cerebras process remained running and untouched. No attach/kill/restart/interrupt actions were performed.

## Recommended next step
1. Keep Mistral as dominant-source regime in current diagnostic narrative.
2. Use merged Mistral full300 outputs as the primary regime-selector evidence update.
3. Treat Cohere targeted replay as biased diagnostic only.
4. If needed, schedule a full unbiased Cohere validation for any revised no-majority fallback idea.

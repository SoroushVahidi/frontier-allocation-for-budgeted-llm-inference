# Direct-reserve learned scorer fresh GSM8K validation

Timestamp: `20260426T_FRESH_GSM8K_SCORER_VALIDATION`

## Outcome

A fresh GSM8K planned-case source was created and evaluated with one bounded Cohere run. The plan loaded `openai/gsm8k` test via Hugging Face `datasets`, excluded 20 prior scorer-validation problem IDs, sampled 20 fresh IDs, and verified zero overlap with the prior scorer slices and replay package.

## Plan and validation

- Fresh plan: `outputs/fresh_gsm8k_direct_reserve_scorer_plan_20260426T_FRESH_GSM8K_SCORER_VALIDATION/`
- Loader: Hugging Face `datasets`, repo `openai/gsm8k`, config `main`, split `test`
- Loaded GSM8K problem IDs: 1,319
- Excluded prior IDs: 20
- Fresh candidates after exclusion: 1,299
- Fresh planned IDs: 20
- Overlap with scorer slice 1: 0
- Overlap with scorer slice 2: 0
- Overlap with replay seed package: 0
- Cohere API used: yes, one 20-case budget-4 run with `command-r-plus-08-2024`
- Real validation output: `outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T_FRESH_GSM8K_SCORER_VALIDATION/`

## Fresh-slice selected-gold rates

| Selector | Selected-gold rate | Improvements vs base | Degradations vs base |
|---|---:|---:|---:|
| base plus-diverse | 0.60 | 0 | 0 |
| support count | 0.55 | 2 | 3 |
| max-gap rule | 0.40 | 0 | 4 |
| margin-gated per-case | 0.75 | 3 | 0 |
| learned logistic | 0.65 | 1 | 0 |
| learned random forest | 0.70 | 2 | 0 |
| learned pairwise logistic | 0.70 | 2 | 0 |
| learned HGB | 0.40 | 0 | 4 |

Learned RF and pairwise beat base plus-diverse by 10 percentage points on genuinely unseen GSM8K problems, with zero degradation versus base in this 20-case slice. Support-count did not remain competitive with learned RF/pairwise here. HGB degraded and should remain excluded from positive recommendations.

## Cross-slice generalization

- First-slice model on fresh GSM8K: base 0.60, learned logit 0.65, learned RF 0.70, pairwise 0.70.
- Fresh model on first slice: base 0.60, learned logit 0.85, learned RF 0.85, pairwise 0.85.
- Combined old+fresh grouped holdout: base 0.667, learned logit 0.778, learned RF 0.833, pairwise 0.833.

Cross-slice train/test supports generalization for RF and pairwise under this diagnostic setup.

## Failure analysis

- Fresh degradation package: `outputs/direct_reserve_candidate_scorer_fresh_gsm8k_degradation_analysis_20260426T_FRESH_GSM8K_SCORER_VALIDATION/`
- Important improvement rows: 5 selector-case rows, covering 2 RF/pairwise improvements plus logistic overlap.
- Degradation rows: 4, all from HGB.
- RF/pairwise/logistic control/easy degradation: 0.
- Gold-present missed rows: 19 selector-case rows.
- Gold-absent rows: 9 selector-case rows.
- Learned model disagreement rows: 3.

Main remaining failure modes are gold absent from the plus-diverse candidate pool, support-count/max-gap picking high-support wrong answers, and HGB overselecting wrong alternatives. Margin-gated remains a strong comparison method but is still diagnostic-only.

## Recommendation

Implement a diagnostic learned-override runtime method next, guarded as diagnostic-only. The conservative rule is met: learned RF and pairwise beat base plus-diverse by at least 5 percentage points on a fresh disjoint slice and have zero degradation versus base. Do not wire it as a production/default runtime method yet; keep collecting fresh slices and exclude HGB from recommendations.

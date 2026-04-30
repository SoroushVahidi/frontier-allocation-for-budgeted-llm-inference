# Selector Comparison 30-case Cohere (20260429T_SELECTOR_COMPARISON_30CASE_COHERE_RERUN)

Artifact: `outputs/cohere_real_model_cost_normalized_validation_20260429T_SELECTOR_COMPARISON_30CASE_COHERE_RERUN`

## Accuracy table

|method|scored|correct|accuracy|mean_tokens|mean_cost_usd|mean_latency_s|
|---|---:|---:|---:|---:|---:|---:|
|external_l1_max|30|24|0.800|480.2|0.002587|2.551|
|direct_reserve_semantic_frontier_v2|30|16|0.533|1029.9|0.005258|7.132|
|direct_reserve_semantic_frontier_v2_selection_fix_v1|30|20|0.667|1061.8|0.005547|7.741|
|direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1|30|16|0.533|1048.2|0.005505|13.723|
|direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1|30|20|0.667|1044.1|0.005434|19.193|

## Paired comparisons

|pair|N|W|T|L|delta_acc|
|---|---:|---:|---:|---:|---:|
|OV vs DRv2|30|5|20|5|0.000|
|PRM vs DRv2|30|8|18|4|0.133|
|OV vs selection_fix|30|2|22|6|-0.133|
|PRM vs selection_fix|30|5|20|5|0.000|
|OV vs L1|30|2|18|10|-0.267|
|PRM vs L1|30|4|18|8|-0.133|
|DRv2 vs L1|30|1|20|9|-0.267|

## Present-but-not-selected analysis
- DR-v2 wrong cases (paired with OV+PRM): 14
- Gold present in OV selector candidates: 11
- Recovered by OV: 2
- Recovered by PRM: 2
- Remaining missed among gold-present: 7
- Regressions when DR-v2 originally correct: OV=5, PRM=4

## Selector surface (OV+PRM rows)
- selector rows analyzed: 60
- candidate_count distribution: {2: 60}
- answer_group_count distribution: {1: 34, 2: 26}
- extraction-source distribution: {'selector_candidate_pool': 60}
- fallback-reason distribution: {'': 60}
- ov_rerank_applied counts: {True: 30, False: 30}
- prm_rerank_applied counts: {False: 30, True: 30}
- verifier-call distribution: {2: 38, 6: 7, 4: 7, 3: 3, 5: 3, 7: 2}
- backend values: {'cohere': 60}
- parse-fallback/error counts: {}

## Claim safety
- classification: **diagnostic_positive**
- This is a 30-case diagnostic only; not final paper evidence.

## Rerun artifact note
- Original timestamp `20260429T_SELECTOR_COMPARISON_30CASE_COHERE` had summary docs but missing `per_example_records.jsonl` in this environment.
- Real offline threshold/loss-case analyses were executed using artifact-complete rerun: `outputs/cohere_real_model_cost_normalized_validation_20260429T_SELECTOR_COMPARISON_30CASE_COHERE_RERUN`.
- See `docs/SELECTOR_COMPARISON_30CASE_COHERE_RERUN_20260429.md`, `docs/SELECTOR_OVERRIDE_THRESHOLD_ANALYSIS_20260429.md`, and `docs/EXTERNAL_L1_LOSS_CASEBOOK_20260429T_SELECTOR_COMPARISON_30CASE_COHERE_RERUN.md`.

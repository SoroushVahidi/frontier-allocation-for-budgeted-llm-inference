# Stage-3 Live Result Schema

## stage3_live_results.csv columns
- case_id
- integrated_prediction
- integrated_correct
- external_l1_prediction
- external_l1_correct
- tale_prediction
- tale_correct
- s1_prediction
- s1_correct
- best_external_prediction
- best_external_correct
- cohere_call_made
- response_text_path
- parse_status
- no_gold_leakage
- no_external_prediction_leakage
- notes

## stage3_live_summary.json keys
- integrated_correct_count
- external_l1_correct_count
- tale_correct_count
- s1_correct_count
- best_external_correct_count
- integrated_minus_external_l1
- integrated_minus_tale
- integrated_minus_s1
- integrated_minus_best_external
- paired_external_l1_only
- paired_tale_only
- paired_s1_only
- paired_best_external_only
- paired_integrated_only_vs_external_l1
- api_errors
- parsing_ambiguities
- no_gold_leakage
- no_external_prediction_leakage

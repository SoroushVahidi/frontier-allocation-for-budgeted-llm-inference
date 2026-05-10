# Hard-continue targeted Cohere validation

- Method: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`
- Model: `command-r-plus-08-2024`
- Cases: 12 (9 primary, 3 secondary)
- Logical calls: 52 / 120
- Exact: 9/12 = 0.750
- Continue responses observed: 13
- Continue leakage cases: 0
- Success criterion met: True

## Failure families
- `correct`: 9
- `final_target_mismatch_or_selection_error`: 1
- `gold_absent_or_not_in_answer_groups`: 2

## Per-case table

| case_id | exact | selected | gold | source | continue_leak | failure_family |
|---|---:|---:|---:|---|---:|---|
| openai_gsm8k_1177 | 1 | 17 | 17 | pal_overlay | 0 | correct |
| openai_gsm8k_1180 | 1 | 5600 | 5600 | pal_overlay | 0 | correct |
| openai_gsm8k_1218 | 0 | 1800 | 225 | pal_overlay | 0 | gold_absent_or_not_in_answer_groups |
| openai_gsm8k_30 | 1 | 109 | 109 | direct_reserve | 0 | correct |
| openai_gsm8k_59 | 1 | 187 | 187 | pal_overlay | 0 | correct |
| openai_gsm8k_62 | 1 | 25000 | 25000 | pal_overlay | 0 | correct |
| openai_gsm8k_217 | 1 | 15 | 15 | pal_overlay | 0 | correct |
| openai_gsm8k_245 | 0 | 14 | 7 | pal_overlay | 0 | final_target_mismatch_or_selection_error |
| openai_gsm8k_358 | 0 | 1.5 | 20 | pal_overlay | 0 | gold_absent_or_not_in_answer_groups |
| openai_gsm8k_1285 | 1 | 1218 | 1218 | pal_overlay | 0 | correct |
| openai_gsm8k_228 | 1 | 1 | 1 | frontier_tiebreak | 0 | correct |
| openai_gsm8k_337 | 1 | 1 | 1 | direct_reserve | 0 | correct |

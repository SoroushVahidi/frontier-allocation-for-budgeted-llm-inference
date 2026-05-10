# 10-case SC6/PAL calibration vs production_equiv + core4 paired rows
- cases: openai_gsm8k_1082, openai_gsm8k_1083, openai_gsm8k_1085, openai_gsm8k_1087, openai_gsm8k_1095, openai_gsm8k_1097, openai_gsm8k_1099, openai_gsm8k_1116, openai_gsm8k_1120, openai_gsm8k_1121

| Comparator | prod_eq correct /10 | comp correct /10 | delta | McNemar b/c |
|---|---:|---:|---:|---|
| external_l1_max_fair_v1 | 9 | 8 | 1 | 1/2 |
| external_self_consistency_4_fair_v1 | 9 | 9 | 0 | 0/0 |
| external_self_consistency_6_fair_v1 | 9 | 0 | 9 | 0/9 |
| external_pal_pot_fair_v1 | 9 | 0 | 9 | 0/9 |
| external_s1_budget_forcing_faithful_v1 | 9 | 9 | 0 | 1/1 |
| external_tale_ep_prompt_budgeting_faithful_v1 | 9 | 10 | -1 | 1/0 |
| best_core4_oracle | 9 | 10 | -1 | 1/0 |

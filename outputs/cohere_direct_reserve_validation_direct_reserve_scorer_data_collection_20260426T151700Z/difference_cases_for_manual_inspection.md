# Difference cases for manual inspection

count=6

| example_id | failure_type | method | external | strict_f3 | stratum |
|---|---|---|---|---|---|
| openai_gsm8k_18 | other | 16 | 14 | 14 | absent_from_tree |
| openai_gsm8k_12 | present_not_selected | 100 | 4(12) + 22 = 48 + 22 = 70 | 58 | absent_from_tree |
| openai_gsm8k_6 | gold_absent | 33.5 | 21.5 | 34.5 | absent_from_tree |
| openai_gsm8k_3 | other | 10 | x = 20 miles per hour | 10 miles per hour | absent_from_tree |
| openai_gsm8k_5 | other | 280 | 100 | 210 | present_not_selected |
| openai_gsm8k_14 | other | 38 | x = 40 - 4 = oxed{36} | 38 | control_correct |

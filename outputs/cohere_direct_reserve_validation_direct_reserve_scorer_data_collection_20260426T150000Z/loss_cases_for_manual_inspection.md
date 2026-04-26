# Loss cases for manual inspection

count=8

| example_id | failure_type | method | external | strict_f3 | stratum |
|---|---|---|---|---|---|
| openai_gsm8k_12 | present_not_selected | 90 | 70 | 62 | absent_from_tree |
| openai_gsm8k_6 | gold_absent | 42.5 | 32 | 33.5 | absent_from_tree |
| openai_gsm8k_18 | present_not_selected | 14 | 16 | 16 | absent_from_tree |
| openai_gsm8k_2 | gold_absent | 1000 | 350 | 500 | absent_from_tree |
| openai_gsm8k_7 | present_not_selected | 100 - 30 * 2 - 20 = oxed{20} | 140 - 80 = oxed{60} | 140 - 80 = 60 | absent_from_tree |
| openai_gsm8k_5 | present_not_selected | 120 | 280 | 260 | present_not_selected |
| openai_gsm8k_13 | gold_absent | 10 | 28 | 10 | control_correct |
| openai_gsm8k_9 | present_not_selected | 4 | 12% | 12% | control_correct |

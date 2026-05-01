# Difference cases for manual inspection

count=9

| example_id | failure_type | method | external | strict_f3 | stratum |
|---|---|---|---|---|---|
| openai_gsm8k_5 | present_not_selected | 120 | 100 | 210 | immediate_miss |
| openai_gsm8k_5 | gold_absent | 120 | 100 | 260 | immediate_miss |
| openai_gsm8k_5 | other | 280 | 100 | 280 | immediate_miss |
| openai_gsm8k_6 | gold_absent | 33.5 | 33 | 28 | immediate_miss |
| openai_gsm8k_6 | gold_absent | 34.5 | 33.5 | 26.5 | immediate_miss |
| openai_gsm8k_6 | gold_absent | 127 | 32 | 25.00 | immediate_miss |
| openai_gsm8k_576 | present_not_selected | 13104 | 11232 | 11232 | immediate_miss |
| openai_gsm8k_576 | other | 11232 | 216 * (4 + 12 + 2 + 34) = oxed{10368} | 16560 | immediate_miss |
| openai_gsm8k_576 | present_not_selected | 17,280 | 11232 | 18144 | immediate_miss |

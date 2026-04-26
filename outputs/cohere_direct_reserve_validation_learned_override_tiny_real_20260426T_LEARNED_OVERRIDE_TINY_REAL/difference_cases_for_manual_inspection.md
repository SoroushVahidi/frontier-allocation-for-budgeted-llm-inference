# Difference cases for manual inspection

count=6

| example_id | failure_type | method | external | strict_f3 | stratum |
|---|---|---|---|---|---|
| openai_gsm8k_926 | other | 1 | 2 | 1 | fresh_gsm8k_unseen |
| openai_gsm8k_316 | gold_absent | 78 marbles | 156 | 156 | fresh_gsm8k_unseen |
| openai_gsm8k_313 | other | 120000 | 63,000 * 2 = 126,000 | 11718000 | fresh_gsm8k_unseen |
| openai_gsm8k_1163 | other | 12 | 18 | 12 | fresh_gsm8k_unseen |
| openai_gsm8k_576 | gold_absent | 13824 | 11232 | 10368 | fresh_gsm8k_unseen |
| openai_gsm8k_1082 | other | 2 | 1.5 | 1.5 | fresh_gsm8k_unseen |

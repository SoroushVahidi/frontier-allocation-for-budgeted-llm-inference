# Cross-provider real-model main-run audit (20260424T163701Z)

## Contract checked
- Providers/models: `openai/gpt-4.1-mini`, `cohere/command-r-plus-08-2024`
- Datasets: `['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024']`
- Budgets: `[4, 6, 8]`
- Seeds: `[11, 23]`
- Subset size: `20`
- Methods: `['strict_f3', 'strict_gate1_cap_k6', 'strict_f2', 'external_l1_max', 'self_consistency_3']`

## Claim-safety answers
- A: OpenAI=yes, Cohere=yes
- B: OpenAI=no, Cohere=no
- C: OpenAI=yes, Cohere=yes
- D: OpenAI=appendix-only, Cohere=appendix-only
- E: **agree**

## Missing or incomplete slices
- `openai` `openai/gsm8k` seed `23` budget `8`: insufficient_scored_examples:99<100
- `cohere` `openai/gsm8k` seed `11` budget `4`: insufficient_scored_examples:93<100
- `cohere` `openai/gsm8k` seed `11` budget `6`: insufficient_scored_examples:90<100
- `cohere` `openai/gsm8k` seed `11` budget `8`: insufficient_scored_examples:97<100
- `cohere` `openai/gsm8k` seed `23` budget `4`: insufficient_scored_examples:79<100
- `cohere` `openai/gsm8k` seed `23` budget `6`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3
- `cohere` `openai/gsm8k` seed `23` budget `8`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3
- `cohere` `HuggingFaceH4/MATH-500` seed `11` budget `4`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3
- `cohere` `HuggingFaceH4/MATH-500` seed `11` budget `6`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3
- `cohere` `HuggingFaceH4/MATH-500` seed `11` budget `8`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3
- `cohere` `HuggingFaceH4/MATH-500` seed `23` budget `4`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3
- `cohere` `HuggingFaceH4/MATH-500` seed `23` budget `6`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3
- `cohere` `HuggingFaceH4/MATH-500` seed `23` budget `8`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3
- `cohere` `HuggingFaceH4/aime_2024` seed `11` budget `4`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3
- `cohere` `HuggingFaceH4/aime_2024` seed `11` budget `6`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3
- `cohere` `HuggingFaceH4/aime_2024` seed `11` budget `8`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3
- `cohere` `HuggingFaceH4/aime_2024` seed `23` budget `4`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3
- `cohere` `HuggingFaceH4/aime_2024` seed `23` budget `6`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3
- `cohere` `HuggingFaceH4/aime_2024` seed `23` budget `8`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3

## Safe interpretation
Real-model evidence is appendix-only unless both providers consistently establish frontier-allocation dominance over `external_l1_max`. Current safe framing is competitive and diagnostically informative, not universally dominant.

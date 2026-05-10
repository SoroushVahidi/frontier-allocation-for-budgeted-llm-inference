# PAL empty-code retry follow-up live batch

- Selected cases (11): ['openai_gsm8k_36', 'openai_gsm8k_61', 'openai_gsm8k_95', 'openai_gsm8k_127', 'openai_gsm8k_347', 'openai_gsm8k_354', 'openai_gsm8k_362', 'openai_gsm8k_374', 'openai_gsm8k_391', 'openai_gsm8k_411', 'openai_gsm8k_433']
- Cases scored/failed: **11/0**
- Cohere logical calls used/cap: **37/240**
- Retry ran count/rate: **4/0.364**
- Retry skipped count/reasons: **7**, {'seed_code_present_and_executable': 7}
- First-attempt code present rate: **0.000**
- Retry code present rate: **1.000**
- Retry parse/safety/exec OK rates: **1.000/0.500/0.250**
- Retry candidate strong count/rate: **1/0.250**
- Exact accuracy: **0.273**
- Fixes vs prior PAL: **3**
- Breaks vs prior PAL: **0**
- Budget correctness (retry-observed/decrement/cap): **True/True/True**

## Aggregate with previous 5-case smoke
- Total retry-evaluated cases: **16**
- Total fixes/breaks/net: **6/0/6**
- Total retry exec OK rate: **0.375**

- Keep retry-on-empty-code: **yes**
- Recommended next step: **E. stop and write up**

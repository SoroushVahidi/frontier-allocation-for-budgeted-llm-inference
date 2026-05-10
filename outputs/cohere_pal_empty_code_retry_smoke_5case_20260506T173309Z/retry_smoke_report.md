# PAL empty-code retry tiny live smoke (5 cases)

- Cases scored/failed: **5/0**
- Logical calls used/cap: **19/120**
- Retry ran count/rate: **4/0.800**
- Retry skipped count: **1**
- Retry skipped reasons: {'seed_code_present_and_executable': 1}
- First-attempt code present rate: **0.000**
- Retry code present rate: **0.500**
- Retry parse/safety/exec OK rates: **0.500/0.500/0.500**
- Retry candidate strong count: **2**
- Exact accuracy on 5 cases: **0.600**
- Fixes vs prior PAL: **3**
- Breaks vs prior PAL: **0**
- Budget correctness (retry observed / decrement / cap respected): **True / True / True**
- Retry-on-empty-code working live: **True**
- 15-case follow-up justified: **True**
- Proposed cap if justified: **360**

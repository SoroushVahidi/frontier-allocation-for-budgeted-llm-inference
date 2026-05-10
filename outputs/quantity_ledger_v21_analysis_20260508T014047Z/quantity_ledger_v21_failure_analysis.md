# quantity_ledger v2.1 failure analysis

## quantity_ledger v2 (Cohere pilot 15 cases, scaffold-only summary)
The v2 runner selected 6 `quantity_ledger` cases:

1. `openai_gsm8k_750` — **exact (fixed)**  
   - V1 status: `failed`  
   - V2 answer: `92`  
   - Gold: `92`  
   - Failure mode: `none`

2. `openai_gsm8k_841` — **failed (recurrence bug)**  
   - V1 status: `failed`  
   - V2 predicted: `378000`  
   - Gold: `262500`  
   - Failure mode: **treated one-time bonus as recurring monthly**, then annualized incorrectly.
   - One-time vs recurring: **bonus “worth half a month’s salary” should be one-time** (add once), but model effectively added it every month.
   - Percent/fraction/base: percent raise on monthly salary is correct, but the bonus fraction should be applied to the (raised) monthly salary **once**, not multiplied by 12.
   - Final target ambiguity: not ambiguous; the question asks for annual total.

3. `openai_gsm8k_1006` — **failed**  
   - V1 status: `not_piloted`  
   - V2 predicted: `61`  
   - Gold: `25`  
   - Failure mode: likely **percent-of-total-vs-percent-of-subtotal** interpretation error for “heartworm check is 60% of total bill”.
   - One-time vs recurring: n/a (not a recurrence issue).
   - Percent/fraction/base: “60% of total bill” implies check amount is 60% of the *final* bill; some solvers compute 60% of the pre-check subtotal instead.
   - Final target ambiguity: low.
   - Proposed v2.1 prompt change: keep percent base semantics explicit in addition to recurrence classification.

4. `openai_gsm8k_1027` — **failed**  
   - V1 status: `not_piloted`  
   - V2 predicted: `1`  
   - Gold: `2`  
   - Failure mode: division by the wrong denominator (pairs vs contacts); not recurrence.
   - One-time vs recurring: n/a
   - Percent/fraction/base: n/a (discount semantics are present but the key error is counting denominator).
   - Proposed v2.1 prompt change: include a “denominator check” in the money ledger (e.g., pair-count vs contact-count).

5. `openai_gsm8k_1029` — **exact**  
   - V1 status: `not_piloted`  
   - V2 answer: `70000`

6. `openai_gsm8k_1045` — **exact**  
   - V1 status: `not_piloted`  
   - V2 answer: `4`

## Key takeaway for v2.1
Only `openai_gsm8k_841` contains the clear, recurrence-style failure described in the pilot goal:
- “bonus worth half a month’s salary” must be **one-time** and should **not** be multiplied by 12 unless the story explicitly says it repeats.

The v2.1 template should harden this with a recurrence classification + an explicit “do not multiply one-time bonus by number of periods” rule.


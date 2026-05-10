# quantity_ledger failures (targeted discovery retry v1 → v2)

## quantity_ledger pilot cases (v1)
There were **3** `quantity_ledger` cases in the v1 Cohere pilot.

- **Succeeded:** `openai_gsm8k_720` (gold **106**, model **106** exact match)
- **Failed (2):**
  1. `openai_gsm8k_750`
     - Problem (summary): bag of marbles costs a base price, then the price “increases by a fixed percentage of the *original* price every two months” over multiple steps
     - Model answer: **772.6**
     - Gold answer: **92**
     - Current PAL answer: **532.466...**
     - Hypothesized failure mode: **interpreted percentage as compounding** on the running price instead of using a **fixed increment** computed from the original price each interval.
     - Evidence from response: plan used a multiplicative factor over periods (compounding), producing a much larger number.
     - Recommended prompt change: explicitly distinguish “percent of the original/base amount each step” (fixed increment) vs “percent increase applied repeatedly to the updated amount” (compounding).

  2. `openai_gsm8k_841`
     - Problem (summary): monthly salary gets a percent raise; a bonus is “worth half a month’s salary”; ask for annual total.
     - Model answer: **262000**
     - Gold answer: **262500**
     - Current PAL answer: **262000** (Cohere did not improve)
     - Hypothesized failure mode: **applied the bonus fraction to the original pre-raise salary** rather than the **raised salary**.
     - Evidence from response: computed bonus using the pre-raise monthly salary, causing the result to be low by exactly the difference between half of the original vs half of the raised salary.
     - Recommended prompt change: compute the **raised monthly salary first**, then apply any “fraction of a month’s salary” bonus to the **raised** salary.

## v2 focus (what to change)
Refine only the `quantity_ledger` scaffold so that:
- the model restates the final money target before solving,
- percentages are applied with correct “base vs repeated” semantics,
- money ledgers track which base amount each percentage/fraction uses,
- the final numeric answer is output exactly once at the end (parseable `\\boxed{}`).


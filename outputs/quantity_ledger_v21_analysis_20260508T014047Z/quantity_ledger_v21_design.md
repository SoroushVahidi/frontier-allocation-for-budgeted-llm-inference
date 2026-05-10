# quantity_ledger v2.1 design (gold-free, recurrence-aware)

## What v2.1 changes
The v2 `quantity_ledger` prompt improved fixed-increment vs compounding (e.g., `openai_gsm8k_750`), but `openai_gsm8k_841` still failed.

The remaining failure pattern is: **one-time bonus/income** described as “worth X months of salary” was incorrectly treated as **recurring monthly** and multiplied by the number of months (annualized by multiplying the bonus into the monthly total).

## Recurrence classification rules (must be applied)
For every money/income/bonus/payment quantity `Q` in the story, classify it as one of:
1. **one-time**: occurs once (or explicitly occurs at the end once).
2. **per-period recurring**: occurs every base period (e.g., every month in a “monthly salary” story).
3. **total across periods**: the story already gives the total across the whole horizon (do not multiply).
4. **unknown**: ambiguous; prefer abstain-like behavior (compute only what is unambiguous).

Critical rule:
- **Never multiply a one-time bonus/payment by the number of periods** (months/weeks/years) unless the problem explicitly says it repeats.

Specific guidance:
- “A bonus worth half a month’s salary” is usually **one-time**:
  - Compute the base (the referenced month’s/raised salary amount),
  - take the fraction (e.g., half),
  - **add it once** to the yearly total.
- If the question asks for an annualized total:
  - Multiply only the **recurring monthly** component by 12,
  - add **one-time** bonuses once.

## Final target restatement
Before arithmetic, restate the final target once:
- amount / total paid / total earned / change / remaining / profit / annualized total, etc.

## Money ledger and compute exactly once
The prompt should:
1. Identify the base salary/monthly salary if present.
2. Apply “percent raise” to get the **raised** recurring monthly salary.
3. Compute any “fraction of a month’s salary” bonus as a **one-time addition**.
4. Compute annual total:
   - annual_total = 12 × (raised monthly salary) + (one-time bonus once)
5. Output only the final numeric answer once:
   - last line `\\boxed{<number>}`

## Output contract
- Gold-free and runtime-legal (no gold answers or external predictions in prompt).
- No intermediate numeric value may be presented as the final answer.
- Final answer appears exactly once at the end in a parseable `\\boxed{}` format.


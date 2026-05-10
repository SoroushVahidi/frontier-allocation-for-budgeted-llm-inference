# quantity_ledger scaffold v2 (gold-free, conservative)

## Design goals
This v2 prompt is intended to fix two observed `quantity_ledger` failure modes:
1. **Fixed-increment vs compounding**: when the story says the increase is “a fraction of the original/base amount each interval” (often phrased as “percent of the original price”), the increment should be constant each interval (no compounding).
2. **Bonus/secondary fractions use the correct base**: when a story applies a percent **raise** and then asks for a bonus “worth a fraction of a month’s salary”, the bonus must be based on the **raised** salary (not the pre-raise salary).

## v2 template (conceptual structure)
The model should:

1. **Final target restatement (money semantics)**
   - Restate what is being asked in one sentence (e.g., total paid in a year, profit, remaining amount, annualized amount, change).
   - Explicitly name whether the quantity is about **after-raise** values (raise/bonus) vs **original/base** values (fixed increment semantics).

2. **Money ledger table**
   - Make a compact ledger of every distinct numeric quantity that matters:
     - principal/base amount(s)
     - updated/raised amount(s) (if any)
     - cost/revenue/profit components
     - bonus/fraction-of-a-month components
     - totals/remaining.
   - For each percentage/fraction, decide its base:
     - If it is a “fraction of the original/base amount each interval”, compute a **constant increment** from the original/base.
     - If it is a “percent raise on a salary”, compute the raised salary first; any later “fraction of a month’s salary” uses the **raised** salary.
     - For unit/time conversions, place everything onto the same basis before combining.

3. **Compute final value once**
   - Compute the final requested money quantity from the ledger.
   - Output **only the final answer once** at the end as a single parseable numeric inside `\\boxed{...}`.

## Output contract
- Do not output an intermediate numeric value as the “final answer”.
- The only parseable final value must be the last line and match `\\boxed{<number>}`.
- Prompt must remain **gold-free** (no gold answers or external predictions in prompt).


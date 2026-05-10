# Targeted discovery retry v2 dry run

- Output: `/home/soroush/research-next-wt/outputs/targeted_discovery_retry_v2_dry_run_20260508T013214Z`
- Selected cases: 15
- Scaffold counts: `{'quantity_ledger': 6, 'rate_table': 3, 'before_after_state': 3, 'target_difference': 3}`
- Prompt versions: `{'quantity_ledger': 'v2', 'rate_table': 'v1', 'before_after_state': 'v1', 'target_difference': 'v1'}`

## Selected case IDs (up to first 15 in scaffold order)
openai_gsm8k_750, openai_gsm8k_841, openai_gsm8k_1006, openai_gsm8k_1027, openai_gsm8k_1029, openai_gsm8k_1045, openai_gsm8k_1003, openai_gsm8k_1099, openai_gsm8k_906, openai_gsm8k_818, openai_gsm8k_864, openai_gsm8k_1166, openai_gsm8k_1019, openai_gsm8k_970, openai_gsm8k_1187

## Prompt examples (exact; 2 cases only)

### Quantity ledger v2 example: openai_gsm8k_750

```
You are solving a grade-school math word problem using a **quantity ledger**.

Problem:
If a bag of marbles costs $２０ and the price increases by ２０% of the original price every two months, how much would a bag of marbles cost after ３６ months?

Instructions:
- Restate the exact final target quantity the question asks for (for money: total paid/earned, yearly amount, change, remaining, profit, etc.).
- Build a money ledger with named lines for every distinct amount in the story (principal/cost/revenue/bonus/total/remaining as applicable).
- For any percentage or fraction mentioned, decide what it applies to:
  - If the story ties the change to the original/base amount each time, use a fixed increment from the original/base (do not compound).
  - If it describes a raise on a salary, compute the raised salary first; any later bonus defined as a fraction of a month's salary must use the raised salary.
- Convert units and time spans so everything is on the same basis before combining.
- Compute the final requested numeric result carefully.
- Output the **final answer only** at the end as specified below.


Rules:
- Use only the problem statement above; do not assume hidden facts.
- Show your reasoning briefly, then give the final numeric answer as the **last line** in \boxed{} (single value).

```

### Non-quantity (unchanged v1) example: openai_gsm8k_1003 (rate_table)

```
You are solving a grade-school math word problem using a **rate table**.

Problem:
Wendy is five times as old as Colin will be seven years from now. In ２５ years, Colin will be a third as old as Wendy is now. How old is Colin now?

Instructions:
- Identify each relevant **rate** (with units), the **base quantity** or time span, and what **total** is needed.
- Build a small table: entity / rate / quantity or duration / subtotal — one row per line of reasoning.
- Make sure units cancel consistently before you combine rows.
- Compute the final numeric result and verify it matches the story.
- Output the **final answer only** at the end as specified below.


Rules:
- Use only the problem statement above; do not assume hidden facts.
- Show your reasoning briefly, then give the final numeric answer as the **last line** in \boxed{} (single value).

```

## Caveats

- Only `quantity_ledger` template changed; other scaffolds reuse v1 wording.
- Prompts are gold-free; offline scoring uses gold only after generation.
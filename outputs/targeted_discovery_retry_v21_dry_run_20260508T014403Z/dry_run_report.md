# Targeted discovery retry v2.1 — dry run

- Output: `outputs/targeted_discovery_retry_v21_dry_run_20260508T014403Z`
- Selected cases: 10
- Scaffold counts: `{'quantity_ledger': 9, 'rate_table': 1}`
- Prompt versions: `{'quantity_ledger': 'quantity_ledger_v2_1', 'rate_table': 'v1', 'before_after_state': 'v1', 'target_difference': 'v1'}`

## Prompt examples (2 cases only)

### quantity_ledger v2.1 example: openai_gsm8k_750
```
You are solving a grade-school math word problem using a **quantity ledger**.

Problem:
If a bag of marbles costs $２０ and the price increases by ２０% of the original price every two months, how much would a bag of marbles cost after ３６ months?

Instructions:
- Restate the final target quantity exactly once (e.g., annual total paid/earned, profit, remaining amount).
- Build a money ledger with named lines for every relevant amount (principal/cost/revenue/profit/bonus/total/remaining as applicable).
- For each money/income/bonus/payment quantity in the story, do **recurrence classification**:
  - one-time (add once),
  - per-period recurring (multiply by number of periods),
  - total across the whole horizon (do not multiply),
  - unknown (compute only unambiguous parts).
- Critical recurrence rule: **Never multiply a one-time bonus/payment by the number of periods** unless the story explicitly says it repeats.
- Percent/fraction base rule: if a percentage is described as applying to an original/base amount each interval, use a constant increment (no compounding). If a percentage is a raise on salary, compute the raised salary first.
- If the story says a bonus is "worth X months of salary" or "a fraction of a month’s salary", treat it as **one-time**: compute from the referenced month’s (raised) salary and add once.
- Convert units/time spans so everything is on the same basis before combining.
- Compute the final requested numeric result.
- Output the **final answer only** at the end as specified below.


Rules:
- Use only the problem statement above; do not assume hidden facts.
- Show your reasoning briefly, then give the final numeric answer as the **last line** in \boxed{} (single value).

```

### non-quantity (v1) example: openai_gsm8k_906 (rate_table)
```
You are solving a grade-school math word problem using a **rate table**.

Problem:
Seth is twice as old as Brooke. In ２ years, the sum of their ages will be ２８. How old is Seth?

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

- Only `quantity_ledger` prompt is refined to v2.1. Other scaffolds use v1 templates unchanged.
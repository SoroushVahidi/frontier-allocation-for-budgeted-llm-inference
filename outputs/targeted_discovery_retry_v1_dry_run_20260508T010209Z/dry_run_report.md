# Targeted discovery retry v1 — dry run

- **Output:** `outputs/targeted_discovery_retry_v1_dry_run_20260508T010209Z`
- **Selected cases:** 25
- **Scaffold counts:** `{'quantity_ledger': 9, 'rate_table': 7, 'before_after_state': 5, 'target_difference': 4}`

## Cohort summary

First implementation cohort: `money_budget`, `rate_ratio`, `temporal_change`, `difference_comparison` from gold-absent diagnosis, `gold_absent_tagged` only. High provenance risk excluded unless listed in `anchor_cases.md` (anchors with unknown family still fail the family filter).

## Ten anchor IDs (in `anchor_cases.md` order, intersecting selected set)

openai_gsm8k_720, openai_gsm8k_750, openai_gsm8k_841, openai_gsm8k_906, openai_gsm8k_1003, openai_gsm8k_1099, openai_gsm8k_864, openai_gsm8k_818, openai_gsm8k_1166, openai_gsm8k_970

## Example prompts (2 cases only)

### openai_gsm8k_720 (quantity_ledger)

```
You are solving a grade-school math word problem using a **quantity ledger**.

Problem:
Mandy owes Benedict $100. They agreed to have monthly interest of 2%. If Mandy was able to pay it after 3 months, how much should she give to Benedict?

Instructions:
- List every numeric quantity with its unit (or "unitless") and what it measures.
- State clearly which quantity the question asks for (the **target**).
- Write the equation or step-by-step arithmetic plan that connects the quantities to the target.
- Execute the plan carefully and double-check units and percentages.
- Output the **final answer only** at the end as specified below.


Rules:
- Use only the problem statement above; do not assume hidden facts.
- Show your reasoning briefly, then give the final numeric answer as the **last line** in \boxed{} (single value).

```

### openai_gsm8k_750 (quantity_ledger)

```
You are solving a grade-school math word problem using a **quantity ledger**.

Problem:
If a bag of marbles costs $20 and the price increases by 20% of the original price every two months, how much would a bag of marbles cost after 36 months?

Instructions:
- List every numeric quantity with its unit (or "unitless") and what it measures.
- State clearly which quantity the question asks for (the **target**).
- Write the equation or step-by-step arithmetic plan that connects the quantities to the target.
- Execute the plan carefully and double-check units and percentages.
- Output the **final answer only** at the end as specified below.


Rules:
- Use only the problem statement above; do not assume hidden facts.
- Show your reasoning briefly, then give the final numeric answer as the **last line** in \boxed{} (single value).

```

## Next live pilot

Run **10–15** cases from the anchor intersection with Cohere on frozen prompts; compare exact match vs baseline PAL; keep structural-commit guardrail replay at 0 regressions.

## Caveats

- Prompts are **gold-free** by construction; CSV still carries gold for offline scoring only.
- `external_prediction_if_available` may contain non-numeric artifact text from sources.

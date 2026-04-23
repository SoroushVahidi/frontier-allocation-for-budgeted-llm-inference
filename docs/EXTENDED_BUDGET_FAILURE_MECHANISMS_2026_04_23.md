# Extended-budget failure mechanisms (broader-seed run, 2026-04-23)

## Purpose

This is a budget-conditioned mechanism explanation pass for the broader-seed extended-budget robustness bundle.
It is explicitly appendix/robustness analysis and does not change canonical main-paper 4/6/8 artifacts.

- source bundle: `outputs/extended_budget_frontier_20260423Textended101214_multiseed_v1/`
- mechanism bundle: `outputs/extended_budget_failure_mechanisms_20260423Textended101214_multiseed_v1_mechanisms/`
- budgets: `10,12,14`
- methods: `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`

## Mechanism conclusion (root)

The high-budget shift away from `strict_f3` is best explained by a combination of:

1. **higher tree-entry failure** (`absent_from_tree`) versus `strict_gate1_cap_k6` at key budgets, and
2. **higher selection miss rate** (`present_not_selected`) at budget 14.

`output_layer_mismatch` stays near zero and is not the main driver.

## Budget-conditioned evidence highlights

- **Budget 10**: `strict_f3` trails both alternatives mainly from elevated `absent_from_tree`; this is strongest versus `strict_f2`.
- **Budget 12**: `strict_gate1_cap_k6` leads narrowly; mechanism gaps are smaller/mixed, with slight tradeoff between tree-entry and selection across methods.
- **Budget 14**: `strict_gate1_cap_k6` has the clearest edge, with both lower `absent_from_tree` and lower `present_not_selected` than `strict_f3`.

## Method-specific interpretation

- `strict_gate1_cap_k6` high-budget strength is mechanistically coherent: better tree-entry plus better selection retention at budget 14, and still strong tree-entry at 12.
- `strict_f2` remains genuinely competitive, especially at budget 10 where tree-entry is strongest; at 12/14 it is close but generally behind `strict_gate1_cap_k6` on absent/select rates.

## Clarification on budget-12 question

On the broader-seed run (dated 2026-04-23), `strict_f3` does **not** win budget 12; budget 12 and 14 are led by `strict_gate1_cap_k6`.
The mechanism analysis therefore explains why `strict_f3` underperforms at 10 and 14 and remains close-but-not-leading at 12.

## Manuscript positioning

Conservative recommendation is unchanged:

- keep main manuscript positioning unchanged,
- keep 10/12/14 extension appendix-only,
- use this mechanism bundle as explanatory robustness support.

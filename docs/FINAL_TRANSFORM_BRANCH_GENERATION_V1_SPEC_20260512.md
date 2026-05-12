# Final-Transform Branch Generation v1 Spec (2026-05-12)

## Purpose

`final_transform_branch_generation_v1` is a no-API, generation-first preflight for the 70 gold-absent wrong-supported-consensus cases.

The goal is not selector-only repair. The goal is to surface the missing final-transform branch earlier so the candidate pool contains answers that are currently absent.

## Failure Pattern

The targeted failure mode is final-target binding failure:

- wrong final transformation
- wrong entity/unit/state binding
- premature intermediate answer
- wrong-supported consensus collapsing the frontier

The dominant subtype in the split report is `mistargeted_final_transformation`.

## 12-Case Cohere Pilot Results

A 12-case Cohere pilot of `final_transform_branch_generation_v1` produced mixed results:

- exact: 0/12
- new candidates: 11/12
- more target-aligned: 10/12

Breakdown of failures:
- target-correct but arithmetic-wrong: 1
- still wrong-target / relation / state / conversion: 8
- parse / formatting failures: 3

**Conclusion:** Do not scale to 30 cases yet. Prompts were tightened after this pilot before any larger run.

## Prompt Tightening Summary

All branch prompts were revised after the 12-case pilot to address mistargeted final transformations:

- Added target-binding checklist (4 questions) before arithmetic in every prompt.
- Required `FINAL_ANSWER: <number>` format in every prompt.
- Added rule: do not output any other number after `FINAL_ANSWER`.
- Added branch-specific formulas and anti-confusion warnings:
  - `ratio_base_branch`: explicit `target = numerator / base` or `target_percent = 100 * numerator / base`.
  - `profit_revenue_cost_branch`: explicit profit formula; warn against returning sale price, revenue, or total cost.
  - `per_unit_share_branch`: pair/leftover handling; convert single items to pairs before division.
  - `original_before_process_branch`: inverse-operation language; explicit before/after state binding.
  - `difference_or_remainder_branch`: both-sides compute then subtract; warn against one-sided return.
  - `unit_conversion_branch`: state source and target unit; write conversion factor before computing.
  - `target_first_final_transform_branch`: classify final transform type; list used and rejected quantities.

## Final-Answer Parse Contract

Every branch prompt requires the model to end its response with exactly:

```
FINAL_ANSWER: <number>
```

- No text after `FINAL_ANSWER: <number>` is permitted.
- The number must be a bare numeric value (integer or decimal).
- This contract is enforced by the prompt rule and verified by downstream parsing.

## Gold-Pool Split

From `/tmp/gold_pool_split_wrong_consensus_97_report.md`:

| bucket | count |
|---|---:|
| gold_present_not_selected | 21 |
| gold_present_selected | 6 |
| gold_absent_from_pool | 70 |

The 70 gold-absent cases cluster into:

| needed family | count |
|---|---:|
| ratio-base branch | 16 |
| original-before-process branch | 16 |
| per-unit/share branch | 13 |
| profit/revenue/cost branch | 12 |
| target-first final-transform | 9 |
| difference/how-many-more branch | 4 |

The router also includes a fallback `target_first_final_transform_branch` for transformed-target questions that do not cleanly match a specialized family.

## Why This Is Generation-First

Selector tuning cannot recover gold answers that never enter the pool. The preflight therefore reserves the branch budget for specialized final-transform prompts, rather than spending the budget on more ranking only.

## Branch Families

- `ratio_base_branch`
- `original_before_process_branch`
- `per_unit_share_branch`
- `profit_revenue_cost_branch`
- `difference_or_remainder_branch`
- `unit_conversion_branch`
- `target_first_final_transform_branch`
- `unknown_final_transform`

## Routing Cues

Use deterministic question cues only:

- ratio/percentage base: percent, percentage, ratio, fraction, proportion, out of, probability, likelihood, chance, odds, weighted
- original-before-process: originally, before, after halving/doubling/etc., at first, initial, used to be, started with, reverse process
- per-unit/share: each, every, apiece, per person, shared equally, split evenly, per item, pairs of, per pair, each pair, contacts per
- profit/revenue/cost: profit, revenue, cost, price, spend, spent, income, earnings, sold, bought, loss, sale
- difference/remainder: how many more, difference, remainder, left, left over, remaining
- unit conversion: convert, conversion, hours to minutes, minutes to hours, miles to feet, pages per, sheets per, per page, per sheet, items per container/box/bag/pack/carton, tabloid
- target-first final-transform fallback: multi-step transformed-target questions with several numeric candidates but no tighter family match

## Fixed-Budget Policy

- Default to one branch slot per case.
- Do not append extra exploratory branches beyond the configured slot budget.
- If multiple cues fire, keep the strongest final-transform family first and record the rest as alternates.

## Logged Fields

Each dry-run row should record:

- case_id
- question
- question_type from the report
- candidate_branch_families
- selected_branch_family
- branch_slot
- routing_reason
- prompt_template_id
- prompt_template_path
- target_schema_json
- no_gold_leak_ok
- render_ok

The output summary should also record:

- branch family counts
- cue hit counts
- unknown routing count
- loaded gold-absent case count

## No-Gold Leakage Rule

Prompts and call plans must not include:

- gold answer
- answer key
- hidden labels
- any gold-derived feature

This preflight may use the gold-pool report only to recover the 70 case IDs and bucket metadata.

## Offline Preflight Plan

1. Parse the gold-pool split report.
2. Load the matching trace packets.
3. Classify each question with deterministic cues.
4. Render the branch template.
5. Emit dry-run artifacts only.

## Success Criteria

- all 70 gold-absent cases are loaded
- prompts render without unresolved placeholders
- no gold leakage appears
- the call plan stays within the configured branch-slot budget
- the routing summary shows the expected branch families

## Stop Criteria

- any prompt leaks gold or answer-key text
- routing relies on gold-derived inputs
- the branch plan ignores the fixed budget
- the case parser cannot recover the 70 gold-absent ids

## Safe Claims

- the scaffold is deterministic and no-API
- the prompts are gold-free
- the routing is generation-first
- the dry-run is trace-compatible

## Unsafe Claims

- runtime improvement
- exact accuracy improvement
- selector-only fix
- solved candidate-pool coverage

# Outcome-verifier selector roadmap

This document defines the current selector-improvement direction after the 30-case trace-complete Cohere diagnostic.

## Why this roadmap exists

The current DR-v2 candidate pool has hidden headroom: in the paired 30-case trace artifact, an oracle selector over DR-v2 candidate groups reaches 0.8667 accuracy while the actual DR-v2 selector reaches 0.6333 and `external_l1_max` reaches 0.8000.

Simple deployable offline selectors did not improve net accuracy. In particular, support-only recovered some L1-correct / DR-v2-wrong cases but broke a comparable number of currently correct cases.

Therefore the next selector should not be another global support heuristic. It should be a conservative answer-verification override.

## Core formulation

The selector should be framed as candidate correctness estimation:

```text
score(problem, candidate answer, optional reasoning trace, source/support/error features)
  -> estimated probability that the candidate answer is correct
```

A deployable selector then compares the current DR-v2 selected answer against competing candidate answer groups and overrides only when the competing answer is clearly more likely to be correct.

## Immediate method target

Suggested offline rule name:

```text
conservative_outcome_verifier_override_v1
```

Equivalent implementation names may use:

```text
conservative_support_override_v1
answer_group_outcome_verifier_selector_v1
```

The method should:

1. keep current DR-v2 selected answer by default;
2. score competing candidate groups for answer correctness;
3. override only when the competing candidate beats the current answer by a margin;
4. require that the competing answer has low or no consistency/error risk;
5. prefer evidence from multiple independent sources when available;
6. avoid breaking currently correct DR-v2 cases.

## Current evidence to use

Primary artifact:

```text
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/
```

Relevant outputs:

```text
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/diagnostics/offline_selector_variants/offline_selector_variant_summary.json
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/diagnostics/offline_selector_variants/offline_selector_variant_casebook.csv
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/diagnostics/offline_selector_variants/offline_selector_variant_report.md
```

Known values:

| Quantity | Value |
|---|---:|
| `external_l1_max` accuracy | 0.8000 |
| current DR-v2 accuracy | 0.6333 |
| oracle selector ceiling | 0.8667 |
| corrected selector gap | 0.2333 |
| L1-correct / DR-v2-wrong cases | 7 |
| gold-present among those losses | 5 |
| gold-absent among those losses | 2 |

## Required next casebook

Before runtime implementation, produce a focused pattern casebook over:

1. `recoverable_present_not_selected` cases:
   - current DR-v2 wrong;
   - gold present in candidate pool;
   - oracle selector would fix it.

2. `support_only_break` cases:
   - current DR-v2 correct;
   - support-only changes the answer;
   - changed answer is wrong.

The casebook should include candidate groups, support counts reconstructed by normalized answer, source labels, candidate source families, current vs competing consistency/error flags, and a human-readable diagnosis.

## Evaluation metrics

A candidate selector should report:

- total accuracy;
- delta vs current DR-v2 selector;
- delta vs `external_l1_max`;
- number of overrides;
- recoverable present-not-selected cases fixed;
- current-correct cases broken;
- net fixes minus breaks;
- override precision;
- remaining selector failures;
- remaining coverage failures.

## Promotion rule

Do not promote an offline selector to runtime unless it satisfies all of the following on the real 30-case artifact:

1. positive net accuracy gain over current DR-v2;
2. fewer breaks than recovered failures;
3. no use of gold answer or oracle labels in the deployable decision rule;
4. clear decision reasons logged per override;
5. focused tests for both fix and no-break behavior.

If promoted, the next API validation should be a 50-case paired trace-complete run with:

- `external_l1_max`,
- base `direct_reserve_semantic_frontier_v2`,
- the new conservative verifier selector method.

## What not to do

- Do not add another broad list of selector heuristics.
- Do not use oracle/gold information in deployable rules.
- Do not run a new API experiment before the offline conservative selector shows positive net gain.
- Do not treat support-only as sufficient; it already shows fix-and-break behavior.
- Do not switch to full PRM work until outcome-level verification has been tested carefully.

## Relationship to old project

The old `-adaptive-llm-inference` project contributed the useful ideas of cost-aware inference control, headroom/oracle analysis, and answer-error-vs-explanation-warning separation. In this project, those ideas are generalized from binary query-level routing to candidate-level frontier selection.

The old binary route-vs-revise runtime policies should not be copied into this repo as the main method. The useful next idea is answer correctness estimation for candidate groups.

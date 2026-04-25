# STRICT_F3 losses-to-external_l1_max feature dataset (20260425T193000Z)

## Scope
- Provider: cohere
- Model: command-r-plus-08-2024
- Dataset: openai/gsm8k
- Seeds: 11, 23
- Budgets: 4, 6, 8
- Comparison: strict_f3 vs external_l1_max

## Answers to required questions
1. Matched strict_f3/external_l1_max cases now available: **256**.
2. strict_f3-loss / external_l1_max-win cases found: **60**.
3. 100 loss cases reached: **False**.
4. If not, why not: Expanded Cohere coverage yielded 60 strict_f3-loss/external-win cases from 256 matched cases, still below the 100-case target; additional matched coverage is needed.
5. Dominant-feature stability vs previous `20260425T120000Z` report (n=9): **partially_shifted** (failure_tag: `unknown` -> `correct_answer_absent_from_tree`, operation_type: `counting_combinatorics` -> `counting_combinatorics`).
6. Enough evidence now for feature-gated hybrid-controller design: **True** (loss-case count=60).
7. Additional coverage needed for 100-loss target: **40** more strict_f3-loss/external-win cases.

## Outputs
- `outputs/strict_f3_loses_to_external_l1_max_feature_dataset_20260425T193000Z/`
- `docs/STRICT_F3_LOSSES_TO_EXTERNAL_L1_MAX_FEATURE_DATASET_20260425T193000Z.md`

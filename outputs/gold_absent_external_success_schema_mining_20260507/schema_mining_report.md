# Gold-absent schema mining (external-correct vs PAL-wrong)

## A. Why validator-trigger implementation is paused

Scaled PAL-code static triggers did not meet the **promising** usefulness band (high recall on `gold_absent_discovery` with low guardrail FPs) in `outputs/gsm8k_structural_validator_eval_20260507/pal_code_static_audit_scaled/`. Automating retries from those signals alone would add noise.

## B. Case selection

- **Gold-absent pool:** 21 cases (`failure_cluster_summary.csv`).
- **Primary:** PAL wrong ∧ **any external correct** ∧ `final_nodes` reasoning text from a correct external → **11** cases.
- **Secondary:** both PAL and best external wrong — included for contrast using **longest** `external_s1_budget_forcing` trace when available → **10** cases.

| case_id | tier | schemas | pal_fail | ext_ok |
| --- | --- | --- | --- | --- |
| openai_gsm8k_1081 | secondary_both_wrong | temporal_state_update|rate_equation|multi_step_chain | wrong_operator|arithmetic_from_wrong_relation | 0 |
| openai_gsm8k_1099 | primary_external_correct | target_mapping_error|aggregation_total|multi_step_chain | wrong_target_variable | 1 |
| openai_gsm8k_1112 | secondary_both_wrong | aggregation_total|difference_comparison | failed_code_or_empty_code | 0 |
| openai_gsm8k_1115 | secondary_both_wrong | temporal_state_update|multi_step_chain | wrong_operator | 0 |
| openai_gsm8k_1125 | primary_external_correct | rate_equation|temporal_state_update|multi_step_chain | wrong_operator|missing_intermediate_state | 1 |
| openai_gsm8k_1132 | secondary_both_wrong | aggregation_total|product_grouping | wrong_operator|arithmetic_from_wrong_relation | 0 |
| openai_gsm8k_1137 | secondary_both_wrong | temporal_state_update|multi_step_chain | wrong_operator | 0 |
| openai_gsm8k_1139 | secondary_both_wrong | difference_comparison|multi_step_chain | wrong_operator | 0 |
| openai_gsm8k_1144 | secondary_both_wrong | multi_step_chain|aggregation_total | failed_code_or_empty_code | 0 |
| openai_gsm8k_1147 | secondary_both_wrong | target_mapping_error|multi_step_chain | wrong_target_variable | 0 |
| openai_gsm8k_1155 | primary_external_correct | unit_conversion|product_grouping | wrong_operator|arithmetic_from_wrong_relation | 1 |
| openai_gsm8k_1158 | secondary_both_wrong | aggregation_total|difference_comparison | wrong_operator|arithmetic_from_wrong_relation | 0 |
| openai_gsm8k_1162 | secondary_both_wrong | multi_step_chain|rate_equation | wrong_target_variable|arithmetic_from_wrong_relation | 0 |
| openai_gsm8k_1166 | primary_external_correct | multi_step_chain|rate_equation | failed_code_or_empty_code | 1 |
| openai_gsm8k_1187 | primary_external_correct | difference_comparison|multi_step_chain | arithmetic_from_wrong_relation | 1 |
| openai_gsm8k_1198 | primary_external_correct | temporal_state_update|multi_step_chain | overcompressed_one_expression|missing_intermediate_state | 1 |
| openai_gsm8k_1215 | primary_external_correct | difference_comparison|multi_step_chain | failed_code_or_empty_code | 1 |
| openai_gsm8k_1230 | primary_external_correct | aggregation_total|proportional_scaling | wrong_target_variable | 1 |
| openai_gsm8k_1244 | primary_external_correct | unit_conversion|multi_step_chain | wrong_target_variable | 1 |
| openai_gsm8k_1248 | primary_external_correct | target_mapping_error|multi_step_chain | arithmetic_from_wrong_relation | 1 |
| openai_gsm8k_1281 | primary_external_correct | multi_step_chain|aggregation_total | omitted_quantity|arithmetic_from_wrong_relation | 1 |

## C. Schema / failure-mode table (full rows)

See `schema_mining_cases.csv` for problem text, PAL code, stdout, full external reasoning excerpts, operation tags, and static-audit snapshots.

## D. External-success comparison

Externals often succeed by (1) **staged arithmetic** (remainders, halves, multi-day updates), (2) **explicit target restatement** (average vs sum, weeks vs days), (3) **additive rate×time** instead of multiplying incompatible rates.

### Top 5 representative primary cases (hand-picked diversity)

```json
[
  {
    "case_id": "openai_gsm8k_1099",
    "required_schemas": "target_mapping_error|aggregation_total|multi_step_chain",
    "pal_failure_modes": "wrong_target_variable",
    "external_method_with_trace": "external_s1_budget_forcing"
  },
  {
    "case_id": "openai_gsm8k_1125",
    "required_schemas": "rate_equation|temporal_state_update|multi_step_chain",
    "pal_failure_modes": "wrong_operator|missing_intermediate_state",
    "external_method_with_trace": "external_s1_budget_forcing"
  },
  {
    "case_id": "openai_gsm8k_1155",
    "required_schemas": "unit_conversion|product_grouping",
    "pal_failure_modes": "wrong_operator|arithmetic_from_wrong_relation",
    "external_method_with_trace": "external_s1_budget_forcing"
  },
  {
    "case_id": "openai_gsm8k_1187",
    "required_schemas": "difference_comparison|multi_step_chain",
    "pal_failure_modes": "arithmetic_from_wrong_relation",
    "external_method_with_trace": "external_tale_prompt_budgeting"
  },
  {
    "case_id": "openai_gsm8k_1198",
    "required_schemas": "temporal_state_update|multi_step_chain",
    "pal_failure_modes": "overcompressed_one_expression|missing_intermediate_state",
    "external_method_with_trace": "external_tale_prompt_budgeting"
  }
]
```

## E. Top repeated missing schemas (counts over all 21)

```json
{
  "multi_step_chain": 16,
  "aggregation_total": 7,
  "temporal_state_update": 5,
  "difference_comparison": 5,
  "rate_equation": 4,
  "target_mapping_error": 3,
  "unit_conversion": 2,
  "product_grouping": 2,
  "proportional_scaling": 1
}
```

### Schema × dominant PAL failure (first schema token cross fail-modes)

```json
{
  "aggregation_total": {
    "wrong_target_variable": 1,
    "failed_code_or_empty_code": 1,
    "wrong_operator": 2,
    "arithmetic_from_wrong_relation": 2
  },
  "difference_comparison": {
    "arithmetic_from_wrong_relation": 1,
    "failed_code_or_empty_code": 1,
    "wrong_operator": 1
  },
  "multi_step_chain": {
    "failed_code_or_empty_code": 2,
    "omitted_quantity": 1,
    "arithmetic_from_wrong_relation": 2,
    "wrong_target_variable": 1
  },
  "rate_equation": {
    "wrong_operator": 1,
    "missing_intermediate_state": 1
  },
  "target_mapping_error": {
    "wrong_target_variable": 2,
    "arithmetic_from_wrong_relation": 1
  },
  "temporal_state_update": {
    "overcompressed_one_expression": 1,
    "missing_intermediate_state": 1,
    "wrong_operator": 3,
    "arithmetic_from_wrong_relation": 1
  },
  "unit_conversion": {
    "wrong_operator": 1,
    "arithmetic_from_wrong_relation": 1,
    "wrong_target_variable": 1
  }
}
```

## F. Candidate targeted retry ideas

```json
[
  {
    "idea": "state_table_temporal_retry",
    "targets_schema": [
      "temporal_state_update"
    ],
    "approx_cases_primary": 2,
    "approx_cases_all": 5,
    "clear_trigger": "medium",
    "guardrail_risk": "high_if_misdetects_multiplicative_rate_problems",
    "needs_api_now": false,
    "offline_testable": true
  },
  {
    "idea": "rate_equation_retry",
    "targets_schema": [
      "rate_equation"
    ],
    "approx_cases_primary": 2,
    "approx_cases_all": 4,
    "clear_trigger": "low",
    "guardrail_risk": "high",
    "needs_api_now": false,
    "offline_testable": true
  },
  {
    "idea": "aggregation_total_retry",
    "targets_schema": [
      "aggregation_total"
    ],
    "approx_cases_primary": 3,
    "approx_cases_all": 7,
    "clear_trigger": "low",
    "guardrail_risk": "medium",
    "needs_api_now": false,
    "offline_testable": true
  },
  {
    "idea": "target_variable_rewrite_retry",
    "targets_schema": [
      "target_mapping_error"
    ],
    "approx_cases_primary": 2,
    "approx_cases_all": 3,
    "clear_trigger": "low_without_NLU",
    "guardrail_risk": "medium",
    "needs_api_now": false,
    "offline_testable": "partial_keyword_checks_only"
  },
  {
    "idea": "quantity_grounding_retry",
    "targets_schema": [
      "unit_conversion",
      "product_grouping"
    ],
    "approx_cases_primary": 2,
    "approx_cases_all": 3,
    "clear_trigger": "medium_for_unit_mismatch_heuristics",
    "guardrail_risk": "medium",
    "needs_api_now": false,
    "offline_testable": true
  }
]
```

## G. Which idea to implement next

Targeted prompting for multi_step_chain + explicit final target restatement (addresses wrong_target_variable and many relation errors) before narrow rate/table triggers.

**Dominant counted schema:** `multi_step_chain`.

## H. API needed now?

**No.** This analysis uses archived traces and code only.

## I. Exact next query

> Prototype **offline** a *target-restatement + staged checklist* PAL retry template on **11** primary cases: force explicit “quantity asked” / units / final transform (half, average, weeks) before codegen; benchmark precision on expanded gold-absent CSV before any API.

# RelationReady Manual Audit Guide

Use this guide to label the seed audit CSV for the first RelationReady / relation_verifier manual pass.

## Manual label fields

### `relation_ready_label_manual`

- `ready` — the candidate trace represents the requested semantic relation and can be used as a positive seed.
- `not_ready` — the candidate trace is wrong, incomplete, or semantically mismatched.
- `uncertain` — the row is ambiguous or you cannot decide from the available evidence.
- `gold_inconsistent` — the row appears to conflict with the gold metadata or is not a valid training seed source.

### `first_error_axis_manual`

- `wrong_target_variable`
- `wrong_relation_composition`
- `wrong_process_state`
- `source_fact_missing`
- `unit_scale_error`
- `percentage_base_error`
- `per_unit_total_error`
- `total_difference_error`
- `original_final_state_error`
- `arithmetic_only_error`
- `formula_format_error`
- `prompt_gold_inconsistent`
- `insufficient_evidence`

## Short examples

- **“How many more” answered by a sum** → `total_difference_error`
- **“How much before spending” answered by the remaining amount** → `original_final_state_error`
- **Percentage computed from the wrong base** → `percentage_base_error`
- **Correct relation but arithmetic slip** → `arithmetic_only_error`

## Labeling notes

- `gold_answer_metadata_only` is metadata only. Do not use it as an inference feature.
- If the candidate trace is clearly the wrong semantic relation, mark `not_ready` even if the arithmetic is internally consistent.
- If there is not enough evidence to decide, use `uncertain` and `insufficient_evidence`.

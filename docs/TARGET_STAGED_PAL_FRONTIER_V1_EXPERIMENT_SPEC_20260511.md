# target_staged_pal_frontier_v1 Experiment Spec (2026-05-11)

## 1. Purpose

`target_staged_pal_frontier_v1` is a no-API candidate-generation preflight for PAL frontier work.

The replay result for `pal_frontier_structural_target_replay_v1` showed that target checks can improve replay-ready cases, but the larger blocker is still candidate-pool coverage. Many failure slices have no replay-ready candidates at all, so the next bottleneck is generation/discovery rather than selector-only repair.

This preflight does not change runtime defaults, does not call model APIs, and does not claim superiority over `external_l1_max`.

## 2. Failure Mechanism Targeted

The method targets the failure mode where the search frontier collapses into a wrong-but-consistent answer family before the final target is explicitly bound.

Observed sub-mechanisms:

- wrong target variable
- premature intermediate answer
- wrong entity / wrong unit / wrong state binding
- wrong operation relation
- wrong-supported consensus that reinforces a bad candidate pool

The preflight is designed to force target binding before arithmetic so candidate generation can surface target-consistent branches earlier.

## 3. Method ID and Alias

- Method ID: `target_staged_pal_frontier_v1`
- Alias: `ts_pal_frontier_v1`

Scope:

- no-API preflight only
- candidate-generation design and dry-run scaffolding
- trace-compatible with existing structural replay features
- not a runtime default

## 4. Target-Schema JSON Contract

The schema prepass must emit only this contract, derived deterministically from the question and not from gold:

```json
{
  "target_variable": "string",
  "entity": "string",
  "unit": "string",
  "time_or_state": "string",
  "operation_goal": "string",
  "known_quantities": [
    {
      "name": "string",
      "value": "string",
      "unit": "string"
    }
  ],
  "required_relations": [
    "string"
  ],
  "uncertainty": true
}
```

Interpretation:

- `target_variable`: the final quantity the answer must resolve to
- `entity`: the thing being counted or measured
- `unit`: canonical unit or `unknown`
- `time_or_state`: before/after/now/final-state style context
- `operation_goal`: add, subtract, compare, convert, ratio, equation, backward-check, or similar
- `known_quantities`: numeric facts explicitly present in the question
- `required_relations`: relations needed for a valid solution
- `uncertainty`: `true` whenever the schema is ambiguous or multiple bindings are plausible

## 5. Branch Families

The preflight reserves one schema-prepass step plus five branch families:

1. `target_schema_prepass`
2. `target_first_reasoning`
3. `entity_unit_ledger_reasoning`
4. `equation_first_reasoning`
5. `pal_code_with_required_target_variable`
6. `backward_from_target_check`

Branch-family intent:

- target-first reasoning: bind the final target before arithmetic
- entity/unit ledger reasoning: maintain a compact entity-unit ledger
- equation-first reasoning: map quantities into equations before computing
- PAL/code with required final target variable: code must assign and print the target variable named in the schema
- backward-from-target check: verify the path from target back to source facts

## 6. Fixed-Budget Policy

- Keep the total action budget aligned with the current PAL+retry budget.
- Reserve one branch slot for target-schema-conditioned generation.
- Do not increase total samples unless explicitly approved later.
- Do not change runtime defaults.
- Do not add extra exploratory branches beyond the manifest budget.

Preflight interpretation:

- one deterministic schema-prepass step
- five target-conditioned branch families
- no paid-model calls

## 7. Expected Metadata Fields

Each call-plan row should carry at least:

- `experiment_id`
- `alias`
- `slice_name`
- `case_id`
- `question_source`
- `target_schema`
- `target_variable`
- `entity`
- `unit`
- `time_or_state`
- `operation_goal`
- `known_quantities`
- `required_relations`
- `uncertainty`
- `branch_family`
- `branch_slot`
- `plan_stage`
- `prompt_template_id`
- `call_plan_id`
- `budget_total`
- `parse_ok`
- `render_ok`
- `no_gold_leak_ok`
- `trace_compat_ok`

The dry-run outputs should also preserve the existing structural replay fields:

- `target_tuple`
- `entity_unit_ledger_proxy`
- `final_answer_role`
- `last_operation_family`
- `target_alignment_score`
- `intermediate_answer_penalty`
- `duplicate_wrong_signature`
- `structural_selector_score`

## 8. Manifest Fields

Machine-readable manifest draft:

- `experiment_id`
- `alias`
- `description`
- `mode`
- `runtime_defaults_changed`
- `api_calls_allowed`
- `total_action_budget`
- `resolved_total_action_budget`
- `reserve_target_schema_slot`
- `extra_samples`
- `branch_families`
- `prompt_templates`
- `slice_definitions`
- `reference_case_banks`
- `target_schema_contract`
- `expected_output_files`
- `validation_flags`

## 9. Prompt Templates

Create one template per step:

- `target_schema_prepass.md`
- `target_first_reasoning.md`
- `entity_unit_ledger_reasoning.md`
- `equation_first_reasoning.md`
- `pal_code_with_required_target_variable.md`
- `backward_from_target_check.md`

Template rules:

- include `{{question}}`
- include `{{target_schema_json}}` where appropriate
- include a branch-family tag in the rendered text
- explicitly forbid hidden reference answers, answer-key information, and label metadata
- explicitly require target binding before arithmetic
- avoid evaluation-label leakage

## 10. No-API Validation Plan

Required dry-run checks:

1. Schema parser/serializer roundtrip
2. Required schema keys preserved
3. Unknown fields ignored or rejected explicitly
4. `uncertainty` survives roundtrip exactly
5. Prompt rendering with all templates
6. No unresolved placeholders in rendered prompts
7. No-gold / no-answer-key leakage in rendered prompts
8. Dry-run call-plan generation only
9. No API client construction
10. Trace compatibility with existing structural replay features
11. Candidate rows can be flattened to CSV and JSONL without losing the replay fields

## 11. Evaluation Slices

Use the offline slices in this order:

- primary: `97` wrong-supported-consensus cases
- secondary: `43` direct-L1-anchor-potential cases
- guardrail: `30`-case four-way pilot
- caution: `15`-case Direct L1 strong-seed diagnostic

Notes:

- The `97` and `43` slices are allowed to use deterministic synthetic question placeholders if the audit source does not expose question text.
- The `30` and `15` slices should prefer real exact-case questions when available.
- The `30`-case pilot is a guardrail only, not a final headline.

## 12. Success Criteria

This preflight succeeds if:

- the schema prepass is deterministic and gold-free
- all prompt templates render cleanly
- no forbidden leakage appears in prompts or plans
- the dry-run call plan is trace-compatible with the structural replay feature layer
- the preflight produces the expected outputs under a timestamped directory
- the new target-staged path is ready for a small offline candidate-generation pilot

Meaningful success for the next runtime step would be:

- more replay-ready candidate coverage on the target slices
- more target-consistent branches surfaced before selection
- fewer cases with no candidate pool

## 13. Stop Criteria

Stop or pivot if any of the following happen:

- schema extraction is unstable on a large fraction of cases
- prompt rendering leaks a gold field or answer key
- dry-run planning requires an API client
- trace compatibility breaks the current structural replay fields
- the branch plan only reshuffles wrong candidates without improving candidate-pool coverage
- the guardrail slice regresses materially

## 14. Safe Claims / Unsafe Claims

Safe claims:

- the preflight is no-API
- the schema and prompt scaffold are deterministic
- the dry-run traces are compatible with the current structural replay feature layer
- the design explicitly targets candidate generation rather than selector-only repair

Unsafe claims:

- that this beats `external_l1_max`
- that the new method is already a runtime improvement
- that the 97-case focus slice is solved
- that the preflight proves final accuracy gains

## 15. Exact Next Implementation Steps

1. Add the manifest and prompt templates.
2. Implement the dry-run preflight script with deterministic schema extraction and call-plan emission.
3. Validate schema roundtrips and prompt rendering on synthetic fixtures.
4. Run the 30-case guardrail slice as a no-API sanity check.
5. Run the 43-case direct-L1-anchor-potential slice next.
6. Run the 97-case wrong-supported-consensus slice after the guardrail is clean.
7. If the candidate pool expands meaningfully, move to a small offline runtime pilot.
8. If the branch plan only reshuffles existing wrong candidates, pivot to stronger candidate-generation or source-side discovery.

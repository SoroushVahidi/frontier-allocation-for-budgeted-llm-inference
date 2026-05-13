# Declarative Equation Branch v2 Spec

Date: 2026-05-13
Status: No-API scaffold only
Method ID: `declarative_equation_branch_v2`

## Motivation

`declarative_equation_branch_v1` showed a narrow coverage gain on a 20-case live slice, but the branch remained structurally weak:

- relation prose was over-penalized by undeclared-variable tokenization
- equations often introduced undeclared derived symbols
- some variable values were emitted as non-JSON numeric expressions instead of JSON numbers
- `solution_formula` was not consistently executable from declared bindings

The v2 contract is meant to align prompt, schema, and validator around one stricter separation:

- `relations` are prose-only semantic statements
- `equations` are the only place for algebraic equalities
- `solution_formula` is the only executable expression

## Required Output Fields

The prompt requires exactly these fields:

- `requested_target`
- `target_variable`
- `target_unit`
- `process_state`
- `source_facts`
- `variables`
- `relations`
- `equations`
- `solve_for`
- `solution_formula`
- `final_answer`
- `uncertainty`
- `abstain_reason`

Each variable must be an object:

```json
{
  "name": "snake_case",
  "value": 12.0,
  "unit": "string",
  "description": "short source-grounded meaning",
  "source": "given|derived|unknown"
}
```

## Hard Validation Rules

- Strict JSON only.
- `target_variable == solve_for`.
- `solve_for` must be declared in `variables[].name`.
- `variables[].value` must be a JSON number or `null`, never a string or expression.
- Every symbol used in `equations` must be declared in `variables`.
- Every symbol used in `solution_formula` must be declared in `variables`.
- `relations` are prose-only semantic descriptions and are not tokenized for undeclared-variable checks.
- `equations` must be machine-checkable strings with declared names and arithmetic operators.
- `solution_formula` must be one safe arithmetic expression executable by the local AST evaluator.
- `final_answer` must match the evaluated `solution_formula` when evaluation succeeds.
- `source_facts` may cite only question facts.
- Gold answers, answer keys, private evaluation metadata, and dataset annotations must not enter prompts.

## Validator Posture

v2 keeps relation handling intentionally relaxed relative to v1:

- relation presence is required
- relation prose is retained as semantic context
- undeclared-variable checks do not run over relation prose

v2 stays strict on:

- equation undeclared variables
- formula undeclared variables
- safe formula execution
- numeric variable values
- target / solve-for agreement

## Preflight Requirements

The no-API preflight must:

- take selected cases from JSONL
- allow optional topology metadata outside `prompt_text`
- allow optional prior v1 output metadata outside `prompt_text`
- render `provider_requests_dry_run.jsonl`
- audit prompts for gold / answer-key / forbidden-string leakage
- emit:
  - `manifest.json`
  - `selected_cases.jsonl`
  - `provider_requests_dry_run.jsonl`
  - `prompt_audit.json`
  - `dry_run_report.md`

Default out dir:

```text
/tmp/declarative_equation_branch_v2_preflight
```

## Runner Requirements

The runner must:

- default to dry-run
- require `--allow-api` for live mode
- support Cohere only when the existing pattern is explicitly enabled
- parse JSON responses
- validate the v2 schema
- evaluate `solution_formula` locally with the safe AST evaluator
- use gold only post-hoc when a casebook is supplied
- emit:
  - `manifest.json`
  - `raw_responses.jsonl`
  - `parsed_responses.jsonl`
  - `declarative_candidate_rows.jsonl`
  - `pilot_summary.json`
  - `dry_run_report.md` or `live_report.md`

## Required Summary Metrics

- `calls_attempted`
- `calls_succeeded`
- `json_parse_ok_count`
- `schema_ok_count`
- `relaxed_relation_schema_ok_count`
- `equation_strict_ok_count`
- `formula_strict_ok_count`
- `target_solve_for_match_count`
- `solve_for_declared_count`
- `numeric_variable_value_ok_count`
- `final_answer_extracted_count`
- `executable_final_answer_count`
- `gold_recovered_by_final_answer_count`
- `gold_recovered_by_executable_answer_count`
- `issue_summary`

## Safe Claims

- v2 is a stricter no-API scaffold than v1 for equation/formula discipline.
- v2 separates relation prose from executable algebra on purpose.
- Dry-run artifacts can verify prompt safety and schema behavior without provider calls.

## Unsafe Claims

- Do not claim runtime accuracy improvement before a bounded live pilot.
- Do not treat relation relaxation as proof that the generation bottleneck is solved.
- Do not use post-hoc gold scoring as prompt context.

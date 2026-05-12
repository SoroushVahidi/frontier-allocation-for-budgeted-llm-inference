# Declarative Equation Branch v1 Spec

Date: 2026-05-12
Status: No-API scaffold only
Method ID: `declarative_equation_branch_v1`

## Why "gold absent" was insufficient

`gold absent from candidate pool` was useful as a selector ceiling diagnosis, but it was too coarse for method design. It did not say:

- which explored node was closest to the correct target
- whether the right quantities were already present but misbound
- whether the miss was a relation-construction failure, a final-state binding failure, a unit conversion miss, or only arithmetic slippage

The missing-gold topology analysis was added to localize those misses at the edge / topology level rather than treating all gold-absent cases as the same failure.

## Topology Result That Motivates This Method

The final audited API-assisted 20-case topology bundle is:

- `outputs/missing_gold_topology_v1_20260512T231758Z/`

Observed counts on that bounded slice:

- `relation_composition_missing = 7`
- `prompt_gold_inconsistent = 5`
- `final_after_process = 4`
- `arithmetic_precision = 3`
- `unit_conversion = 1`

Interpretation:

- relation construction is the dominant bottleneck
- final-state / after-state binding is still materially present
- arithmetic-only repair exists, but it is not the main bottleneck
- prompt/gold inconsistencies must be partitioned away from clean runtime gating

## Purpose

`declarative_equation_branch_v1` is a scaffold for a candidate-generation branch that does:

1. target relation first
2. equation composition second
3. arithmetic last

The method is intentionally aimed at the topology result above. It is not a "formula execution only" branch. It exists to force explicit construction of the right target relation before any arithmetic expression is trusted.

## Failure Modes It Explicitly Tries To Address

### `relation_composition_missing`

Require a relation layer before the final formula:

- named variables
- declarative relations
- explicit equations
- target solve variable

### `final_after_process`

Require explicit `process_state` with:

- `before`
- `after`
- `final`
- `original`
- `unknown`

This is meant to catch profit / remaining / pre-change / post-change target confusion.

### `unit_conversion`

Require:

- explicit `target_unit`
- variable units
- unit-preserving relations

### `arithmetic_precision`

Arithmetic is still handled, but only after the relation contract is coherent. The local evaluator is a validation layer, not the main method hypothesis.

### `prompt_gold_inconsistent`

These cases must be flagged and partitioned. They are not clean runtime promotion evidence. Topology metadata may be carried offline, but gold-bearing labels must not enter prompts.

## Required Output Schema

The prompt requires exactly these fields:

- `requested_target`
- `target_variable`
- `target_unit`
- `process_state`
- `source_facts`
- `variables`
- `relations`
- `equations`
- `equation_rationale`
- `solve_for`
- `solution_formula`
- `final_answer`
- `uncertainty`
- `abstain_reason`

Required structural rules:

- `target_variable == solve_for`
- every variable used in `relations`, `equations`, or `solution_formula` must appear in `variables`
- `relations` and `equations` must be declarative, not prose paragraphs
- `source_facts` may only restate question/context facts
- `process_state` must be one of `before|after|final|original|unknown`
- `final_answer` must be derived from solving `target_variable`
- if the relation is ambiguous, set `uncertainty=true` and provide an `abstain_reason`

## No-Gold Prompt Rules

Gold answers may be used only for offline analysis/reporting. They may not appear in provider prompts or request context.

Forbidden prompt content includes:

- `gold_answer`
- `answer_key`
- hidden labels / hidden label metadata
- `gold:` / `gold=`

Prior branch outputs may be included only as model-generated context and must remain gold-free.
Optional topology labels may be attached as offline metadata, but if they contain gold-bearing information they must not enter `prompt_text`.

## Validation Layer

The scaffold validates:

- strict JSON parsing
- required-field presence
- `target_variable == solve_for`
- `process_state` enumeration
- `relations` presence
- `equations` presence
- unknown-variable detection across relations and equations
- safe AST-based `solution_formula` evaluation
- final-answer / evaluated-formula consistency when both exist
- post-hoc gold scoring only if a casebook is provided

This is an internal coherence layer, not proof of task correctness.

## Summary Metrics

The runner summary must report:

- `calls_attempted`
- `calls_succeeded`
- `json_parse_ok_count`
- `schema_ok_count`
- `relation_present_count`
- `equation_present_count`
- `target_solve_for_match_count`
- `formula_eval_ok_count`
- `final_answer_extracted_count`
- `executable_final_answer_count`
- `gold_recovered_by_final_answer_count`
- `gold_recovered_by_executable_answer_count`
- `issue_summary`

Gold recovery counts are post-hoc only.

## Safe Claims

- The scaffold enforces a stricter target/relation/equation contract than BFTC-only or formula-only repair.
- The topology result motivates relation-first construction as the next no-API scaffold.
- Dry-run artifacts can verify prompt safety and schema/validation behavior without any provider calls.

## Unsafe Claims

- Do not claim the scaffold improves runtime accuracy before a bounded live pilot.
- Do not claim this solves the dominant error mode merely because the schema is more explicit.
- Do not treat prompt/gold-inconsistent cases as clean evidence for or against runtime promotion.

## Future Live Pilot Design

Any later live pilot should:

- stay bounded, explicit, and gold-free
- separate prompt/gold-inconsistent cases from the clean slice
- report relation-present and schema-valid rates before focusing on exact recovery
- compare model final answers and executable answers separately
- preserve the distinction between candidate generation evidence and selector-only evidence

## Expected Use

This scaffold is ready first for no-API preflight and dry-run inspection.
Any live use requires explicit approval and should remain a separate uncommitted / later-commit step until reviewed.

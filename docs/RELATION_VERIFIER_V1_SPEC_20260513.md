# Relation Verifier V1 Spec
**Date:** 2026-05-13
**Experiment:** `relation_verifier_v1`

## Motivation

The current failure pattern is no longer just arithmetic or formatting noise. Across:

- BFTC executable repair
- declarative equation branch v1
- declarative equation branch v2

the recurring issue is that models can produce fluent, executable-looking candidates whose semantic relation does not actually match the target. A relation verifier is the next no-API step because it checks whether a proposed candidate is grounded in the question before that candidate is used as a branch gate, selector feature, or live-pilot input.

This is a diagnostic and gating scaffold, not a claim of external-baseline improvement.

## What It Must Distinguish

The verifier should separate these failure modes:

- formatting/schema failure
- arithmetic failure
- wrong relation
- wrong target variable
- missing source fact
- wrong process state
- unit/scale error
- prompt/gold inconsistency

The main purpose is to tell whether the candidate relation/equation is internally aligned with the question, not to recover gold from scratch.

## Safe and Unsafe Claims

Safe claims:

- whether the candidate relation appears to match the requested target
- whether the target variable appears to match the requested target
- whether the equations are grounded in the stated source facts
- whether the process state and unit/scale handling are consistent
- whether the candidate is executable as written

Unsafe claims:

- any claim that the verifier proves correctness against gold
- any claim that a live run beats the external baseline
- any claim that a single small slice is representative of the full task

## No-Gold Prompt Rules

The verifier prompt must not use:

- gold answers
- answer keys
- private evaluation metadata
- dataset annotations

The prompt should use only:

- the question
- `requested_target` if available
- candidate variables
- candidate relations
- candidate equations
- `solution_formula`
- `final_answer`
- `process_state`
- `source_facts`
- supporting prior-candidate summaries, if available

Gold may be used only post-hoc in offline analysis, never in provider prompts.

## Future Use

This scaffold is intended for future use as:

- a branch gate before spending more budget
- a selector feature for ranking candidate relations
- a no-API diagnostic for relation construction failures

It is not external-baseline evidence and should not be presented as such.


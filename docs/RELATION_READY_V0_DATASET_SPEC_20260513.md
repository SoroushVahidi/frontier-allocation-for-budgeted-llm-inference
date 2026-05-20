# RelationReady v0 Dataset Spec
**Date:** 2026-05-13
**Status:** Offline scaffold only. No model training or live API use.

## Purpose

`RelationReady_v0` is an offline training/evaluation table for a learned relation-correctness verifier. The table is one row per candidate artifact, not one row per case. It combines:

- BFTC-only answer artifacts
- BFTC executable-repair artifacts
- declarative equation branch v1 artifacts
- declarative equation branch v2 artifacts
- relation verifier v1 primary-candidate judgments
- missing-gold topology labels
- post-hoc casebook labels

The goal is to support a later no-API classifier that predicts whether a candidate is safe to trust for the requested target.

## Scope

This scaffold is explicitly offline:

- no provider prompts
- no model/API calls
- no mutation of source artifacts
- gold labels used only post-hoc for supervised labels/features

It is not evidence of baseline improvement.

## Row Granularity

Each row represents one candidate artifact for one case, with `candidate_source` in:

- `bftc_only`
- `bftc_executable`
- `declarative_v1`
- `declarative_v2`
- `relation_verifier_v1_primary`

`relation_verifier_v1_primary` refers to the verifier judgment over the primary candidate used in the verifier pilot, which is generally the declarative-v2 candidate on this 20-case slice.

## Required Columns

Minimum required fields:

- `case_id`
- `normalized_case_id`
- `candidate_id`
- `candidate_source`
- `topology_label`
- `prompt_gold_inconsistent_flag`
- `final_answer`
- `executable_final_answer`
- `exact_final_answer_posthoc`
- `exact_executable_answer_posthoc`
- `any_prior_exact_posthoc`
- `relation_verifier_error_type`
- `relation_verifier_accept`
- `relation_verifier_false_accept`
- `target_relation_correct`
- `target_variable_correct`
- `source_facts_sufficient`
- `equations_match_source_facts`
- `process_state_correct`
- `unit_scale_correct`
- `arithmetic_executable`
- `target_variable_ok`
- `target_binding_ok`
- `source_facts_ok`
- `process_state_ok`
- `unit_scale_ok`
- `equation_semantics_ok`
- `formula_executable_ok`
- `first_error_axis`
- `relation_ready_label`
- `relation_ready_source`
- `label_confidence`
- `notes`

The builder may add extra ML-ready features and one-hot fields.

## Conservative Label Policy

`relation_ready_label=true` only if:

- the candidate is post-hoc exact by final answer or executable answer
- and no known semantic/topology blocker is present

`relation_ready_label=false` if any of the following hold:

- verifier false accept
- wrong relation
- wrong target variable
- missing source fact
- wrong process state
- unit/scale error
- prompt/gold inconsistency
- known semantically wrong equation/formula

`relation_ready_label=null` if evidence is insufficient.

This is intentionally conservative because the current bottleneck is false acceptance of locally plausible but globally wrong candidates.

## Recommended Feature Families

### Structural features

- `has_formula`
- `has_executable_answer`
- `formula_eval_ok`
- `target_solve_for_match`
- `solve_for_declared`
- `equation_strict_ok`
- `formula_strict_ok`
- `numeric_variable_value_ok`

### Verifier-derived features

- `relation_verifier_accept_bool`
- `relation_verifier_error_type`
- per-error-type one-hot columns

### Topology / provenance features

- `topology_label`
- per-topology one-hot columns
- `candidate_source`
- per-source one-hot columns
- `prompt_gold_inconsistent_flag`

## Output Files

The builder writes:

- `relation_ready_rows.jsonl`
- `relation_ready_rows.csv`
- `relation_ready_summary.json`
- `relation_ready_report.md`

Output defaults to a timestamped directory under `outputs/`.

## Split Guidance

The builder should emit suggested train/val/test splits based on normalized case ID, but it should not train a model yet.

## Safe Reuse

This dataset is safe to build from internal offline artifacts because:

- it uses existing outputs only
- it does not place gold into prompts
- it does not call providers
- it preserves original evidence hierarchy


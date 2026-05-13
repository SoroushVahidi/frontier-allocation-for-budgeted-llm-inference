RelationReady annotation guide

Goal
- Provide clear instructions so annotators can label whether a candidate relation/formula is semantically correct for the requested target, even when locally plausible and executable.

Annotation unit
- One candidate-per-row tied to a case_id and candidate_id. Each row contains: case_id, candidate_text (verbal), candidate_formula (executable string if present), candidate_source (e.g., declarative_v2, executable_formula), supporting_evidence (excerpted facts), gold_present_flag (for internal QA only), and other metadata.

Primary labels
- accept: boolean (true if candidate is semantically correct for the requested target)
- error_type: one of {prompt_gold_inconsistent, relation_composition_missing, final_after_process, arithmetic_precision, unit_scale_error, wrong_variable_binding, missing_source_fact, other}
- rationale: short free-text explaining why accept/reject

Annotation protocol
1. Read the case prompt (without gold) and candidate text/formula.
2. Try to bind candidate symbols to prompt variables. If binding fails, label wrong_variable_binding or missing_source_fact.
3. If binding succeeds, check whether the relation chain covers required steps; if not, relation_composition_missing.
4. If relation is correct but numeric discrepancy arises from arithmetic rounding, label arithmetic_precision.
5. Use final_after_process when candidate requires a multi-step process that the candidate omits or misorders.
6. Provide a concise rationale for each reject/accept.

Quality control
- Every item gets two independent annotations; disagreements go to adjudication.
- Record annotator IDs and time; sample items for gold-review by senior annotator.

Privacy/provenance
- Do not include gold values in prompts shown to annotators. Gold may be revealed only during adjudication and not as input to models.


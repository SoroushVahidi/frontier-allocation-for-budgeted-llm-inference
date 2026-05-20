RelationReady JSON schema (summary)

Each training row (JSON object) fields:
- case_id: string (case identifier)
- candidate_id: string
- candidate_text: string (verbal candidate)
- candidate_formula: string or null (executable representation, e.g., Python/SymPy expression)
- candidate_source: string (e.g., declarative_v2, bftc, exec_formula)
- supporting_evidence: array[string] (optional excerpts from prompt/context used by annotator)
- deterministic_checks: object {
    "formula_parsable": boolean,
    "formula_exec_ok": boolean,
    "formula_exec_value": number|null,
    "unit_match": boolean|null
  }
- accept: boolean (annotator label)
- error_type: string|null (see guide taxonomy)
- rationale: string (short explanation)
- annotator_id: string
- annotation_time: iso8601 timestamp
- adjudicated: boolean
- adjudicator_id: string|null
- split: string in {"train","val","test","eval_holdout"}

Notes
- Gold values must not be embedded into candidate_text or candidate_formula fields used for training.
- "eval_holdout" split must contain all live/pilot slices reserved for final evaluation.


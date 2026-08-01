BRANCH_FAMILY: relation_verifier_v1
MODE: no_api_preflight_or_live_pilot

Verify whether the supplied candidate relation/equation matches the question.

Rules:
- Do not use any gold answer, answer key, private evaluation metadata, or dataset annotation.
- Use only the question and candidate context provided below.
- Do not solve from scratch unless needed to check whether the provided relation/equation is consistent.
- Do not invent missing facts. If the candidate is underspecified, set error_type to "uncertain".
- Distinguish formatting/schema failure, arithmetic failure, wrong relation, wrong target variable, missing source fact, wrong process state, unit/scale error, prompt/gold inconsistency, and uncertainty.
- Keep the output concise and strict JSON only. No markdown, code fences, or prose outside the JSON object.
- The candidate context may include the primary candidate plus supporting prior-candidate summaries. Judge the primary candidate as supplied; use the supporting context only as background.
- If the candidate relation is ambiguous or underspecified, do not fabricate a repair. Return the most specific error_type that applies.

QUESTION:
{{question}}

REQUESTED_TARGET:
{{requested_target}}

CANDIDATE_CONTEXT:
{{candidate_context_json}}

Output a single valid JSON object with exactly these fields and no other text:
{
  "target_relation_correct": <true or false>,
  "target_variable_correct": <true or false>,
  "source_facts_sufficient": <true or false>,
  "equations_match_source_facts": <true or false>,
  "process_state_correct": <true or false>,
  "unit_scale_correct": <true or false>,
  "arithmetic_executable": <true or false>,
  "error_type": "none|wrong_relation|wrong_target_variable|missing_source_fact|wrong_process_state|unit_scale_error|arithmetic_error|format_error|uncertain",
  "failed_relation": "<short phrase>",
  "repair_hint": "<short phrase>",
  "confidence": <0.0 to 1.0>
}


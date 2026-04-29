# Answer-Grouped Outcome-Verifier Rerank V1

## Implemented
- Added `experiments/answer_grouped_outcome_verifier.py` with:
  - candidate/verifier/selection dataclasses;
  - verifier interface + deterministic mock verifier + Cohere verifier backend (`COHERE_API_KEY`);
  - candidate scoring, answer grouping, per-source cap, and group score aggregation;
  - tie-break logic, strict JSON-only prompt builder, and conservative parse fallback.
- Added focused tests in `tests/test_answer_grouped_outcome_verifier.py`.
- Added validation test in `tests/test_method_validation_outcome_verifier_rerank.py`.

## Inspiration
This follows Cobbe-style outcome verification ideas: verify candidate outcomes, then aggregate by normalized final answer rather than selecting a single raw trace.

## Current behavior
- DR-v2-style candidate list can be re-ranked by normalized answer groups.
- Support bonus rewards repeated independent support for same normalized answer.
- Prompt builder is strict verifier-only and excludes gold/reference answers.
- Controller emits explicit fallback metadata when no candidates are extracted or only one candidate exists (`fallback_reason`, `single_candidate_fallback`, `candidate_count`, `verifier_calls`).
- Result metadata includes both normalized and raw selected-answer fields for reporting compatibility (`selected_normalized_answer`, `ov_rerank_selected_answer`, `ov_rerank_original_dr_v2_selected_answer`).

## Not yet implemented
- No completed paired 100-case Cohere result is included in this file.

## Live runner registration status
- `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1` is live-runnable in the runtime strategy builder.
- Default verifier backend is `mock` for safety; set `DR_V2_OV_RERANK_VERIFIER_BACKEND=cohere` for live verifier calls.

## Next validation command
```bash
python -m pytest -q tests/test_answer_grouped_outcome_verifier.py
```

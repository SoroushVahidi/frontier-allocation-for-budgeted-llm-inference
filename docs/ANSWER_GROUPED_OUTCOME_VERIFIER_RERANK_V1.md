# Answer-Grouped Outcome-Verifier Rerank V1

## Implemented
- Added `experiments/answer_grouped_outcome_verifier.py` with:
  - candidate/verifier/selection dataclasses;
  - verifier interface + deterministic mock verifier;
  - candidate scoring, answer grouping, per-source cap, and group score aggregation;
  - tie-break logic and prompt builder.
- Added focused tests in `tests/test_answer_grouped_outcome_verifier.py`.

## Inspiration
This follows Cobbe-style outcome verification ideas: verify candidate outcomes, then aggregate by normalized final answer rather than selecting a single raw trace.

## Current behavior
- DR-v2-style candidate list can be re-ranked by normalized answer groups.
- Support bonus rewards repeated independent support for same normalized answer.
- Prompt builder is strict verifier-only and excludes gold/reference answers.

## Not yet implemented
- No live Cohere outcome-verifier backend is wired in this change.
- No large API evaluation run is included.

## Live runner registration status
- `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1` is currently module/test-ready.
- Full runtime registration in live strategy builders remains future integration work.

## Next validation command
```bash
python -m pytest -q tests/test_answer_grouped_outcome_verifier.py
```

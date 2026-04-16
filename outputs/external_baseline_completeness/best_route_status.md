# BEST-Route status

- Generated (UTC): `2026-04-16T01:29:17.824519+00:00`
- Baseline: `best_route_microsoft`
- Status: `runnable_adjacent`
- Integration kind: `verified_import_only`

## Conservative interpretation
- This is an **adjacent import protocol**, not an in-repo full reproduction.
- Imported artifacts must pass strict contract validation before use.

## Required import contract highlights
- Required files: `metadata.json` and `results.csv`.
- Required workflow-stage declarations:
  - mixed_prompt_construction
  - multi_sample_response_generation
  - armoRM_scoring
  - proxy_reward_model_scoring
  - router_training
- Candidate arms must encode model+best-of-n variants and include both bo1 and bo>1.
- Comparability scope must be explicitly `adjacent_only`.

## Safe vs unsafe claims
Safe now:
- Reviewer-auditable BEST-Route import/validation path exists in this repo.

Not safe now:
- Claiming direct, apples-to-apples in-repo BEST-Route reproduction.

# BEST-Route status

- Generated (UTC): `2026-04-21T04:54:56.020736+00:00`
- Baseline: `best_route_microsoft`
- Resource level: `official`
- Status: `import_validated`
- Control equivalence: `adjacent`
- Integration kind: `official_adjacent_import_validated`

## Conservative interpretation
- This is an **official adjacent import-validated** baseline lane.
- This is **not** an in-repo full BEST-Route training/eval reproduction.

## Required import contract highlights
- Config: `configs/best_route_official_import_v1.json`.
- Validator: `scripts/verify_best_route_import.py`.
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
- Reviewer-auditable, official adjacent import-validated BEST-Route path exists in this repo.

Not safe now:
- Claiming direct frontier-allocation equivalence or full paper-faithful in-repo reproduction.

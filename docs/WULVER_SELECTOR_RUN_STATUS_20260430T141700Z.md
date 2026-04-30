# Wulver Selector Run Status (2026-04-30)

## Submitted Jobs

- `1016361` (`l1_selector_verifier`) from `jobs/run_l1_defeat_selector_verifier_wulver_20260430T180856Z.sbatch`
- `1016364` (`large_selector`) from `jobs/run_large_selector_tournament_wulver_20260430T181201Z.sbatch`

## Outcomes

- `1016361`: `FAILED (1:0)`
- `1016364`: `FAILED (1:0)`

## Evidence Paths

- `logs/l1_selector_verifier_1016361.out`
- `logs/l1_selector_verifier_1016361.err`
- `logs/large_selector_1016364.out`
- `logs/large_selector_1016364.err`

## What Completed Before Failure

- `1016361` completed:
  - repo health check
  - selector tests
  - artifact scan
  - best-artifact reconstruction
  - heuristic selector stage
  - Cohere dry-run stage
- `1016364` completed:
  - repo health check
  - tournament tests
  - artifact scan
  - large artifact build entrypoint (then failed due to empty built artifact)

## Failure Details

- Cluster shell lacked `rg`, which is used in sbatch env-selection checks.
- Cohere API request path used by current verifier script returned HTTP 404 in this environment.
- Large tournament run terminated when `selector_eval_artifact/per_example_records.jsonl` was empty.

## Immediate Follow-up Needed

1. Remove `rg` dependency from sbatch scripts (use POSIX-safe checks).
2. Harden Cohere verifier request path/model handling and fallback for non-200 responses.
3. Ensure artifact-builder emits non-empty eval artifacts or exits with explicit diagnostic reason before tournament stage.
4. Resubmit both jobs after the above fixes.

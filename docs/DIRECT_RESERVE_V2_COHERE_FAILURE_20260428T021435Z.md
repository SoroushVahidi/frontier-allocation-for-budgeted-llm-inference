# Direct reserve v2 Cohere failure note (20260428T021435Z)

## Job

- Slurm job id: `1011738`
- Sbatch: `batch/run_direct_reserve_v2_cohere_20260428T021435Z.sbatch`
- Status: `FAILED` (`ExitCode=2:0`, elapsed `00:01:00`)

## Stage of failure

Failure happened in **pre-run readiness/smoke check** before case selection or scoring.

- `COHERE_API_KEY`: present
- Readiness outcome: `network_or_timeout`
- Sanitized error: `smoke test timed out after 45s`

## Dry-run prerequisite status

Dry selection completed successfully before submission:

- command mode: `--mode cohere --dry-run-selection`
- selected rows: `30`
- unique example_ids: `16`
- fallback duplicate/cycle rows: `14`

## Monitoring snapshots

- **t=0s**: job `R`; stdout/stderr files created; output dir not yet present.
- **t=30s**: job `R`; output dir present; no selected cases yet.
- **t=60s**: job no longer in `squeue`; stdout shows `cohere_mode ok=False msg=readiness:network_or_timeout`; `cohere_api_key_issue.md` present.
- **t=90s**: `sacct` reports `FAILED 2:0`; no `selected_cases.jsonl`, no `full_traces/`, no `manifest.json`, no `per_case_results.csv`.
- **t=120s**: unchanged from t=90s.

## Logs and partial outputs

- stdout: `outputs/slurm_logs/direct_reserve_v2_cohere_20260428T021435Z_1011738.out`
- stderr: `outputs/slurm_logs/direct_reserve_v2_cohere_20260428T021435Z_1011738.err` (empty)
- issue marker: `outputs/semantic_diversity_controller_diagnostic_20260428T021435Z/cohere_api_key_issue.md`
- output dir: `outputs/semantic_diversity_controller_diagnostic_20260428T021435Z/`

## Recommended fix

1. Re-run from a node/environment with reliable outbound network access for Cohere readiness.
2. Keep the same method list including `direct_reserve_semantic_frontier_v2`.
3. Do **not** resubmit blindly until readiness check succeeds interactively on the submit side.

# Repository job status (2026-04-17)

This note summarizes Slurm jobs tied to this repository that were visible in `sacct` during the 2026-04-17 triage window.

## Completed jobs

- `914297` (`heavy_real_routing_eval`): completed; final completion line present in `logs/slurm/heavy_real_routing_eval-914297.out`.
- `935481` (`branch_scorer_v3_heavy_ml`): completed.
- `935482` (`branch_scorer_v3_final_eval`): completed.
- `937459` (`branch_scorer_v3_heavy_ml`): completed after wrapper fix and resubmission.

## Failed jobs and resolution

- `914308` (`branch_scorer_v3_heavy_ml`) failed with:
  - `ValueError: invalid literal for int() with base 10: 'b10'`
  - Root cause: filename-stem parsing in the sweep pipeline expected an older split format.
  - Resolution: pipeline now uses regex stem parsing (`seed/budget/init`) in `scripts/run_branch_scorer_ml_sweep.sh`; subsequent runs complete.

- `935401` (`branch_scorer_v3_heavy_ml`) failed with:
  - `mkdir: cannot create directory 'logs': Permission denied`
  - `mkdir: cannot create directory 'outputs': Permission denied`
  - Root cause: batch launch directory (`SLURM_SUBMIT_DIR`) was not writable / not suitable for writing run artifacts.
  - Resolution: `jobs/branch_scorer_v3_heavy_ml.sbatch` now validates submit dir and falls back to `${HOME}/adaptive-reasoning-budget-allocation` when needed.
  - Resubmission: `937459` completed successfully.

## Operational note

Jobs named `evictv1-heavy-eval` appeared in `sacct` but are not tied to tracked scripts/logs in this repository snapshot, so they were excluded from this repo-specific remediation pass.

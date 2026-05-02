# Full verifier score completion on 88 external-loss cases (2026-05-02)

## Purpose

Complete missing Cohere outcome-verifier scores for the same 88-case external-loss slice used in the prior full-pipeline selector diagnostic, then rerun `outcome_verifier_answer_group_selector_v1` with `scorer_mode: cached_jsonl` so the rerun is not driven by missing-score fallbacks.

This is **diagnostic** work on a **selected external-loss subset**. It is not evidence of broad external-baseline superiority or of general selector performance.

## Previous run (job 1018219)

| Item | Value |
|------|--------|
| Output directory | `outputs/full_pipeline_best_selector_on_88_external_losses_20260502T210610Z/` |
| Evaluated cases | 88 |
| Correct / still wrong (reported) | 19 / 69 |
| `missing_score_count` (per prior summary) | 134 |
| `fallback_due_to_missing_score_count` | 81 |

Score coverage was incomplete, so many decisions used fallbacks. A **fully scored** cache is required before treating selector behavior as claim-safe on this slice.

## New score-completion job (1018248)

| Item | Value |
|------|--------|
| Slurm job ID | `1018248` |
| Batch file | `batch/run_full_score_completion_on_88_external_losses_wulver.sbatch` |
| Score-completion / preflight directory | `outputs/full_score_completion_88_external_losses_20260502T213834Z/` |
| Final rerun directory | `outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/` |
| Bounded API calls (plan) | **134** (`expected_api_calls` in `missing_score_call_plan_summary.json`) |
| Call-plan rows | **134** distinct verifier items; **81** unique cases with prior fallback (`unique_case_count`) |

### Job status at documentation time

Slurm reported **RUNNING** for job `1018248` while this documentation was prepared. **Final** `summary.json`, merge reports, and `comparison_vs_previous_run.*` under the final rerun directory were **not** present yet (only preflight artifacts and a local `run_env.log` had been written).

Re-check completion:

```bash
sacct -j 1018248 --format=JobID,State,Elapsed,ExitCode,End
```

### Success conditions (after the job finishes)

From the final rerun `summary.json`, the diagnostic should satisfy:

- `missing_score_count == 0`
- `fallback_due_to_missing_score_count == 0`
- `selected_candidate_not_in_pool_count == 0`

Inspect when available:

```bash
cat outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/summary.json
```

## Artifacts committed vs left local

Committed (small, reproducibility-focused):

- Wulver batch wrapper and Python driver: `batch/run_full_score_completion_on_88_external_losses_wulver.sbatch`, `scripts/run_full_score_completion_on_external_losses.py`
- Preflight: `missing_score_call_plan_summary.json`, `missing_score_call_plan.jsonl`, `monitor_log.jsonl`, `batch_submission_info.json`, `plan_only_stdout.json`, `sbatch_submit.txt`
- This doc and `outputs/full_score_completion_88_external_losses_20260502T213834Z/artifact_summary.md`

Not committed (by policy or size): large verifier score caches, full `per_case_results.jsonl`, secrets, and `*.log` files (e.g. `run_env.log`). Slurm `logs/slurm/full_score_completion_88_external_losses_1018248.out` was not committed to avoid shipping environment booleans about credential presence; use the JSON summaries and cluster logs locally if needed.

## Commands to inspect later

```bash
# Plan and bounds
cat outputs/full_score_completion_88_external_losses_20260502T213834Z/missing_score_call_plan_summary.json

# Final metrics (after job completes)
cat outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/summary.json
sed -n '1,120p' outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/summary_report.md

# Merge + comparison (after job completes)
cat outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/score_merge_report.json
sed -n '1,160p' outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/comparison_vs_previous_run.md
```

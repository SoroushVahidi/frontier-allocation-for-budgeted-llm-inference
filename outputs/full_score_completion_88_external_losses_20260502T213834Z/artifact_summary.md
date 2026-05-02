# Artifact summary: `full_score_completion_88_external_losses_20260502T213834Z`

## Counts (from `missing_score_call_plan_summary.json`)

| Field | Value |
|-------|--------|
| `total_missing_items_to_score` | 134 |
| `unique_case_count` | 81 |
| `expected_api_calls` | 134 |
| `items_missing_required_fields` | 0 |

## Files in this directory (committed where noted)

| File | Role |
|------|------|
| `missing_score_call_plan.jsonl` | One row per deduped verifier scoring item (committed; ~207 KB). |
| `missing_score_call_plan_summary.json` | Bounded plan metadata and input paths (committed). |
| `plan_only_stdout.json` | Captured stdout from plan-only preflight (committed). |
| `batch_submission_info.json` | Slurm job id `1018248`, batch path, output dirs (committed). |
| `sbatch_submit.txt` | Raw `sbatch` submission line / stamp (committed). |
| `monitor_log.jsonl` | Short preflight monitoring samples (committed). |

## Relation to prior diagnostic (1018219)

- **Previous selector output:** `outputs/full_pipeline_best_selector_on_88_external_losses_20260502T210610Z/`
- **Discovery records used for pools:** `outputs/cohere_real_model_cost_normalized_validation_20260502T210610Z_DISCOVERY/per_example_records.jsonl`
- **Base score cache merged in:** `outputs/outcome_verifier_scores_cohere_smoke10_20260501T162328Z/verifier_scores.jsonl` (local path may appear as `/mmfs1/.../outputs/...` on Wulver)

## Final rerun directory

Full selector rerun and merge reports (when the job finishes) are written under:

`outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/`

Large JSONL caches and per-case dumps remain **out of git** per repository `outputs/` policy unless separately whitelisted.

# Wulver submission: expanded-loss-pool Cohere diagnostic (20260428T143500Z)

## Identifiers

| Field | Value |
|--------|--------|
| Timestamp (live) | `20260428T143500Z` |
| Slurm job ID | **1011613** |
| Job name | `semdiv-exp-pool` |
| Partition (sbatch) | `debug` (see sbatch file) |

## Paths

| Artifact | Path |
|----------|------|
| sbatch script | `batch/run_semantic_diversity_expanded_pool_20260428T143500Z.sbatch` |
| Output directory | `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/` |
| Slurm stdout | `outputs/slurm_logs/semantic_diversity_expanded_pool_20260428T143500Z_1011613.out` |
| Slurm stderr | `outputs/slurm_logs/semantic_diversity_expanded_pool_20260428T143500Z_1011613.err` |
| Expected report (on completion) | `docs/SEMANTIC_DIVERSITY_CONTROLLER_DIAGNOSTIC_20260428T143500Z.md` |

## Exact Python command (inside sbatch)

```bash
python scripts/run_semantic_diversity_controller_diagnostic.py \
  --timestamp "20260428T143500Z" \
  --mode cohere \
  --run-live-cohere \
  --selection-profile expanded-loss-pool \
  --max-cases 30 \
  --allow-large-run \
  --allow-duplicate-example-fallback \
  --methods external_l1_max,strict_f3,direct_reserve_semantic_frontier_v1,semantic_minimum_maturation_plus_direct_reserve_v1 \
  --budgets 4,6,8 \
  --emit-full-traces \
  --dataset-name openai/gsm8k \
  --loss-jsonl outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/loss_cases_absent_from_tree.jsonl
```

## COHERE_API_KEY

Checked at submission time on the submit host: **present** (value never printed).

Job stdout at start on compute node also printed `COHERE_API_KEY: present`. No `cohere_api_key_issue.md` appeared in the output directory during the first 2 minutes.

## Dry-selection result (gate before submit)

See `docs/SEMANTIC_DIVERSITY_EXPANDED_POOL_DRY_SELECTION_20260428T143500Z.md`.

Summary: **189** candidates inspected, **163** rejected empty question/gold, **26** eligible rows, **16** unique eligible `example_id`s, **30** selected rows (**14** fallback duplicate/cycle rows), **≥ 20** threshold met → live run submitted.

## First 2-minute monitoring (every 30s after submission)

Snapshots: **t=0s, 30s, 60s, 90s, 120s** (UTC ~2026-04-28T00:27–00:29).

| t (s) | `squeue` | `out_dir` | `selected_cases.jsonl` | pool audits | `full_traces/` files | `cohere_api_key_issue.md` | `run_failure_issue.md` |
|------:|----------|-----------|-------------------------|-------------|----------------------|---------------------------|-------------------------|
| 0 | `R` on n0111 | no | no | no | 0 | no | no |
| 30 | `R` | yes | yes | yes | 6 | no | no |
| 60 | `R` | yes | yes | yes | 12 | no | no |
| 90 | `R` | yes | yes | yes | 19 | no | no |
| 120 | `R` | yes | yes | yes | 23 | no | no |

At each snapshot: stdout/stderr log files existed; `manifest.json` and `per_case_results.csv` were not present yet (run in progress).

**Status after 120s:** job **still running** (`ST=R`, ~2:14 elapsed on n0111). Traces growing normally; no readiness or runtime issue markers in the monitored window.

## How to check later

```bash
squeue -j 1011613
sacct -j 1011613 --format=JobID,State,Elapsed,ExitCode
tail -f outputs/slurm_logs/semantic_diversity_expanded_pool_20260428T143500Z_1011613.out
```

## Expected outputs (on completion)

Under `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z/`, including `selected_cases.jsonl`, `selected_case_pool_audit.csv`, `case_pool_expansion_audit.csv`, `per_case_results.csv`, paired and method summaries, `manifest.json`, `full_traces/`, and issue markdown only if applicable.

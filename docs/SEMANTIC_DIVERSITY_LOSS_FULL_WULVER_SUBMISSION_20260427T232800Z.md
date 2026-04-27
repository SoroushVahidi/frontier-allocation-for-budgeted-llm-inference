# Wulver submission: Cohere loss-full trace-complete diagnostic (20260427T232800Z)

## sbatch

- **File:** `batch/run_semantic_diversity_loss_full_20260427T232800Z.sbatch`
- **Job ID:** `1011561`
- **Job name:** `semdiv-loss-full`
- **Partition / QOS:** `debug` / `debug`
- **Resources:** 1 task, 4 CPUs, 16G, wall time 06:00:00

## Python command (repo root)

```bash
python scripts/run_semantic_diversity_controller_diagnostic.py \
  --timestamp 20260427T232800Z \
  --mode cohere \
  --run-live-cohere \
  --max-cases 30 \
  --allow-large-run \
  --selection-profile loss-full \
  --budgets 4,6,8 \
  --emit-full-traces \
  --dataset-name openai/gsm8k
```

- **Case source (default in runner):** `outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/loss_cases_absent_from_tree.jsonl`
- **Methods:** default for `loss-full` — `external_l1_max`, `strict_f3`, `semantic_minimum_maturation_frontier_v1_d3`, `direct_reserve_semantic_frontier_v1`, `branching_necessity_gate_v1`, `semantic_minimum_maturation_plus_direct_reserve_v1` (excludes `semantic_minimum_maturation_frontier_v1_d2`).

## Outputs (timestamped)

- **Run directory:** `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z/`
- **Diagnostic report:** `docs/SEMANTIC_DIVERSITY_CONTROLLER_DIAGNOSTIC_20260427T232800Z.md` (written when the runner finishes successfully)

### Slurm logs

- **stdout:** `outputs/slurm_logs/semantic_diversity_loss_full_20260427T232800Z_1011561.out`
- **stderr:** `outputs/slurm_logs/semantic_diversity_loss_full_20260427T232800Z_1011561.err`

## COHERE_API_KEY

- Batch script prints only `COHERE_API_KEY: present` or `absent` and aborts if absent.
- Submit environment had the key available for this job (see stdout header).

## Cohere readiness in logs

- Readiness runs inside the Python process via `run_readiness_check` (prints `smoke_test: success` on success). Slurm stdout may be block-buffered; within the first two minutes the log file did not yet show those lines.
- **Indirect evidence readiness passed:** `selected_cases.jsonl` was created under the output directory, `full_traces/` appeared with multiple JSON files, and neither `cohere_api_key_issue.md` nor `run_failure_issue.md` was present during monitoring.

## First 2-minute monitoring (job 1011561)

| Time | squeue | out_dir | selected_cases.jsonl | per_case_results.csv | manifest.json | full_traces | issue files |
|------|--------|---------|----------------------|----------------------|---------------|-------------|-------------|
| ~0s | R | no | no | no | no | — | none |
| ~30s | R | yes | yes | no | no | — | none |
| ~60s | R | yes | yes | no | no | — | none |
| ~90s | R | yes | yes | no | no | dir exists | none |
| ~120s | R (~2:01) | yes | yes | no | no | ~22 JSON files | none |

**Status after 120 seconds:** job **still running** (`ST=R`). Final CSVs and `manifest.json` are written at the end of the run.

## Check later

```bash
squeue -j 1011561
sacct -j 1011561 --format=JobID,State,ExitCode,Elapsed,MaxRSS
tail -f outputs/slurm_logs/semantic_diversity_loss_full_20260427T232800Z_1011561.out
```

## Expected artifacts (when complete)

- `selected_cases.jsonl`, `per_case_results.csv`, `paired_summary.csv`, `method_accuracy_summary.csv`, `token_cost_latency_summary.csv`, `semantic_family_summary.csv`, `maturation_phase_audit.csv`, `branching_necessity_audit.csv`, `incumbent_replacement_audit.csv`, `absent_from_tree_rescue_audit.csv`, `failure_taxonomy.csv`, `candidate_next_steps.md`, `manifest.json`, `full_traces/`, optional `run_failure_issue.md` / `cohere_api_key_issue.md` on failure paths.

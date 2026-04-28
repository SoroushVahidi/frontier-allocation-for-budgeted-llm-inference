# Direct reserve v2 Cohere Wulver submission (20260428T_DR_V2_LONG)

## Submission metadata

- Timestamp: `20260428T_DR_V2_LONG`
- Sbatch path: `batch/run_direct_reserve_v2_cohere_20260428T_DR_V2_LONG.sbatch`
- Job id: `1011746`
- Output directory: `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/`
- Stdout log: `outputs/slurm_logs/direct_reserve_v2_cohere_20260428T_DR_V2_LONG_1011746.out`
- Stderr log: `outputs/slurm_logs/direct_reserve_v2_cohere_20260428T_DR_V2_LONG_1011746.err`

## Exact Python command inside sbatch

```bash
python scripts/run_semantic_diversity_controller_diagnostic.py \
  --timestamp 20260428T_DR_V2_LONG \
  --mode cohere \
  --run-live-cohere \
  --selection-profile expanded-loss-pool \
  --max-cases 30 \
  --allow-large-run \
  --allow-duplicate-example-fallback \
  --methods external_l1_max,strict_f3,direct_reserve_semantic_frontier_v1,direct_reserve_semantic_frontier_v2,semantic_minimum_maturation_plus_direct_reserve_v1 \
  --budgets 4,6,8 \
  --emit-full-traces \
  --dataset-name openai/gsm8k \
  --loss-jsonl outputs/cohere_absent_from_tree_loss_diagnostics_20260427T171917Z/loss_cases_absent_from_tree.jsonl
```

## Dry-run validation

- Dry timestamp: `20260428T_DR_V2_DRY`
- Result: success (`dry_selection_exit_code=0`)
- Selection summary: `selected_rows=30`, `unique_example_ids_selected=16`, `n_fallback_duplicate_or_cycle_rows=14`

## COHERE_API_KEY status

- `COHERE_API_KEY: present`

## Mandatory 2-minute monitoring snapshots

### t=0s
- `squeue`: `R` on `n0111` (runtime `0:06`)
- stdout exists: yes
- stderr exists: yes
- output dir exists: no
- `selected_cases.jsonl`: no
- `selected_case_pool_audit.csv`: no
- `case_pool_expansion_audit.csv`: no
- `full_traces/`: no (`count=0`)
- `cohere_api_key_issue.md`: no
- `run_failure_issue.md`: no
- `manifest.json`: no
- `per_case_results.csv`: no

### t=30s
- `squeue`: `R` on `n0111` (runtime `0:48`)
- stdout exists: yes
- stderr exists: yes
- output dir exists: yes
- `selected_cases.jsonl`: yes
- `selected_case_pool_audit.csv`: yes
- `case_pool_expansion_audit.csv`: yes
- `full_traces/`: yes (`count=4`)
- `cohere_api_key_issue.md`: no
- `run_failure_issue.md`: no
- `manifest.json`: no
- `per_case_results.csv`: no

### t=60s
- `squeue`: `R` on `n0111` (runtime `1:28`)
- stdout exists: yes
- stderr exists: yes
- output dir exists: yes
- `selected_cases.jsonl`: yes
- `selected_case_pool_audit.csv`: yes
- `case_pool_expansion_audit.csv`: yes
- `full_traces/`: yes (`count=9`, growing)
- `cohere_api_key_issue.md`: no
- `run_failure_issue.md`: no
- `manifest.json`: no
- `per_case_results.csv`: no

### t=90s
- `squeue`: `R` on `n0111` (runtime `2:13`)
- stdout exists: yes
- stderr exists: yes
- output dir exists: yes
- `selected_cases.jsonl`: yes
- `selected_case_pool_audit.csv`: yes
- `case_pool_expansion_audit.csv`: yes
- `full_traces/`: yes (`count=11`, growing)
- `cohere_api_key_issue.md`: no
- `run_failure_issue.md`: no
- `manifest.json`: no
- `per_case_results.csv`: no

### t=120s
- `squeue`: `R` on `n0111` (runtime `2:56`)
- stdout exists: yes
- stderr exists: yes
- output dir exists: yes
- `selected_cases.jsonl`: yes
- `selected_case_pool_audit.csv`: yes
- `case_pool_expansion_audit.csv`: yes
- `full_traces/`: yes (`count=19`, growing)
- `cohere_api_key_issue.md`: no
- `run_failure_issue.md`: no
- `manifest.json`: no
- `per_case_results.csv`: no

## Status after 120s

Job is running normally with trace generation and no readiness/runtime issue markers in the first 2 minutes.

## How to check later

```bash
squeue -j 1011746
sacct -j 1011746 --format=JobID,State,ExitCode,Elapsed,MaxRSS
```

## Expected output files on completion

- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/selected_cases.jsonl`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/selected_case_pool_audit.csv`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/case_pool_expansion_audit.csv`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/per_case_results.csv`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/method_accuracy_summary.csv`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/paired_summary.csv`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/failure_taxonomy.csv`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/rescue_case_table.csv`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/token_cost_latency_summary.csv`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/manifest.json`
- `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG/full_traces/`

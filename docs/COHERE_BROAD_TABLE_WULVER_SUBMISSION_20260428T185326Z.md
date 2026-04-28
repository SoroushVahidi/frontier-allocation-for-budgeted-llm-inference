# Cohere broad accuracy/cost table Wulver submission (20260428T185326Z)

- Timestamp: `20260428T185326Z`
- Sbatch path: `batch/run_cohere_broad_accuracy_cost_table_20260428T185326Z.sbatch`
- Job id: `1013242`
- Current status after 3-minute monitoring: **running**

## Exact command

```bash
python scripts/run_semantic_diversity_controller_diagnostic.py \
  --timestamp 20260428T185326Z \
  --mode cohere \
  --run-live-cohere \
  --selection-profile expanded-loss-pool \
  --max-cases 30 \
  --allow-large-run \
  --allow-duplicate-example-fallback \
  --methods direct_reserve_semantic_frontier_v2,strict_f3,external_l1_max,external_l1_exact,self_consistency_3,tot_bfs_matched_budget,tot_beam_matched_budget,tot_dfs_matched_budget \
  --budgets 4,6,8 \
  --emit-full-traces \
  --dataset-name openai/gsm8k \
  --loss-jsonl outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/loss_cases_absent_from_tree.jsonl
```

## Resolved loss pool

- `outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/loss_cases_absent_from_tree.jsonl`

## Methods

- Included: `direct_reserve_semantic_frontier_v2`, `strict_f3`, `external_l1_max`, `external_l1_exact`, `self_consistency_3`, `tot_bfs_matched_budget`, `tot_beam_matched_budget`, `tot_dfs_matched_budget`
- Excluded (unavailable/non-registered in current Cohere diagnostic registry): `direct_reserve_semantic_frontier_v2_thresholded_ordered`
- Excluded (implemented elsewhere but not enabled by this runner's `_build_specs_for_budget()` flags): `s1`, `external_s1_budget_forcing`, `tale`, `external_tale_prompt_budgeting`

## Dry selection summary

- candidates inspected: `204`
- eligible rows: `41`
- selected rows: `30`
- unique example IDs: `16`
- duplicate fallback rows: `14`
- selected rows >= 20 gate: **passed**

## Output and log paths

- Stdout log: `outputs/slurm_logs/cohere_broad_accuracy_cost_table_20260428T185326Z_1013242.out`
- Stderr log: `outputs/slurm_logs/cohere_broad_accuracy_cost_table_20260428T185326Z_1013242.err`
- Output dir: `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z`

## 3-minute monitoring snapshots

### t=0
- squeue: `R` on `n0052`
- stdout exists: yes
- stderr exists: yes
- output dir exists: no
- selected_cases.jsonl: no
- selected_case_pool_audit.csv: no
- case_pool_expansion_audit.csv: no
- full_traces/: no (`0` files)
- cohere_api_key_issue.md: no
- run_failure_issue.md: no
- manifest.json: no
- per_case_results.csv: no
- stdout tail: startup header + `COHERE_API_KEY: present`
- stderr tail: empty

### t=30
- squeue: `R`
- stdout exists: yes
- stderr exists: yes
- output dir exists: yes
- selected_cases.jsonl: yes
- selected_case_pool_audit.csv: yes
- case_pool_expansion_audit.csv: yes
- full_traces/: yes (`6` files)
- cohere_api_key_issue.md: no
- run_failure_issue.md: no
- manifest.json: no
- per_case_results.csv: no
- stdout tail: startup header + `COHERE_API_KEY: present`
- stderr tail: empty

### t=60
- squeue: `R`
- stdout exists: yes
- stderr exists: yes
- output dir exists: yes
- selected_cases.jsonl: yes
- selected_case_pool_audit.csv: yes
- case_pool_expansion_audit.csv: yes
- full_traces/: yes (`13` files)
- cohere_api_key_issue.md: no
- run_failure_issue.md: no
- manifest.json: no
- per_case_results.csv: no
- stdout tail: startup header + `COHERE_API_KEY: present`
- stderr tail: empty

### t=90
- squeue: `R`
- stdout exists: yes
- stderr exists: yes
- output dir exists: yes
- selected_cases.jsonl: yes
- selected_case_pool_audit.csv: yes
- case_pool_expansion_audit.csv: yes
- full_traces/: yes (`20` files)
- cohere_api_key_issue.md: no
- run_failure_issue.md: no
- manifest.json: no
- per_case_results.csv: no
- stdout tail: startup header + `COHERE_API_KEY: present`
- stderr tail: empty

### t=120
- squeue: `R`
- stdout exists: yes
- stderr exists: yes
- output dir exists: yes
- selected_cases.jsonl: yes
- selected_case_pool_audit.csv: yes
- case_pool_expansion_audit.csv: yes
- full_traces/: yes (`29` files)
- cohere_api_key_issue.md: no
- run_failure_issue.md: no
- manifest.json: no
- per_case_results.csv: no
- stdout tail: startup header + `COHERE_API_KEY: present`
- stderr tail: empty

### t=150
- squeue: `R`
- stdout exists: yes
- stderr exists: yes
- output dir exists: yes
- selected_cases.jsonl: yes
- selected_case_pool_audit.csv: yes
- case_pool_expansion_audit.csv: yes
- full_traces/: yes (`43` files)
- cohere_api_key_issue.md: no
- run_failure_issue.md: no
- manifest.json: no
- per_case_results.csv: no
- stdout tail: startup header + `COHERE_API_KEY: present`
- stderr tail: empty

### t=180
- squeue: `R`
- stdout exists: yes
- stderr exists: yes
- output dir exists: yes
- selected_cases.jsonl: yes
- selected_case_pool_audit.csv: yes
- case_pool_expansion_audit.csv: yes
- full_traces/: yes (`52` files)
- cohere_api_key_issue.md: no
- run_failure_issue.md: no
- manifest.json: no
- per_case_results.csv: no
- stdout tail: startup header + `COHERE_API_KEY: present`
- stderr tail: empty

## How to check later

```bash
squeue -j 1013242
sacct -j 1013242 --format=JobID,State,ExitCode,Elapsed,MaxRSS
```

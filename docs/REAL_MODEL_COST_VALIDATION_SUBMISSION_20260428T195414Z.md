# Real-model cost validation submission (20260428T195414Z)

- Timestamp: `20260428T195414Z`
- Sbatch path: `batch/run_real_model_cost_validation_20260428T195414Z.sbatch`
- Job id: `1013340`
- Current status: `RUNNING`

## Exact command (inside batch)

```bash
python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp 20260428T195414Z \
  --providers cohere \
  --cohere-model command-r-plus-08-2024 \
  --datasets openai/gsm8k,HuggingFaceH4/MATH-500 \
  --budgets 4,6,8 \
  --seeds 11,23 \
  --methods strict_f3,strict_gate1_cap_k6,strict_f3_anti_collapse_weak_v1,external_l1_max,tale,s1 \
  --target-scored-per-slice 30 \
  --max-examples 30 \
  --resume
```

## Dry-check run

- Ran summarize-only dry check before submission:
  - `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260428T195414Z_DRYCHECK --providers cohere --cohere-model command-r-plus-08-2024 --datasets openai/gsm8k,HuggingFaceH4/MATH-500 --budgets 4,6,8 --seeds 11,23 --methods strict_f3,strict_gate1_cap_k6,strict_f3_anti_collapse_weak_v1,external_l1_max,tale,s1 --target-scored-per-slice 30 --max-examples 30 --summarize-only`
  - Exit code: `0`

## Output and logs

- Primary output dir (runner): `outputs/cohere_real_model_cost_normalized_validation_20260428T195414Z/`
- Reviewer alias output dir: `outputs/real_model_cost_validation_20260428T195414Z/`
- Stdout log: `outputs/slurm_logs/real_model_cost_validation_20260428T195414Z_1013340.out`
- Stderr log: `outputs/slurm_logs/real_model_cost_validation_20260428T195414Z_1013340.err`

## Expected outputs

- `per_case_results.csv`
- `method_summary.csv`
- `paired_vs_external_l1_max.csv`
- `token_latency_cost_summary.csv`
- `failure_decomposition.csv`
- `run_manifest.json`
- (plus upstream runner artifacts: `slice_summary.csv`, `pairwise_comparisons.csv`, `claim_safety_table.csv`, `manifest.json`, `per_example_records.jsonl`)

## Initial monitoring snapshot

- `squeue -j 1013340`: running on `general`
- `sacct -j 1013340 --format=JobID,State,ExitCode,Elapsed,MaxRSS`: `RUNNING`
- Stdout includes:
  - batch header,
  - git commit hash,
  - python version,
  - key presence booleans (`OPENAI_API_KEY`, `COHERE_API_KEY`, `HF_TOKEN`).
- Stderr currently empty.

## How to check status

```bash
squeue -j 1013340
sacct -j 1013340 --format=JobID,State,ExitCode,Elapsed,MaxRSS
```

## Scope note

This run is supporting/diagnostic real-model cost-aware validation and is not automatically promoted to headline manuscript evidence without explicit canonical decision-doc promotion.

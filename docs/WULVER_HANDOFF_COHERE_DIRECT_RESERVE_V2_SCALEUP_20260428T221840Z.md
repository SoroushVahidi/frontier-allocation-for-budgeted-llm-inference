# Wulver Handoff: Cohere DR-v2 vs external_l1_max Scale-up (2026-04-28)

## Purpose
Run a controlled, paired, cost-aware Cohere scale-up to compare:
- `direct_reserve_semantic_frontier_v2`
- `external_l1_max`
- `strict_f3`
- `strict_gate1_cap_k6`
- `strict_f3_anti_collapse_weak_v1`
- `tale`
- `s1`

across budgets `4,6,8`, seeds `11,23`, and datasets `openai/gsm8k,HuggingFaceH4/MATH-500`.

## Batch file
`batch/run_cohere_direct_reserve_v2_vs_external_l1_scaleup_20260428T221840Z.sbatch`

## Manual submit command (run on Wulver)
```bash
sbatch batch/run_cohere_direct_reserve_v2_vs_external_l1_scaleup_20260428T221840Z.sbatch
```

## Expected outputs
Primary timestamped output directory (created by batch script):
- `outputs/cohere_direct_reserve_v2_vs_external_l1_scaleup_<TS>/`

Upstream runner directory (also timestamped):
- `outputs/cohere_real_model_cost_normalized_validation_<TS>/`

Expected files in final handoff directory:
- `manifest.json`
- `per_case_results.csv`
- `method_summary.csv`
- `unique_example_method_summary.csv`
- `paired_vs_external_l1_max.csv`
- `paired_vs_best_external.csv`
- `token_latency_cost_summary.csv`
- `cost_normalized_leaderboard.csv`
- `coverage_gap_report.csv`
- `methods_excluded.csv`
- `run_status.json`

## Logs
Configured log paths:
- stdout: `outputs/slurm_logs/cohere_direct_reserve_v2_vs_external_l1_scaleup_<JOB_ID>.out`
- stderr: `outputs/slurm_logs/cohere_direct_reserve_v2_vs_external_l1_scaleup_<JOB_ID>.err`

If you only have the job ID, locate logs with:
```bash
ls -1 outputs/slurm_logs/*cohere_direct_reserve_v2_vs_external_l1_scaleup*<JOB_ID>*
```

## Required environment variables
Set and export before submission (never print secret values):
- `COHERE_API_KEY`
- `HF_TOKEN`

## Pre-submit checks
```bash
git status --short
git rev-parse --short HEAD
python - <<'PY'
import os
print('COHERE_API_KEY_present', bool(os.getenv('COHERE_API_KEY')))
print('HF_TOKEN_present', bool(os.getenv('HF_TOKEN')))
PY
sed -n '1,220p' batch/run_cohere_direct_reserve_v2_vs_external_l1_scaleup_20260428T221840Z.sbatch
```

Optional local handoff validator:
```bash
python scripts/validate_cohere_scaleup_handoff.py
```

## Monitoring commands
After `sbatch` returns `<JOB_ID>`:
```bash
squeue -j <JOB_ID>
sacct -j <JOB_ID> --format=JobID,State,ExitCode,Elapsed,MaxRSS
tail -n 80 outputs/slurm_logs/cohere_direct_reserve_v2_vs_external_l1_scaleup_<JOB_ID>.out
tail -n 80 outputs/slurm_logs/cohere_direct_reserve_v2_vs_external_l1_scaleup_<JOB_ID>.err
```

## Immediate-failure triage
1. **Environment activation failure**
   - Symptom: `python: command not found` or missing deps.
   - Action: ensure expected venv/conda activation path on Wulver is correct; update sbatch activation lines.

2. **Missing API key**
   - Symptom: readiness check fails early with missing/unauthorized key.
   - Action: export `COHERE_API_KEY` for your job shell; re-submit.

3. **Hugging Face access issue**
   - Symptom: dataset load/auth failure for gated datasets.
   - Action: ensure `HF_TOKEN` is exported and valid; run a small `datasets` load check on Wulver login node.

4. **Method alias/runtime issue**
   - Symptom: method skipped/excluded unexpectedly.
   - Action: verify alias map in `scripts/run_cohere_real_model_cost_normalized_validation.py` contains:
     - `direct_reserve_semantic_frontier_v1 -> direct_reserve_frontier_gate_v1`
     - `direct_reserve_semantic_frontier_v2 -> direct_reserve_frontier_gate_v2`

5. **Timeout**
   - Symptom: Slurm `TIMEOUT` state.
   - Action: increase `#SBATCH --time` and re-submit, or reduce `TARGET/MAXE` from 100 to 50 with rationale.

6. **Quota/rate limit**
   - Symptom: repeated 429 / quota errors in stderr and run artifacts.
   - Action: reduce concurrency pressure (already single task), reduce cap to 50, or retry in lower-load window.

7. **Output-path issue**
   - Symptom: missing expected files / `cp` failures.
   - Action: inspect `outputs/cohere_real_model_cost_normalized_validation_<TS>/` first; if present, rerun postprocess and copy steps manually.

## Status discipline
This package is prepared for **manual Wulver submission**. It does **not** claim that a Wulver job has already been submitted or completed.

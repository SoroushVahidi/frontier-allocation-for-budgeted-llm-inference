# Wulver batch workflow — comparative frontier audit (new-paper track)

This workflow runs the **matched-budget comparative frontier audit** (same datasets, budgets, and single API backend for all eight in-repo controller families) without an interactive session.

## Main entry point

| Piece | Role |
|--------|------|
| **`scripts/run_comparative_frontier_audit.py`** | Core audit: writes `method_metrics.csv`, `comparison_summary.csv`, `oracle_gap_summary.csv`, `main_drawbacks_report.md`, `run_manifest.json` under `outputs/comparative_frontier_audit/<run_id>/`. |
| **`scripts/wulver_comparative_frontier_audit.sh`** | Wulver-friendly wrapper: optional conda/bashrc, sources `.env`, **requires** API keys (no silent simulator fallback), writes a small **launch meta JSON** beside outputs, logs the exact CLI to `outputs/comparative_frontier_audit/wulver_last_batch.log`. |
| **`jobs/comparative_frontier_audit_wulver.sbatch`** | Slurm driver: moderate **4 h / 4 CPU / 16 GB** request; calls the shell wrapper. |

## Default first-cluster scale (moderate)

- **Datasets:** GSM8K + MATH mirror (`openai/gsm8k`, `EleutherAI/hendrycks_math`). GPQA is **not** included by default (gated / variable latency).
- **Budgets:** `8,10`
- **Subset size:** `14` examples per dataset (eval-only, full slice for matched comparison)
- **Backend:** `openai` + `gpt-4.1-mini` (override with env vars below)

Increase scale later with `COMPARATIVE_AUDIT_SUBSET_SIZE`, `COMPARATIVE_AUDIT_BUDGETS`, or longer `#SBATCH --time`.

## Prerequisites

1. Repo-root **`.env`** with the key for your chosen backend (`OPENAI_API_KEY` for default `openai`; `GROQ_API_KEY` or `GOOGLE_API_KEY` / `GEMINI_API_KEY` if you switch backend).
2. **Python** with repo `requirements.txt` / your conda env (edit `wulver_comparative_frontier_audit.sh` to `conda activate <env>` if needed).
3. **Hugging Face** dataset access for MATH mirror (same as local runs).

## Submit on Wulver

From the repository root (so `SLURM_SUBMIT_DIR` is the repo):

```bash
cd /path/to/adaptive-reasoning-budget-allocation
mkdir -p logs/slurm
sbatch jobs/comparative_frontier_audit_wulver.sbatch
```

Optional overrides (export before `sbatch`, or use `#SBATCH --export=ALL` and set on login node):

```bash
export COMPARATIVE_AUDIT_SUBSET_SIZE=20
export COMPARATIVE_AUDIT_BUDGETS=8,10,12
export COMPARATIVE_AUDIT_MODEL=gpt-4.1-mini
sbatch jobs/comparative_frontier_audit_wulver.sbatch
```

## Inspect queue and logs

```bash
squeue -u "$USER"
# or
sacct -j <JOBID> --format=JobID,State,Elapsed,MaxRSS

tail -f logs/slurm/frontier_audit_api-<JOBID>.out
```

## Where outputs go

- **Per-run artifacts:** `outputs/comparative_frontier_audit/<run_id>/` (timestamped folder created by the Python runner).
- **Launch metadata (no secrets):** `outputs/comparative_frontier_audit/wulver_launch_${SLURM_JOB_ID}_<stamp>.json`
- **Append-only batch echo:** `outputs/comparative_frontier_audit/wulver_last_batch.log`
- **Slurm stdout/stderr:** `logs/slurm/frontier_audit_api-<jobid>.out` / `.err`

`run_manifest.json` inside each `<run_id>/` includes `slurm_job_id` when the job runs under Slurm.

## Editing for your site

- **`jobs/comparative_frontier_audit_wulver.sbatch`:** `#SBATCH --partition`, `--qos`, `--account` (if required), `--mem`, `--time`.
- **`scripts/wulver_comparative_frontier_audit.sh`:** `module load …`, `conda activate …`, `COMPARATIVE_AUDIT_CONDA_ENV`.

## Honesty

- This is **not** a giant benchmark sweep; defaults favor a **first serious API-backed** run that fits a few-hour allocation.
- Runtime is dominated by **sequential LLM calls** per method × example × budget; scaling up requires longer `#SBATCH --time` and rate-limit awareness.

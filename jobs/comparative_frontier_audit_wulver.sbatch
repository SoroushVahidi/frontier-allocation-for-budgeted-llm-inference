#!/bin/bash
#SBATCH --job-name=frontier_audit_api
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err
#
# New-paper track: matched-budget comparative frontier audit (API-backed).
# Submit from repository root so SLURM_SUBMIT_DIR resolves correctly:
#   cd /path/to/adaptive-reasoning-budget-allocation
#   sbatch jobs/comparative_frontier_audit_wulver.sbatch
#
# Edit partition/qos/account/mem/time to match your Wulver allocation.
# Optional env vars (same shell as sbatch, or use #SBATCH --export=ALL):
#   COMPARATIVE_AUDIT_API_BACKEND   openai (default) | groq | gemini
#   COMPARATIVE_AUDIT_MODEL         default gpt-4.1-mini (use Groq/Gemini model id if switching backend)
#   COMPARATIVE_AUDIT_SUBSET_SIZE   default 14
#   COMPARATIVE_AUDIT_BUDGETS       default 8,10
#   COMPARATIVE_AUDIT_DATASETS      default openai/gsm8k,EleutherAI/hendrycks_math
#   COMPARATIVE_AUDIT_CONDA_ENV     conda env name if not using base

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "${REPO_ROOT}"

mkdir -p logs/slurm

bash scripts/wulver_comparative_frontier_audit.sh

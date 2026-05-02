#!/bin/bash
#SBATCH --job-name=main3-vs-best3-100
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=10:00:00
#SBATCH --output=logs/slurm/main3_vs_best3_100_%j.out
#SBATCH --error=logs/slurm/main3_vs_best3_100_%j.err

set -euo pipefail

REPO_ROOT="/home/sv96/adaptive-reasoning-budget-allocation"
cd "$REPO_ROOT"

mkdir -p logs/slurm outputs

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTDIR="outputs/main3_external_vs_best3_internal_100case_${STAMP}"
mkdir -p "${OUTDIR}"

if [ -f "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh" ]; then
  # shellcheck disable=SC1091
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh
fi
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

{
  echo "start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hostname=$(hostname)"
  echo "slurm_job_id=${SLURM_JOB_ID:-unknown}"
  echo "git_commit=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "python=$(command -v python || true)"
  python -V || true
  echo "COHERE_API_KEY present: $( [ -n \"${COHERE_API_KEY:-}\" ] && echo true || echo false )"
  echo "OPENAI_API_KEY present: $( [ -n \"${OPENAI_API_KEY:-}\" ] && echo true || echo false )"
} | tee "${OUTDIR}/run_env.log"

python scripts/run_main3_external_vs_best3_internal_100case.py \
  --timestamp "${STAMP}" \
  --budget 6 \
  --seed 20260501 \
  --target-cases 100 \
  --max-examples 100 \
  --cohere-model command-a-03-2025 \
  --output-root outputs \
  2>&1 | tee "${OUTDIR}/runner_stdout_stderr.log"

echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "${OUTDIR}/run_env.log"
echo "output_dir=${OUTDIR}" | tee -a "${OUTDIR}/run_env.log"

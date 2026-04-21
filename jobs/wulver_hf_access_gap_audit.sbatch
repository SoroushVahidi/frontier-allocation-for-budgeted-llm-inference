#!/bin/bash
#SBATCH --job-name=hf_gap_audit
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "${REPO_ROOT}"
mkdir -p logs/slurm

if [[ -f "${HOME}/.bashrc" ]]; then
  source "${HOME}/.bashrc" || true
fi
if command -v conda >/dev/null 2>&1; then
  conda activate "${WULVER_CONDA_ENV:-base}" >/dev/null 2>&1 || true
fi

python scripts/build_hf_access_gap_audit.py

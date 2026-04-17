#!/usr/bin/env bash
#SBATCH --job-name=branch_scorer_v3_heavy_ml
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

set -euo pipefail

# Prefer submit dir only when it looks like the repo root and is writable.
SUBMIT_DIR="${SLURM_SUBMIT_DIR:-}"
DEFAULT_REPO_ROOT="${HOME}/adaptive-reasoning-budget-allocation"
if [[ -n "${SUBMIT_DIR}" && -d "${SUBMIT_DIR}/scripts" && -w "${SUBMIT_DIR}" ]]; then
  REPO_ROOT="${SUBMIT_DIR}"
else
  REPO_ROOT="${DEFAULT_REPO_ROOT}"
fi

if [[ ! -d "${REPO_ROOT}/scripts" ]]; then
  echo "ERROR: Could not locate repository root with scripts/ directory." >&2
  echo "Checked REPO_ROOT='${REPO_ROOT}' (from SLURM_SUBMIT_DIR='${SUBMIT_DIR}')." >&2
  exit 2
fi

cd "${REPO_ROOT}"

mkdir -p logs/slurm outputs/branch_scorer_v3_heavy_ml

if [[ -f "$HOME/.bashrc" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.bashrc"
fi

if command -v conda >/dev/null 2>&1; then
  conda activate base >/dev/null 2>&1 || true
fi

bash scripts/run_branch_scorer_ml_sweep.sh

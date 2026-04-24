#!/usr/bin/env bash
#SBATCH --job-name=heavy_real_routing_eval
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=48:00:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

set -euo pipefail

REPO_DIR="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_DIR"

mkdir -p logs/slurm outputs/real_model_fixed_budget_heavy

if [[ -f "$HOME/.bashrc" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.bashrc"
fi

if command -v conda >/dev/null 2>&1; then
  conda activate base >/dev/null 2>&1 || true
fi

# Export everything loaded by .env into child processes.
if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

bash scripts/run_heavy_real_routing_eval.sh

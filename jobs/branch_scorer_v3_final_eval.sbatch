#!/usr/bin/env bash
#SBATCH --job-name=branch_scorer_v3_final_eval
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

mkdir -p logs/slurm outputs/branch_scorer_v3_final_eval

if [[ -f "$HOME/.bashrc" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.bashrc"
fi

if command -v conda >/dev/null 2>&1; then
  conda activate base >/dev/null 2>&1 || true
fi

bash scripts/run_final_manuscript_eval.sh

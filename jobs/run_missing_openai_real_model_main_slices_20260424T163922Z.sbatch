#!/bin/bash
#SBATCH --job-name=openai-real-main-missing
#SBATCH --partition=debug
#SBATCH --qos=debug
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

set -euo pipefail
REPO_DIR="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_DIR"
mkdir -p logs/slurm
if [[ -f /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh ]]; then
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh || true
  conda activate base >/dev/null 2>&1 || true
fi
if [[ -f "$HOME/.bashrc" ]]; then
  source "$HOME/.bashrc" || true
fi
echo "OPENAI_API_KEY present: $( [[ -n "${OPENAI_API_KEY:-}" ]] && echo true || echo false )"
if [[ -z "${OPENAI_API_KEY:-}" ]]; then echo "Missing OPENAI_API_KEY"; exit 1; fi
echo "python: $(command -v python3 || true)"
python3 --version || true

echo "Running slice: dataset=openai/gsm8k seed=23 budget=8"
python3 scripts/run_canonical_real_model_validation.py --timestamp 20260424T_OPENAI_REAL_MAIN_PATCH_20260424T163922Z_openai_23_8_openai_gsm8k --provider openai --model gpt-4.1-mini --datasets openai/gsm8k --subset-size 20 --seeds 23 --budgets 8 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3


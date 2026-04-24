#!/bin/bash
#SBATCH --job-name=held_out_claim_safety
#SBATCH --output=logs/slurm/held_out_claim_safety_%j.out
#SBATCH --error=logs/slurm/held_out_claim_safety_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --partition=cpu

set -euo pipefail

cd /workspace/adaptive-reasoning-budget-allocation
mkdir -p logs/slurm

# Load standard repo python environment (adjust on cluster if env name differs).
if command -v conda >/dev/null 2>&1; then
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate base || true
fi

python --version

HF_PRESENT=false
if [[ -n "${HF_TOKEN:-}" ]]; then
  HF_PRESENT=true
fi
echo "HF_TOKEN_PRESENT=${HF_PRESENT}"

# Explicitly avoid paid LLM providers.
unset OPENAI_API_KEY || true
unset COHERE_API_KEY || true
unset GROQ_API_KEY || true
unset GEMINI_API_KEY || true
unset GOOGLE_API_KEY || true

TS="20260424T231500Z"
python scripts/run_held_out_surface_generalization_claim_safety.py \
  --timestamp "${TS}" \
  --datasets "Idavidrein/gpqa,Hothan/OlympiadBench,livecodebench/execution-v2" \
  --subset-size 50 \
  --seeds 11,23,37 \
  --budgets 4,6,8

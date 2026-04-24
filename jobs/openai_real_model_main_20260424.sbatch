#!/usr/bin/env bash
#SBATCH --job-name=openai-real-main
#SBATCH --partition=debug
#SBATCH --qos=debug
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=logs/slurm/openai_real_main_%j.out
#SBATCH --error=logs/slurm/openai_real_main_%j.err

set -euo pipefail

REPO_DIR="/home/sv96/adaptive-reasoning-budget-allocation"
cd "$REPO_DIR"

mkdir -p logs/slurm
export PYTHONUNBUFFERED=1

if [[ -f "$HOME/.bashrc" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.bashrc"
fi

# Prefer already active virtualenv; otherwise try common local env options.
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  echo "Using active virtualenv: $VIRTUAL_ENV"
elif [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
  echo "Activated .venv"
elif command -v conda >/dev/null 2>&1; then
  if conda env list | awk '{print $1}' | rg -x "adaptive-reasoning-budget-allocation" >/dev/null 2>&1; then
    conda activate adaptive-reasoning-budget-allocation >/dev/null 2>&1 || true
    echo "Attempted conda activate adaptive-reasoning-budget-allocation"
  elif conda env list | awk '{print $1}' | rg -x "base" >/dev/null 2>&1; then
    conda activate base >/dev/null 2>&1 || true
    echo "Attempted conda activate base"
  fi
fi

echo "hostname: $(hostname)"
echo "date: $(date -Iseconds)"
echo "pwd: $(pwd)"
echo "python: $(command -v python3 || true)"
python3 --version || true
echo "OPENAI_API_KEY set: $( [[ -n "${OPENAI_API_KEY:-}" ]] && echo true || echo false )"

python3 - <<'PY'
import os
import re
import sys

def redact(message: str) -> str:
    if not isinstance(message, str):
        message = repr(message)
    key = os.getenv("OPENAI_API_KEY")
    if key:
        message = message.replace(key, "[REDACTED]")
    message = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", message)
    return message[:300]

try:
    from openai import OpenAI
except Exception as e:
    print("OpenAI package import: false")
    print("OpenAI API usable: false")
    print("Error:", type(e).__name__, redact(str(e)))
    sys.exit(1)

print("OpenAI package import: true")
try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    client.models.list()
    print("OpenAI API usable: true")
except Exception as e:
    print("OpenAI API usable: false")
    print("Error:", type(e).__name__, redact(str(e)))
    sys.exit(1)
PY

python scripts/run_real_model_ours_vs_external_validation.py \
  --timestamp 20260424T_OPENAI_REAL_MAIN \
  --providers openai \
  --datasets openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024 \
  --subset-size 20 \
  --seeds 11,23 \
  --budgets 4,6,8 \
  --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,external_l1_exact,external_tale_prompt_budgeting,external_s1_budget_forcing,self_consistency_3 \
  --resume

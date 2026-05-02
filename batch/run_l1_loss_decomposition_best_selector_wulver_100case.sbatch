#!/bin/bash
#SBATCH --job-name=l1-loss-dec-best-sel
#SBATCH --partition=debug
#SBATCH --qos=debug
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=logs/slurm/l1_loss_decomposition_best_selector_%j.out
#SBATCH --error=logs/slurm/l1_loss_decomposition_best_selector_%j.err

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$PWD}"
cd "$REPO_ROOT" || exit 1

mkdir -p logs/slurm "outputs"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUTDIR="${OUTDIR:-outputs/l1_loss_decomposition_best_selector_${STAMP}}"
# Conservative estimate for a full 100 paired triple (L1 + DR-v2 + selector) run is ~12.4k generator calls;
# override when probing with a small cap (e.g. MAX_CALLS=600 yields ~4 paired cases).
MAX_CALLS="${MAX_CALLS:-12400}"

export DR_V2_OV_RERANK_VERIFIER_BACKEND="${DR_V2_OV_RERANK_VERIFIER_BACKEND:-cohere}"
export DR_V2_OV_RERANK_COHERE_MODEL="${DR_V2_OV_RERANK_COHERE_MODEL:-command-a-03-2025}"

echo "==== L1 loss decomposition (best DR-v2 selector) ===="
hostname
date -u
echo "working_directory=$(pwd)"
echo "git_commit_sha=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
python -V || true

COHERE_BOOL=false
HF_BOOL=false
if [ -n "${COHERE_API_KEY:-}" ]; then COHERE_BOOL=true; fi
if [ -n "${HF_TOKEN:-}" ]; then HF_BOOL=true; fi
echo "COHERE_API_KEY_present=${COHERE_BOOL}"
echo "HF_TOKEN_present=${HF_BOOL}"

if [ "${COHERE_BOOL}" != "true" ]; then
  echo "ERROR: COHERE_API_KEY must be present in the submission environment."
  exit 1
fi

if [ -f "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh" ]; then
  # shellcheck disable=SC1091
  source "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh"
fi

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

python - <<'PY'
import importlib.util
import subprocess
import sys

spec = importlib.util.find_spec("cohere")
if spec is None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "cohere"])
PY

mkdir -p "${OUTDIR}"

RUN_CMD=(python scripts/run_l1_loss_decomposition_for_best_selector.py
  --timestamp "${STAMP}"
  --provider cohere
  --dataset openai/gsm8k
  --split test
  --seed 20260501
  --budget 4
  --target-scored 100
  --cohere-model command-a-03-2025
  --allow-api
  --max-calls "${MAX_CALLS}"
  --output-dir "${OUTDIR}"
  --resume)

echo "command=${RUN_CMD[*]}"
"${RUN_CMD[@]}"

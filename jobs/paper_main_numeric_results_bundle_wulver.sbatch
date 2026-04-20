#!/bin/bash
#SBATCH --job-name=paper_main_numeric_bundle
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=24:00:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err
#
# Submit from repository root:
#   sbatch jobs/paper_main_numeric_results_bundle_wulver.sbatch
#
# Optional env overrides:
#   PAPER_MAIN_NUMERIC_CONDA_ENV=base
#   PAPER_MAIN_NUMERIC_API_BACKEND=simulator|openai|groq|gemini
#   PAPER_MAIN_NUMERIC_MODEL=gpt-4.1-mini
#   PAPER_MAIN_NUMERIC_DATASETS="openai/gsm8k,EleutherAI/hendrycks_math,HuggingFaceH4/MATH-500,Idavidrein/gpqa,Hothan/OlympiadBench,meituan-longcat/AMO-Bench"
#   PAPER_MAIN_NUMERIC_BUDGETS="6,8,10"
#   PAPER_MAIN_NUMERIC_SEEDS="42,43,44"
#   PAPER_MAIN_NUMERIC_SUBSET_SIZE=24
#   PAPER_MAIN_NUMERIC_OUTPUT_DIR=outputs/paper_main_numeric_results_bundle_YYYYMMDD
#   PAPER_MAIN_NUMERIC_INCLUDE_NATURAL_PLAN=1

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "${REPO_ROOT}"

mkdir -p logs/slurm outputs

if [[ -f "${HOME}/.bashrc" ]]; then
  # shellcheck disable=SC1090
  source "${HOME}/.bashrc" || true
fi
if command -v conda >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  conda activate "${PAPER_MAIN_NUMERIC_CONDA_ENV:-base}" >/dev/null 2>&1 || true
fi

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

DATE_UTC="$(date -u +%Y%m%d)"
OUTPUT_DIR="${PAPER_MAIN_NUMERIC_OUTPUT_DIR:-outputs/paper_main_numeric_results_bundle_${DATE_UTC}}"
DATASETS="${PAPER_MAIN_NUMERIC_DATASETS:-openai/gsm8k,EleutherAI/hendrycks_math,HuggingFaceH4/MATH-500,Idavidrein/gpqa,Hothan/OlympiadBench,meituan-longcat/AMO-Bench}"
BUDGETS="${PAPER_MAIN_NUMERIC_BUDGETS:-6,8,10}"
SEEDS="${PAPER_MAIN_NUMERIC_SEEDS:-42,43,44}"
SUBSET_SIZE="${PAPER_MAIN_NUMERIC_SUBSET_SIZE:-24}"
API_BACKEND="${PAPER_MAIN_NUMERIC_API_BACKEND:-simulator}"
MODEL="${PAPER_MAIN_NUMERIC_MODEL:-gpt-4.1-mini}"

CMD=(
  python "scripts/run_paper_main_numeric_results_bundle.py"
  --output-dir "${OUTPUT_DIR}"
  --datasets "${DATASETS}"
  --budgets "${BUDGETS}"
  --seeds "${SEEDS}"
  --subset-size "${SUBSET_SIZE}"
  --api-backend "${API_BACKEND}"
  --model "${MODEL}"
  --resume
)

if [[ "${PAPER_MAIN_NUMERIC_INCLUDE_NATURAL_PLAN:-0}" == "1" ]]; then
  CMD+=(--include-natural-plan)
fi

echo "Running command:"
printf ' %q' "${CMD[@]}"
echo

"${CMD[@]}"

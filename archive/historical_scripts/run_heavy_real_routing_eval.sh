#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

if [[ -z "${HF_TOKEN:-}" && -z "${HUGGINGFACE_HUB_TOKEN:-}" ]]; then
  echo "Missing HF token env (HF_TOKEN or HUGGINGFACE_HUB_TOKEN)."
  exit 1
fi
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "Missing OPENAI_API_KEY."
  exit 1
fi
if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "Missing GEMINI_API_KEY."
  exit 1
fi
if [[ -z "${GROQ_API_KEY:-}" ]]; then
  echo "Missing GROQ_API_KEY."
  exit 1
fi

OUT_ROOT="${OUT_ROOT:-outputs/real_model_fixed_budget_heavy}"
mkdir -p "$OUT_ROOT"

SUBSET_SIZE="${SUBSET_SIZE:-60}"
MAX_ACTIONS="${MAX_ACTIONS:-8}"
MAX_BRANCHES="${MAX_BRANCHES:-4}"
BEST_OF_N_CANDIDATES="${BEST_OF_N_CANDIDATES:-3}"

PROVIDERS=(openai gemini groq)
DATASETS=(
  "openai/gsm8k"
  "EleutherAI/hendrycks_math"
  "Idavidrein/gpqa"
  "Hothan/OlympiadBench"
)
SEEDS=(7 19 23)

echo "Starting heavy real-model routing evaluation matrix."
echo "subset_size=$SUBSET_SIZE max_actions=$MAX_ACTIONS max_branches=$MAX_BRANCHES seeds=${SEEDS[*]}"

for provider in "${PROVIDERS[@]}"; do
  for dataset in "${DATASETS[@]}"; do
    for seed in "${SEEDS[@]}"; do
      safe_dataset="${dataset//\//__}"
      combo_root="$OUT_ROOT/provider_${provider}__dataset_${safe_dataset}__seed_${seed}"
      mkdir -p "$combo_root"

      if compgen -G "$combo_root/*/summary.csv" > /dev/null; then
        echo "Skipping completed combo: provider=$provider dataset=$dataset seed=$seed"
        continue
      fi

      echo "Running combo: provider=$provider dataset=$dataset seed=$seed"
      python scripts/run_real_model_fixed_budget_pilot.py \
        --providers "$provider" \
        --datasets "$dataset" \
        --subset-size "$SUBSET_SIZE" \
        --seed "$seed" \
        --max-actions "$MAX_ACTIONS" \
        --max-branches "$MAX_BRANCHES" \
        --include-best-of-n \
        --best-of-n-candidates "$BEST_OF_N_CANDIDATES" \
        --output-dir "$combo_root"
    done
  done
done

echo "Heavy real-model routing evaluation matrix complete."

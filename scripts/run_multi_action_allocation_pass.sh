#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_ROOT="${OUT_ROOT:-outputs/multi_action_allocation_pass}"
MODEL_DIR="${MODEL_DIR:-outputs/branch_scorer_v3/models}"
mkdir -p "$OUT_ROOT"

ROBUSTNESS_SEEDS="${ROBUSTNESS_SEEDS:-3,7,11,19,23}"
ROBUSTNESS_BUDGETS="${ROBUSTNESS_BUDGETS:-8,10,12,14}"
ROBUSTNESS_INIT_BRANCHES="${ROBUSTNESS_INIT_BRANCHES:-3,5,7}"
ROBUSTNESS_EPISODES="${ROBUSTNESS_EPISODES:-700}"
CONTROLLER_EVAL_EPISODES="${CONTROLLER_EVAL_EPISODES:-1200}"
CONTROLLER_EVAL_SEED="${CONTROLLER_EVAL_SEED:-17}"

required_models=(
  "$MODEL_DIR/adaptive_learned_branch_score.json"
  "$MODEL_DIR/adaptive_learned_branch_score_v4.json"
  "$MODEL_DIR/adaptive_learned_branch_score_v5.json"
  "$MODEL_DIR/adaptive_learned_branch_score_v6.json"
)

missing_models=0
for model_path in "${required_models[@]}"; do
  if [[ ! -f "$model_path" ]]; then
    missing_models=1
    break
  fi
done

if [[ "$missing_models" -eq 1 ]]; then
  TRAIN_ROOT="${TRAIN_ROOT:-outputs/branch_scorer_v3}"
  mkdir -p "$TRAIN_ROOT"
  dataset_path="$TRAIN_ROOT/branch_scorer_v3_dataset.jsonl"
  if [[ ! -f "$dataset_path" ]]; then
    python scripts/build_v3_ranking_dataset.py \
      --output-dir "$TRAIN_ROOT" \
      --episodes 1500 \
      --budget 10 \
      --n-init-branches 5 \
      --seed 7
  fi
  python scripts/train_branch_scorer_v3.py \
    --dataset "$dataset_path" \
    --output-dir "$TRAIN_ROOT"
  MODEL_DIR="$TRAIN_ROOT/models"
fi

ROBUSTNESS_DIR="$OUT_ROOT/robustness"
if [[ ! -f "$ROBUSTNESS_DIR/robustness_summary.json" ]]; then
  python scripts/evaluate_branch_scorer_robustness.py \
    --model-dir "$MODEL_DIR" \
    --output-dir "$ROBUSTNESS_DIR" \
    --seeds "$ROBUSTNESS_SEEDS" \
    --budgets "$ROBUSTNESS_BUDGETS" \
    --init-branches "$ROBUSTNESS_INIT_BRANCHES" \
    --episodes "$ROBUSTNESS_EPISODES" \
    --include-score-plus-progress \
    --include-eptree-baseline
else
  echo "Skipping robustness sweep; found $ROBUSTNESS_DIR/robustness_summary.json"
fi

IFS=',' read -r -a budget_values <<< "$ROBUSTNESS_BUDGETS"
IFS=',' read -r -a init_values <<< "$ROBUSTNESS_INIT_BRANCHES"

for budget in "${budget_values[@]}"; do
  for init_b in "${init_values[@]}"; do
    budget_trimmed="$(echo "$budget" | xargs)"
    init_trimmed="$(echo "$init_b" | xargs)"
    if [[ -z "$budget_trimmed" || -z "$init_trimmed" ]]; then
      continue
    fi
    out_json="$OUT_ROOT/controller_eval/controller_eval_b${budget_trimmed}_i${init_trimmed}.json"
    if [[ -f "$out_json" ]]; then
      echo "Skipping controller eval; found $out_json"
      continue
    fi
    python scripts/evaluate_branch_scorer_controller.py \
      --model-dir "$MODEL_DIR" \
      --output "$out_json" \
      --episodes "$CONTROLLER_EVAL_EPISODES" \
      --seed "$CONTROLLER_EVAL_SEED" \
      --budget "$budget_trimmed" \
      --n-init-branches "$init_trimmed"
  done
done

echo "Multi-action allocation pass complete: $OUT_ROOT"

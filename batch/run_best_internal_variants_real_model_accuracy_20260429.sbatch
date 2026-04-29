#!/bin/bash
#SBATCH -J best_internal_real_acc_20260429
#SBATCH -o logs/%x_%j.out
#SBATCH -e logs/%x_%j.err
#SBATCH -N 1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH -t 24:00:00

set -euo pipefail
mkdir -p logs

TS=20260429T_BEST_INTERNAL_VARIANTS_REAL_MODEL_ACCURACY_FULL
METHODS="strict_f3,strict_gate1_cap_k6,strict_f2,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max,tale,s1,self_consistency_3"
python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp "$TS" \
  --providers cohere \
  --cohere-model command-r-plus-08-2024 \
  --datasets openai/gsm8k,HuggingFaceH4/MATH-500 \
  --budgets 4,6,8 \
  --seeds 11,23 \
  --methods "$METHODS" \
  --target-scored-per-slice 50 \
  --max-examples 50 \
  --resume \
  --emit-trace-audit

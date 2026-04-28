#!/bin/bash
# Optional plan only. Do not submit without explicit approval.
#SBATCH --job-name=cohere-broad-table-nonloss
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=outputs/slurm_logs/cohere_broad_accuracy_cost_table_nonloss_20260428T185326Z_%j.out
#SBATCH --error=outputs/slurm_logs/cohere_broad_accuracy_cost_table_nonloss_20260428T185326Z_%j.err

set -euo pipefail

REPO_ROOT="/home/sv96/adaptive-reasoning-budget-allocation"
cd "$REPO_ROOT"
mkdir -p outputs/slurm_logs logs

TIMESTAMP="20260428T185326Z_NONLOSS_PLAN"
METHODS="direct_reserve_semantic_frontier_v2,strict_f3,external_l1_max,external_l1_exact,self_consistency_3,tot_bfs_matched_budget,tot_beam_matched_budget,tot_dfs_matched_budget"

if [ -f "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh" ]; then
  # shellcheck disable=SC1091
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh
fi
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

python - <<'PY'
import os
print("COHERE_API_KEY: present" if os.getenv("COHERE_API_KEY") else "COHERE_API_KEY: absent")
raise SystemExit(0 if os.getenv("COHERE_API_KEY") else 2)
PY

# NOTE: this repository runner does not currently include a non-loss random GSM8K selector
# in scripts/run_semantic_diversity_controller_diagnostic.py. Keep this as a submission template
# pending implementation of a random non-loss case sampler.
python scripts/run_semantic_diversity_controller_diagnostic.py \
  --timestamp "${TIMESTAMP}" \
  --mode cohere \
  --run-live-cohere \
  --selection-profile standard \
  --max-cases 30 \
  --allow-large-run \
  --methods "${METHODS}" \
  --budgets 4,6,8 \
  --emit-full-traces \
  --dataset-name openai/gsm8k

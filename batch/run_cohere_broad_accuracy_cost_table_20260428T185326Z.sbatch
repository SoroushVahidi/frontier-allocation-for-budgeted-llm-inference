#!/bin/bash
#SBATCH --job-name=cohere-broad-table
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=outputs/slurm_logs/cohere_broad_accuracy_cost_table_20260428T185326Z_%j.out
#SBATCH --error=outputs/slurm_logs/cohere_broad_accuracy_cost_table_20260428T185326Z_%j.err

set -euo pipefail

REPO_ROOT="/home/sv96/adaptive-reasoning-budget-allocation"
cd "$REPO_ROOT"
mkdir -p outputs/slurm_logs logs

TIMESTAMP="20260428T185326Z"
METHODS="direct_reserve_semantic_frontier_v2,strict_f3,external_l1_max,external_l1_exact,self_consistency_3,tot_bfs_matched_budget,tot_beam_matched_budget,tot_dfs_matched_budget"
LOSS_JSONL="outputs/cohere_absent_from_tree_loss_diagnostics_20260428T185257Z/loss_cases_absent_from_tree.jsonl"

echo "==== Cohere broad accuracy/cost table run ===="
echo "hostname=$(hostname)"
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "job_id=${SLURM_JOB_ID:-unknown}"
echo "repo_root=${REPO_ROOT}"
echo "git_commit=$(git rev-parse HEAD 2>/dev/null || echo unknown)"

if [ -f "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh" ]; then
  # shellcheck disable=SC1091
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh
fi
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "python=$(command -v python || command -v python3 || true)"
python -V || true

python - <<'PY'
import os
print("COHERE_API_KEY: present" if os.getenv("COHERE_API_KEY") else "COHERE_API_KEY: absent")
raise SystemExit(0 if os.getenv("COHERE_API_KEY") else 2)
PY
cohere_rc=$?
if [ "${cohere_rc}" -ne 0 ]; then
  echo "COHERE_API_KEY_MISSING_OR_EMPTY_ABORTING"
  exit 1
fi

python scripts/run_semantic_diversity_controller_diagnostic.py \
  --timestamp "${TIMESTAMP}" \
  --mode cohere \
  --run-live-cohere \
  --selection-profile expanded-loss-pool \
  --max-cases 30 \
  --allow-large-run \
  --allow-duplicate-example-fallback \
  --methods "${METHODS}" \
  --budgets 4,6,8 \
  --emit-full-traces \
  --dataset-name openai/gsm8k \
  --loss-jsonl "${LOSS_JSONL}"

exit_rc=$?
echo "runner_exit_code=${exit_rc}"
echo "outputs_dir=${REPO_ROOT}/outputs/semantic_diversity_controller_diagnostic_${TIMESTAMP}"
echo "report_doc=${REPO_ROOT}/docs/SEMANTIC_DIVERSITY_CONTROLLER_DIAGNOSTIC_${TIMESTAMP}.md"
exit "${exit_rc}"

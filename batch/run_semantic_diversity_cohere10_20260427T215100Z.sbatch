#!/bin/bash
#SBATCH --job-name=semdiv_coh10
#SBATCH --partition=debug
#SBATCH --qos=debug
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=06:00:00
#SBATCH --output=outputs/slurm_logs/semantic_diversity_cohere10_20260427T215100Z_%j.out
#SBATCH --error=outputs/slurm_logs/semantic_diversity_cohere10_20260427T215100Z_%j.err

set -euo pipefail

REPO_ROOT="/home/sv96/adaptive-reasoning-budget-allocation"
cd "$REPO_ROOT"
mkdir -p logs outputs/slurm_logs

TIMESTAMP="20260427T215100Z"

echo "==== Semantic diversity Cohere-10 diagnostic ===="
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
print("COHERE_API_KEY:", "present" if os.getenv("COHERE_API_KEY") else "absent")
raise SystemExit(0 if os.getenv("COHERE_API_KEY") else 2)
PY
cohere_rc=$?
if [ "${cohere_rc}" -ne 0 ]; then
  echo "COHERE_API_KEY_MISSING_OR_EMPTY_ABORTING"
  exit 1
fi

echo "Running: scripts/run_semantic_diversity_controller_diagnostic.py --timestamp ${TIMESTAMP} --mode cohere --run-live-cohere --max-cases 10"

python scripts/run_semantic_diversity_controller_diagnostic.py \
  --timestamp "${TIMESTAMP}" \
  --mode cohere \
  --run-live-cohere \
  --max-cases 10

exit_rc=$?
echo "runner_exit_code=${exit_rc}"
echo "outputs_dir=${REPO_ROOT}/outputs/semantic_diversity_controller_diagnostic_${TIMESTAMP}"
echo "report_doc=${REPO_ROOT}/docs/SEMANTIC_DIVERSITY_CONTROLLER_DIAGNOSTIC_${TIMESTAMP}.md"

exit "${exit_rc}"

#!/bin/bash
#SBATCH --job-name=offline_paper_audit
#SBATCH --partition=debug
#SBATCH --qos=debug
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=logs/offline_paper_audit_%j.out
#SBATCH --error=logs/offline_paper_audit_%j.err

set -u

REPO_ROOT="/home/sv96/adaptive-reasoning-budget-allocation"
cd "$REPO_ROOT"
mkdir -p logs

if [ -f "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh" ]; then
  # shellcheck disable=SC1091
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh
fi

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="outputs/offline_submission_audit_${TIMESTAMP}"
mkdir -p "$OUT_DIR"

echo "==== Offline Submission Audit Start ===="
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "hostname=$(hostname)"
echo "python_path=$(command -v python || true)"
echo "python_version=$(python -V 2>&1 || true)"
echo "git_commit=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
echo "policy=NO_PROVIDER_API_CALLS (Cohere/OpenAI/external generative APIs disabled for this audit)"

repo_health_pass="unknown"
ruff_pass="unknown"
pytest_pass="unknown"
paper_artifacts_pass="unknown"

run_step() {
  step_name="$1"
  shift
  echo "---- step=${step_name} ----"
  echo "cmd=$*"
  "$@"
  rc=$?
  echo "step=${step_name} rc=${rc}"
  return $rc
}

run_step "check_repo_health" python scripts/check_repo_health.py
if [ $? -eq 0 ]; then repo_health_pass="pass"; else repo_health_pass="fail"; fi

run_step "ruff_check" python -m ruff check
if [ $? -eq 0 ]; then ruff_pass="pass"; else ruff_pass="fail"; fi

run_step "pytest" python -m pytest
if [ $? -eq 0 ]; then pytest_pass="pass"; else pytest_pass="fail"; fi

run_step "paper_artifacts_regeneration" python scripts/paper/run_all_neurips_paper_artifacts.py
if [ $? -eq 0 ]; then paper_artifacts_pass="pass"; else paper_artifacts_pass="fail"; fi

python scripts/audit_manuscript_figure_table_consistency.py \
  --timestamp "$TIMESTAMP" \
  --out-dir "$OUT_DIR" \
  --repo-health-pass "$repo_health_pass" \
  --ruff-pass "$ruff_pass" \
  --pytest-pass "$pytest_pass" \
  --paper-artifacts-pass "$paper_artifacts_pass"

echo "==== Final artifact pointers ===="
echo "out_dir=${OUT_DIR}"
echo "report=docs/OFFLINE_SUBMISSION_AUDIT_${TIMESTAMP}.md"
echo "repo_health_pass=${repo_health_pass}"
echo "ruff_pass=${ruff_pass}"
echo "pytest_pass=${pytest_pass}"
echo "paper_artifacts_pass=${paper_artifacts_pass}"
echo "==== Offline Submission Audit End ===="

#!/bin/bash
#SBATCH --job-name=scorefill-88-losses
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=08:00:00
#SBATCH --output=logs/slurm/full_score_completion_88_external_losses_%j.out
#SBATCH --error=logs/slurm/full_score_completion_88_external_losses_%j.err

set -euo pipefail

REPO_ROOT="/home/sv96/adaptive-reasoning-budget-allocation"
cd "$REPO_ROOT"
mkdir -p logs/slurm outputs

RUN_STAMP="${RUN_STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
PREV_DIR="outputs/full_pipeline_best_selector_on_88_external_losses_20260502T210610Z"
SCORE_DIR="outputs/full_score_completion_88_external_losses_${RUN_STAMP}"
FINAL_DIR="outputs/full_score_completed_best_selector_on_88_external_losses_${RUN_STAMP}"
SELECTED_CASES="outputs/best_methods_on_external_losses_20260430T195200Z/selected_100_cases.csv"
SELECTED_CONFIG="configs/selected_selector_current.json"
DISCOVERY_JSONL="outputs/cohere_real_model_cost_normalized_validation_20260502T210610Z_DISCOVERY/per_example_records.jsonl"

mkdir -p "$SCORE_DIR" "$FINAL_DIR"

if [ -f "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh" ]; then
  # shellcheck disable=SC1091
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh
fi
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

{
  echo "start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hostname=$(hostname)"
  echo "repo_root=$REPO_ROOT"
  echo "branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  echo "commit=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "python=$(command -v python || true)"
  python -V || true
  echo "SLURM_JOB_ID=${SLURM_JOB_ID:-unknown}"
  echo "COHERE_API_KEY_present=$( [ -n \"${COHERE_API_KEY:-}\" ] && echo true || echo false )"
} | tee "$FINAL_DIR/run_env.log"

# Validate required inputs.
test -d "$PREV_DIR"
test -f "$SELECTED_CASES"
test -f "$SELECTED_CONFIG"
test -f "$DISCOVERY_JSONL"

# Cheap checks.
python scripts/run_full_score_completion_on_external_losses.py --help >/dev/null
python scripts/run_cohere_real_model_cost_normalized_validation.py --help >/dev/null

# Plan-only: build call plan and get expected API calls.
python scripts/run_full_score_completion_on_external_losses.py \
  --previous-output-dir "$PREV_DIR" \
  --selected-cases-csv "$SELECTED_CASES" \
  --selected-config "$SELECTED_CONFIG" \
  --discovery-records-jsonl "$DISCOVERY_JSONL" \
  --score-completion-output-dir "$SCORE_DIR" \
  --final-output-dir "$FINAL_DIR" \
  --verifier-model command-a-03-2025 \
  --plan-only | tee "$SCORE_DIR/plan_only_stdout.json"

EXPECTED_CALLS=$(python - <<PY
import json
from pathlib import Path
p=Path("$SCORE_DIR/missing_score_call_plan_summary.json")
d=json.loads(p.read_text(encoding="utf-8"))
print(int(d["expected_api_calls"]))
PY
)
echo "expected_api_calls=${EXPECTED_CALLS}" | tee -a "$FINAL_DIR/run_env.log"

# Bound check: stop if unexpectedly too large.
if [ "$EXPECTED_CALLS" -gt 200 ]; then
  python - <<PY
import json
from pathlib import Path
out=Path("$FINAL_DIR")
payload={
  "status":"failed_preflight",
  "reason":"expected_api_calls_too_large",
  "expected_api_calls": $EXPECTED_CALLS,
  "note":"Refusing paid API run because expected calls is unexpectedly much larger than prior ~134 missing."
}
(out/"failure_report.json").write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
PY
  exit 2
fi

# Execute full score completion + rerun.
python scripts/run_full_score_completion_on_external_losses.py \
  --previous-output-dir "$PREV_DIR" \
  --selected-cases-csv "$SELECTED_CASES" \
  --selected-config "$SELECTED_CONFIG" \
  --discovery-records-jsonl "$DISCOVERY_JSONL" \
  --score-completion-output-dir "$SCORE_DIR" \
  --final-output-dir "$FINAL_DIR" \
  --verifier-model command-a-03-2025

python - <<PY
import json
from pathlib import Path
score_dir=Path("$SCORE_DIR")
final_dir=Path("$FINAL_DIR")
payload={
  "submitted_job_id":"${SLURM_JOB_ID:-unknown}",
  "batch_script":"batch/run_full_score_completion_on_88_external_losses_wulver.sbatch",
  "score_completion_output_dir":str(score_dir),
  "final_rerun_output_dir":str(final_dir),
  "stdout_log":"logs/slurm/full_score_completion_88_external_losses_${SLURM_JOB_ID:-unknown}.out",
  "stderr_log":"logs/slurm/full_score_completion_88_external_losses_${SLURM_JOB_ID:-unknown}.err"
}
(score_dir/"batch_submission_info.json").write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
(final_dir/"batch_submission_info.json").write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
PY

echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$FINAL_DIR/run_env.log"

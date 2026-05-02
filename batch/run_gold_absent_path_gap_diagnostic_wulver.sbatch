#!/bin/bash
#SBATCH --job-name=gapdiag-88-abs
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=logs/slurm/gold_absent_path_gap_diagnostic_%j.out
#SBATCH --error=logs/slurm/gold_absent_path_gap_diagnostic_%j.err

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/sv96/adaptive-reasoning-budget-allocation}"
cd "$REPO_ROOT"
mkdir -p logs/slurm outputs

RUN_STAMP="${RUN_STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUTDIR="${OUTDIR:-outputs/gold_absent_path_gap_diagnostic_${RUN_STAMP}}"
INPUT_CASES="${INPUT_CASES:-outputs/best_methods_on_external_losses_20260430T195200Z/selected_100_cases.csv}"
DISCOVERY_JSONL="${DISCOVERY_JSONL:-outputs/cohere_real_model_cost_normalized_validation_20260502T210610Z_DISCOVERY/per_example_records.jsonl}"

declare -a PREV_CANDS=(
  "outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z"
  "outputs/full_pipeline_best_selector_on_88_external_losses_20260502T210610Z"
)
PREV_DIR=""
for d in "${PREV_CANDS[@]}"; do
  if [ -f "$d/per_case_results.csv" ]; then
    PREV_DIR="$d"
    break
  fi
done
if [ -z "${PREV_DIR}" ]; then
  echo "error: no previous run dir with per_case_results.csv found" >&2
  exit 4
fi

TRACE_ROOT_EXTRA=(
  "${REPO_ROOT}/outputs/trace_complete_external_losses_retry_20260430T204900Z/cohere_real_model_cost_normalized_validation_20260430T204900Z"
)

if [ -f "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh" ]; then
  # shellcheck disable=SC1091
  source "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh"
fi
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

mkdir -p "$OUTDIR"

{
  echo "start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hostname=$(hostname)"
  echo "repo_root=$REPO_ROOT"
  echo "branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  echo "commit=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "python=$(command -v python3 || command -v python || true)"
  python3 -V || true
  echo "SLURM_JOB_ID=${SLURM_JOB_ID:-unknown}"
} | tee "$OUTDIR/run_env.log"

python3 scripts/check_repo_health.py | tee -a "$OUTDIR/run_env.log"

python3 scripts/diagnose_gold_absent_path_gap.py \
  --input-cases "$INPUT_CASES" \
  --previous-run-dir "$PREV_DIR" \
  --output-dir "$OUTDIR" \
  --discovery-jsonl "$DISCOVERY_JSONL" \
  --trace-roots "${TRACE_ROOT_EXTRA[@]}" \
  | tee -a "$OUTDIR/run_env.log"

export PREV_DIR OUTDIR DISCOVERY_JSONL
python3 - <<'PY'
import json
import os
from pathlib import Path

meta = Path(os.environ["OUTDIR"]) / "batch_submission_info.json"
obj = {}
if meta.exists():
    try:
        obj = json.loads(meta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        obj = {}
obj.update(
    {
        "job_id": os.environ.get("SLURM_JOB_ID", ""),
        "submitted_via": "batch/run_gold_absent_path_gap_diagnostic_wulver.sbatch",
        "previous_run_dir": os.environ["PREV_DIR"],
        "output_dir": os.environ["OUTDIR"],
        "discovery_jsonl": os.environ["DISCOVERY_JSONL"],
    }
)
meta.parent.mkdir(parents=True, exist_ok=True)
meta.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

echo "done output_dir=$OUTDIR"

#!/bin/bash
#SBATCH --job-name=ssdf-v1-gold-abs
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=08:00:00
#SBATCH --output=logs/slurm/strategy_seeded_discovery_66_gold_absent_%j.out
#SBATCH --error=logs/slurm/strategy_seeded_discovery_66_gold_absent_%j.err

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/sv96/adaptive-reasoning-budget-allocation}"
cd "$REPO_ROOT"
mkdir -p logs/slurm outputs

RUN_STAMP="${RUN_STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_MAIN="outputs/strategy_seeded_discovery_on_66_gold_absent_${RUN_STAMP}"

PATH_GAP_CSV="${PATH_GAP_CSV:-outputs/gold_absent_path_gap_diagnostic_20260502T215957Z/per_case_path_gap_diagnostic.csv}"
STILL_LOST_CSV="${STILL_LOST_CSV:-outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/still_lost_cases.csv}"
SELECTED_100_CSV="${SELECTED_100_CSV:-outputs/best_methods_on_external_losses_20260430T195200Z/selected_100_cases.csv}"
BASELINE_JSONL="${BASELINE_JSONL:-outputs/cohere_real_model_cost_normalized_validation_20260502T210610Z_DISCOVERY/per_example_records.jsonl}"

EXPECTED_CASES="${EXPECTED_CASES:-66}"
CASE_SLOP="${CASE_SLOP:-3}"
MAX_SUM_BUDGET="${MAX_SUM_BUDGET:-620}"
ALLOW_CASE_MISMATCH="${ALLOW_CASE_MISMATCH:-0}"

mkdir -p "$OUT_MAIN"

if [[ -f "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh" ]]; then
  # shellcheck disable=SC1091
  source "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh"
fi
if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

PYTHON_BIN="$(command -v python3 || command -v python || true)"

{
  echo "start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hostname=$(hostname)"
  echo "repo_root=$REPO_ROOT"
  echo "branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  echo "commit=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "python=$PYTHON_BIN"
  "$PYTHON_BIN" -V || true
  echo "SLURM_JOB_ID=${SLURM_JOB_ID:-unknown}"
  if [[ -n "${COHERE_API_KEY:-}" ]]; then echo "COHERE_API_KEY_present=true"; else echo "COHERE_API_KEY_present=false"; fi
} | tee "$OUT_MAIN/run_env.log"

for f in "$PATH_GAP_CSV" "$STILL_LOST_CSV" "$SELECTED_100_CSV" "$BASELINE_JSONL"; do
  test -f "$f" || { echo "missing required input: $f" >&2; exit 2; }
done

"$PYTHON_BIN" scripts/check_repo_health.py | tee -a "$OUT_MAIN/run_env.log"

"$PYTHON_BIN" scripts/run_strategy_seeded_discovery_on_66_gold_absent.py \
  --path-gap-csv "$PATH_GAP_CSV" \
  --still-lost-csv "$STILL_LOST_CSV" \
  --selected-100-csv "$SELECTED_100_CSV" \
  --baseline-jsonl "$BASELINE_JSONL" \
  --expect-case-count "$EXPECTED_CASES" \
  --case-count-slop "$CASE_SLOP" \
  --max-budget-sum "$MAX_SUM_BUDGET" \
  --preflight-only \
  --stamp "$RUN_STAMP" | tee "$OUT_MAIN/preflight_stats.stdout.txt"

test -f "$OUT_MAIN/preflight_stats.json"

"$PYTHON_BIN" - <<PY | tee -a "$OUT_MAIN/run_env.log"
import json
from pathlib import Path

d = json.loads(Path("$OUT_MAIN/preflight_stats.json").read_text(encoding="utf-8"))
case_n = int(d["case_count"])
sum_budget = int(d["sum_budget_ceiling_hint"])
low = ${EXPECTED_CASES} - ${CASE_SLOP}
high = ${EXPECTED_CASES} + ${CASE_SLOP}
print(f"parsed_preflight_case_count={case_n}")
print(f"parsed_preflight_sum_budget_ceiling_hint={sum_budget}")
print(f"expected_case_band=[{low}, {high}]")
if ${ALLOW_CASE_MISMATCH} != 1:
    assert low <= case_n <= high, f"case count {case_n} outside band"
assert sum_budget <= ${MAX_SUM_BUDGET}, f"sum budget {sum_budget} exceeds ceiling ${MAX_SUM_BUDGET}"
print("estimated_generation_completion_calls_ceiling_cases_times_budget=" + str(sum_budget))
print("preflight_ok=true")
PY

"$PYTHON_BIN" scripts/run_strategy_seeded_discovery_on_66_gold_absent.py \
  --path-gap-csv "$PATH_GAP_CSV" \
  --still-lost-csv "$STILL_LOST_CSV" \
  --selected-100-csv "$SELECTED_100_CSV" \
  --baseline-jsonl "$BASELINE_JSONL" \
  --expect-case-count "$EXPECTED_CASES" \
  --case-count-slop "$CASE_SLOP" \
  --max-budget-sum "$MAX_SUM_BUDGET" \
  --stamp "$RUN_STAMP" 2>&1 | tee "$OUT_MAIN/slurm_discovery_stdout.log"

"$PYTHON_BIN" - <<PY
import json
from pathlib import Path
out = Path("$OUT_MAIN")
meta = {}
if (out / "batch_submission_info.json").exists():
    try:
        meta = json.loads((out / "batch_submission_info.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        meta = {}
meta.update({
    "submitted_job_id": "${SLURM_JOB_ID:-unknown}",
    "submitted_via": "batch/run_strategy_seeded_discovery_on_66_gold_absent_wulver.sbatch",
    "run_stamp": "$RUN_STAMP",
    "output_dir": "$OUT_MAIN",
    "paths": {
        "path_gap_csv": "$PATH_GAP_CSV",
        "still_lost_csv": "$STILL_LOST_CSV",
        "selected_100_csv": "$SELECTED_100_CSV",
        "baseline_jsonl": "$BASELINE_JSONL",
    },
    "expected_cases": ${EXPECTED_CASES},
    "case_slop": ${CASE_SLOP},
    "max_sum_budget_guard": ${MAX_SUM_BUDGET},
})
out.mkdir(parents=True, exist_ok=True)
(out / "batch_submission_info.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

echo "done output_dir=$OUT_MAIN" | tee -a "$OUT_MAIN/run_env.log"

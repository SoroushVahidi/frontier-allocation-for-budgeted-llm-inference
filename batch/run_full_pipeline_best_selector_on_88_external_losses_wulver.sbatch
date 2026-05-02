#!/bin/bash
#SBATCH --job-name=fullpipe-88-losses
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=12:00:00
#SBATCH --output=logs/slurm/full_pipeline_best_selector_on_88_external_losses_%j.out
#SBATCH --error=logs/slurm/full_pipeline_best_selector_on_88_external_losses_%j.err

set -euo pipefail

REPO_ROOT="/home/sv96/adaptive-reasoning-budget-allocation"
cd "$REPO_ROOT"

mkdir -p logs/slurm outputs

RUN_STAMP="${RUN_STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUTDIR="outputs/full_pipeline_best_selector_on_88_external_losses_${RUN_STAMP}"
DISCOVERY_TS="${RUN_STAMP}_DISCOVERY"
DISCOVERY_OUT="outputs/cohere_real_model_cost_normalized_validation_${DISCOVERY_TS}"
INPUT_CASES="outputs/best_methods_on_external_losses_20260430T195200Z/selected_100_cases.csv"
SELECTOR_CONFIG="configs/selected_selector_current.json"

mkdir -p "$OUTDIR"

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
  echo "OPENAI_API_KEY_present=$( [ -n \"${OPENAI_API_KEY:-}\" ] && echo true || echo false )"
} | tee "$OUTDIR/run_env.log"

# 1) Validate required inputs
test -f "$INPUT_CASES"
test -f "$SELECTOR_CONFIG"

# 2) Cheap helps / invocation checks
python scripts/run_cohere_real_model_cost_normalized_validation.py --help >/dev/null
python scripts/run_full_pipeline_best_selector_on_external_losses.py --help >/dev/null

# 3) Prepare exact 88-case filter and run vars
RUN_STAMP="$RUN_STAMP" OUTDIR="$OUTDIR" python - <<'PY'
import csv
import json
import os
from pathlib import Path

repo = Path("/home/sv96/adaptive-reasoning-budget-allocation")
input_cases = repo / "outputs/best_methods_on_external_losses_20260430T195200Z/selected_100_cases.csv"
outdir = repo / os.environ["OUTDIR"]
rows = list(csv.DictReader(input_cases.open("r", encoding="utf-8", newline="")))
if len(rows) != 88:
    raise SystemExit(f"Expected 88 rows in selected_100_cases.csv, found {len(rows)}")

allowed = outdir / "allowed_example_ids.jsonl"
datasets = set()
seeds = set()
budgets = set()
with allowed.open("w", encoding="utf-8") as f:
    for r in rows:
        datasets.add(str(r["dataset"]))
        seeds.add(int(float(r["seed"])))
        budgets.add(int(float(r["budget"])))
        obj = {
            "dataset": r["dataset"],
            "example_id": r["example_id"],
            "seed": int(float(r["seed"])),
            "budget": int(float(r["budget"])),
            "method": "direct_reserve_semantic_frontier_v2",
        }
        f.write(json.dumps(obj) + "\n")

run_vars = {
    "DATASETS": ",".join(sorted(datasets)),
    "SEEDS": ",".join(str(x) for x in sorted(seeds)),
    "BUDGETS": ",".join(str(x) for x in sorted(budgets)),
    "EXPECTED_CASES": len(rows),
    "EXPECTED_MAX_API_CALLS_BOUND": len(rows),
}
(outdir / "run_vars.json").write_text(json.dumps(run_vars, indent=2) + "\n", encoding="utf-8")
PY

# Export run vars from JSON without printing secrets.
DATASETS=$(python -c "import json;print(json.load(open('$OUTDIR/run_vars.json'))['DATASETS'])")
SEEDS=$(python -c "import json;print(json.load(open('$OUTDIR/run_vars.json'))['SEEDS'])")
BUDGETS=$(python -c "import json;print(json.load(open('$OUTDIR/run_vars.json'))['BUDGETS'])")
EXPECTED_CASES=$(python -c "import json;print(json.load(open('$OUTDIR/run_vars.json'))['EXPECTED_CASES'])")
EXPECTED_MAX_API_CALLS_BOUND=$(python -c "import json;print(json.load(open('$OUTDIR/run_vars.json'))['EXPECTED_MAX_API_CALLS_BOUND'])")

echo "datasets=${DATASETS}" | tee -a "$OUTDIR/run_env.log"
echo "seeds=${SEEDS}" | tee -a "$OUTDIR/run_env.log"
echo "budgets=${BUDGETS}" | tee -a "$OUTDIR/run_env.log"
echo "expected_cases=${EXPECTED_CASES}" | tee -a "$OUTDIR/run_env.log"
echo "expected_max_api_calls_bound=${EXPECTED_MAX_API_CALLS_BOUND}" | tee -a "$OUTDIR/run_env.log"

# 4) Validate method runnable without paid calls
python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp "${DISCOVERY_TS}_VALIDATE" \
  --providers cohere \
  --datasets "$DATASETS" \
  --budgets "$BUDGETS" \
  --seeds "$SEEDS" \
  --methods direct_reserve_semantic_frontier_v2 \
  --target-scored-per-slice 88 \
  --max-examples 88 \
  --validate-methods-only

# 5) Full discovery rerun on exactly the 88 cases (paid calls bounded by filter)
python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp "$DISCOVERY_TS" \
  --providers cohere \
  --cohere-model command-a-03-2025 \
  --datasets "$DATASETS" \
  --budgets "$BUDGETS" \
  --seeds "$SEEDS" \
  --methods direct_reserve_semantic_frontier_v2 \
  --target-scored-per-slice 88 \
  --max-examples 88 \
  --allowed-example-ids-file "$OUTDIR/allowed_example_ids.jsonl" \
  --resume

# 6) Post-hoc selected-selector application + required artifact package
python scripts/run_full_pipeline_best_selector_on_external_losses.py \
  --input-cases-csv "$INPUT_CASES" \
  --selected-config "$SELECTOR_CONFIG" \
  --discovery-records-jsonl "$DISCOVERY_OUT/per_example_records.jsonl" \
  --output-dir "$OUTDIR" \
  --run-type B

python - <<PY
import json
from pathlib import Path
out = Path("$OUTDIR")
payload = {
  "submitted_job_id": "${SLURM_JOB_ID:-unknown}",
  "batch_script": "batch/run_full_pipeline_best_selector_on_88_external_losses_wulver.sbatch",
  "output_dir": str(out),
  "discovery_output_dir": "$DISCOVERY_OUT",
  "stdout_log": "logs/slurm/full_pipeline_best_selector_on_88_external_losses_${SLURM_JOB_ID:-unknown}.out",
  "stderr_log": "logs/slurm/full_pipeline_best_selector_on_88_external_losses_${SLURM_JOB_ID:-unknown}.err"
}
(out / "batch_submission_info.json").write_text(json.dumps(payload, indent=2) + "\\n", encoding="utf-8")
PY

echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$OUTDIR/run_env.log"

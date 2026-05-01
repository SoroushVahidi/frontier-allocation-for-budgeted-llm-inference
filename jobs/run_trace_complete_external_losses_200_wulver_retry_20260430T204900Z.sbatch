#!/bin/bash
#SBATCH --job-name=trace_loss_retry
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=24:00:00
#SBATCH --output=logs/trace_loss_retry_%j.out
#SBATCH --error=logs/trace_loss_retry_%j.err

set -euo pipefail

echo "hostname: $(hostname)"
echo "date: $(date)"
echo "repo_path: $(pwd)"
echo "branch: $(git rev-parse --abbrev-ref HEAD)"
echo "commit: $(git rev-parse HEAD)"

if [ -f /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh ]; then
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh
  if conda env list | awk '{print $1}' | awk '/adaptive|frontier/ {found=1} END {exit found?0:1}'; then
    conda activate adaptive-reasoning-budget-allocation || conda activate frontier-allocation || true
  fi
fi

if [ -n "${COHERE_API_KEY:-}" ]; then
  echo "COHERE_API_KEY: present"
else
  echo "COHERE_API_KEY: missing"
fi

python scripts/check_repo_health.py || true
pytest -q tests/test_trace_complete_external_losses.py

RUN_TS=20260430T204900Z
OUT_DRY="outputs/trace_complete_external_losses_retry_${RUN_TS}_dryrun"
OUT_SMOKE="outputs/trace_complete_external_losses_retry_${RUN_TS}_smoke"
OUT_FULL="outputs/trace_complete_external_losses_retry_${RUN_TS}"

python scripts/collect_trace_complete_external_losses.py \
  --target-trace-losses 200 \
  --dataset gsm8k \
  --budgets 4 6 8 \
  --seeds 11 23 37 41 53 67 \
  --search-roots outputs archive logs results \
  --output-dir "${OUT_DRY}" \
  --provider cohere \
  --cohere-model command-r-plus \
  --dry-run

python scripts/collect_trace_complete_external_losses.py \
  --target-trace-losses 200 \
  --dataset gsm8k \
  --budgets 4 \
  --seeds 11 \
  --search-roots outputs archive logs results \
  --output-dir "${OUT_SMOKE}" \
  --provider cohere \
  --cohere-model command-r-plus \
  --smoke-generate \
  --smoke-limit 3

python - <<'PY'
import json, pathlib, sys
summary = pathlib.Path("outputs/trace_complete_external_losses_retry_20260430T204900Z_smoke/trace_complete_loss_summary.json")
obj = json.loads(summary.read_text(encoding="utf-8"))
if obj.get("generation_runner_return_code", 1) != 0:
    print("Smoke gate failed: generation runner returned nonzero")
    sys.exit(1)
if int(obj.get("generated_per_example_records_files", 0)) <= 0:
    print("Smoke gate failed: no per_example_records output")
    sys.exit(1)
print("Smoke gate passed.")
PY

python scripts/collect_trace_complete_external_losses.py \
  --target-trace-losses 200 \
  --dataset gsm8k \
  --budgets 4 6 8 \
  --seeds 11 23 37 41 53 67 \
  --search-roots outputs archive logs results \
  --output-dir "${OUT_FULL}" \
  --provider cohere \
  --cohere-model command-r-plus

#!/bin/bash
#SBATCH --job-name=trace_loss_200
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=24:00:00
#SBATCH --output=logs/trace_loss_200_%j.out
#SBATCH --error=logs/trace_loss_200_%j.err

set -euo pipefail

REPO_ROOT="/mmfs1/home/sv96/adaptive-reasoning-budget-allocation"
cd "${REPO_ROOT}"

TS="20260430T194200Z"
OUT_DIR="outputs/trace_complete_external_losses_${TS}"
mkdir -p logs jobs "${OUT_DIR}"

echo "hostname: $(hostname)"
echo "date: $(date -u)"
echo "repo_path: ${REPO_ROOT}"
echo "branch: $(git rev-parse --abbrev-ref HEAD)"
echo "commit: $(git rev-parse HEAD)"

if [ -f /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh ]; then
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh
fi

if [ -d ".venv/bin" ]; then
  source .venv/bin/activate
elif [ -d ".venv-test/bin" ]; then
  source .venv-test/bin/activate
elif command -v conda >/dev/null 2>&1; then
  if conda env list | awk '{print $1}' | awk '$1=="repo-env"{ok=1} END{exit ok?0:1}'; then
    conda activate repo-env
  else
    conda create -y -n repo-env python=3.10
    conda activate repo-env
  fi
else
  python3 -m venv .venv
  source .venv/bin/activate
fi

python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt -r requirements-dev.txt

if [ -n "${COHERE_API_KEY:-}" ]; then
  echo "COHERE_API_KEY: present"
else
  echo "COHERE_API_KEY: absent"
fi

python scripts/check_repo_health.py || true
pytest -q tests/test_trace_complete_external_losses.py

python scripts/collect_trace_complete_external_losses.py \
  --target-trace-losses 200 \
  --dataset gsm8k \
  --budgets 4 6 8 \
  --seeds 11 23 37 41 53 67 \
  --search-roots outputs archive logs results \
  --output-dir "${OUT_DIR}" \
  --provider cohere \
  --cohere-model command-r-plus \
  --dry-run

PLAN="$(python - <<'PY'
import json
from pathlib import Path
p = Path("outputs/trace_complete_external_losses_20260430T194200Z/generation_plan.json")
d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
print(",".join([
    str(int(d.get("existing_trace_complete_losses_found", 0))),
    str(int(d.get("additional_trace_complete_losses_needed", 0))),
    str(int(d.get("expected_cohere_generation_calls", 0))),
    str(int(d.get("expected_cohere_diagnostic_annotation_calls", 0))),
]))
PY
)"

EXISTING="$(echo "${PLAN}" | cut -d',' -f1)"
NEEDED="$(echo "${PLAN}" | cut -d',' -f2)"
GEN_CALLS="$(echo "${PLAN}" | cut -d',' -f3)"
ANN_CALLS="$(echo "${PLAN}" | cut -d',' -f4)"

echo "dry_run_existing_trace_complete=${EXISTING}"
echo "dry_run_additional_needed=${NEEDED}"
echo "dry_run_expected_generation_calls=${GEN_CALLS}"
echo "dry_run_expected_annotation_calls=${ANN_CALLS}"
echo "dry_run_model=command-r-plus"
echo "dry_run_output_dir=${OUT_DIR}"
echo "dry_run_generation_cache_path=${OUT_DIR}/cohere_generation_cache.jsonl"
echo "dry_run_annotation_cache_path=${OUT_DIR}/cohere_annotation_cache.jsonl"
echo "dry_run_dataset=gsm8k"
echo "dry_run_budgets=4,6,8"
echo "dry_run_seeds=11,23,37,41,53,67"
echo "dry_run_methods=direct_reserve_semantic_frontier_v2,strict_f3,external_l1_max"

if [ -n "${COHERE_API_KEY:-}" ] && [ "${GEN_CALLS}" -le 2000 ] && [ "${ANN_CALLS}" -le 200 ]; then
  python scripts/collect_trace_complete_external_losses.py \
    --target-trace-losses 200 \
    --dataset gsm8k \
    --budgets 4 6 8 \
    --seeds 11 23 37 41 53 67 \
    --search-roots outputs archive logs results \
    --output-dir "${OUT_DIR}" \
    --provider cohere \
    --cohere-model command-r-plus
else
  echo "Skipping actual run: dry-run gate failed."
fi

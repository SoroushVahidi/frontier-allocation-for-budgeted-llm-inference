#!/bin/bash
#SBATCH --job-name=loss_casebook_broad
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=40G
#SBATCH --time=24:00:00
#SBATCH --output=logs/loss_casebook_broad_%j.out
#SBATCH --error=logs/loss_casebook_broad_%j.err

set -euo pipefail

REPO_ROOT="/mmfs1/home/sv96/adaptive-reasoning-budget-allocation"
cd "${REPO_ROOT}"

TS="20260430T185500Z"
OUT_DIR="outputs/external_loss_casebook_broad_${TS}"
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
pytest -q tests/test_external_loss_casebook.py

python scripts/collect_external_loss_casebook.py \
  --target-losses 200 \
  --broad-search \
  --include-final-row-only \
  --search-roots outputs archive logs results batch jobs neurips2026_anonymous_artifact \
  --output-dir "${OUT_DIR}" \
  --provider cohere \
  --cohere-model command-r-plus \
  --dry-run

DRY_COUNTS="$(python - <<'PY'
import json
from pathlib import Path
out = Path("outputs/external_loss_casebook_broad_20260430T185500Z/loss_summary.json")
plan = Path("outputs/external_loss_casebook_broad_20260430T185500Z/cohere_annotation_plan.jsonl")
trace = final = comb = calls = 0
if out.exists():
    d = json.loads(out.read_text(encoding='utf-8'))
    trace = int(d.get("trace_complete_loss_cases_found", 0))
    final = int(d.get("final_row_only_loss_cases_found", 0))
    comb = int(d.get("combined_selected_casebook_size", 0))
if plan.exists():
    for line in plan.read_text(encoding='utf-8').splitlines():
        if line.strip():
            calls += int(json.loads(line).get("would_call", 0))
print(f"{trace},{final},{comb},{calls}")
PY
)"

TRACE_COUNT="$(echo "${DRY_COUNTS}" | cut -d',' -f1)"
FINAL_COUNT="$(echo "${DRY_COUNTS}" | cut -d',' -f2)"
COMBINED_COUNT="$(echo "${DRY_COUNTS}" | cut -d',' -f3)"
CALL_COUNT="$(echo "${DRY_COUNTS}" | cut -d',' -f4)"

echo "dry_run_trace_complete_losses=${TRACE_COUNT}"
echo "dry_run_final_row_only_losses=${FINAL_COUNT}"
echo "dry_run_combined_selected=${COMBINED_COUNT}"
echo "dry_run_expected_cohere_calls=${CALL_COUNT}"
echo "dry_run_cache_path=${OUT_DIR}/cohere_annotation_cache.jsonl"
echo "dry_run_model=command-r-plus"
echo "dry_run_output_dir=${OUT_DIR}"

if [ "${COMBINED_COUNT}" -ge 1 ] && [ -n "${COHERE_API_KEY:-}" ] && [ "${CALL_COUNT}" -le 200 ]; then
  python scripts/collect_external_loss_casebook.py \
    --target-losses 200 \
    --broad-search \
    --include-final-row-only \
    --search-roots outputs archive logs results batch jobs neurips2026_anonymous_artifact \
    --output-dir "${OUT_DIR}" \
    --provider cohere \
    --cohere-model command-r-plus
else
  echo "Skipping actual Cohere annotation run (gate failed)."
fi

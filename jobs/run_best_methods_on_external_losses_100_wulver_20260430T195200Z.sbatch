#!/bin/bash
#SBATCH --job-name=best_on_losses
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=24:00:00
#SBATCH --output=logs/best_on_losses_%j.out
#SBATCH --error=logs/best_on_losses_%j.err

set -euo pipefail

echo "hostname=$(hostname)"
echo "date=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "repo_path=$(pwd)"
echo "branch=$(git rev-parse --abbrev-ref HEAD)"
echo "commit=$(git rev-parse HEAD)"

if [ -f /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh ]; then
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh
  if conda env list | awk '{print $1}' | awk '/frontier-allocation/ {found=1} END {exit found?0:1}'; then
    conda activate frontier-allocation || true
  fi
fi

if [ -z "${COHERE_API_KEY:-}" ]; then
  echo "COHERE_API_KEY_present=0"
else
  echo "COHERE_API_KEY_present=1"
fi

python scripts/check_repo_health.py || true
pytest -q tests/test_evaluate_best_methods_on_external_loss_cases.py

RUN_TS=20260430T195200Z
OUT_DIR="outputs/best_methods_on_external_losses_${RUN_TS}"

python scripts/evaluate_best_methods_on_external_loss_cases.py \
  --target-cases 100 \
  --include-existing-trace-losses \
  --loss-casebook-dir outputs/external_loss_casebook_broad_20260430T185500Z \
  --search-roots outputs archive logs results \
  --output-dir "${OUT_DIR}" \
  --provider cohere \
  --cohere-model command-r-plus \
  --dry-run | tee "${OUT_DIR}_dry_run_plan.log"

EXPECTED_CALLS=$(python - <<'PY'
import json
from pathlib import Path
p=Path("outputs/best_methods_on_external_losses_20260430T195200Z_dry_run_plan.log")
txt=p.read_text(encoding="utf-8", errors="ignore")
start=txt.find("{")
end=txt.rfind("}")
if start>=0 and end>start:
    obj=json.loads(txt[start:end+1])
    print(int(obj.get("expected_cohere_calls", 0)))
else:
    print(999999)
PY
)
echo "expected_cohere_calls=${EXPECTED_CALLS}"

if [ "${EXPECTED_CALLS}" -le 400 ]; then
  python scripts/evaluate_best_methods_on_external_loss_cases.py \
    --target-cases 100 \
    --include-existing-trace-losses \
    --loss-casebook-dir outputs/external_loss_casebook_broad_20260430T185500Z \
    --search-roots outputs archive logs results \
    --output-dir "${OUT_DIR}" \
    --provider cohere \
    --cohere-model command-r-plus
else
  echo "Skip actual run because expected calls exceed cap."
  exit 1
fi

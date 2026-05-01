#!/bin/bash
#SBATCH --job-name=selector_33
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --output=logs/selector_33_%j.out
#SBATCH --error=logs/selector_33_%j.err

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
pytest -q tests/test_selector_on_gold_present_losses.py

RUN_TS=20260430T211700Z
OUT_DIR="outputs/selector_on_gold_present_losses_${RUN_TS}"

python scripts/run_selector_on_gold_present_losses.py \
  --loss-casebook-dir outputs/external_loss_casebook_broad_20260430T185500Z \
  --output-dir "${OUT_DIR}" \
  --provider cohere \
  --cohere-model command-r-plus \
  --dry-run | tee "${OUT_DIR}_dry_run.log"

EXPECTED=$(python - <<'PY'
import json, pathlib
p = pathlib.Path("outputs/selector_on_gold_present_losses_20260430T211700Z_dry_run.log")
t = p.read_text(encoding="utf-8", errors="ignore")
s = t.find("{"); e = t.rfind("}")
if s >= 0 and e > s:
    obj = json.loads(t[s:e+1])
    print(int(obj.get("expected_total_calls_upper_bound", 999999)))
else:
    print(999999)
PY
)
echo "expected_cohere_calls=${EXPECTED}"

if [ -n "${COHERE_API_KEY:-}" ] && [ "${EXPECTED}" -le 500 ]; then
  python scripts/run_selector_on_gold_present_losses.py \
    --loss-casebook-dir outputs/external_loss_casebook_broad_20260430T185500Z \
    --output-dir "${OUT_DIR}" \
    --provider cohere \
    --cohere-model command-r-plus
else
  echo "Skip actual run: missing key or expected calls too high."
  exit 1
fi

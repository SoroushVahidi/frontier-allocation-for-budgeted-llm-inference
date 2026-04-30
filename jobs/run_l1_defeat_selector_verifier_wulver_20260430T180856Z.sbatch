#!/bin/bash
#SBATCH --job-name=l1_selector_verifier
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=12:00:00
#SBATCH --output=logs/l1_selector_verifier_%j.out
#SBATCH --error=logs/l1_selector_verifier_%j.err

set -euo pipefail

REPO_ROOT="/mmfs1/home/sv96/adaptive-reasoning-budget-allocation"
cd "${REPO_ROOT}"

TS="20260430T180856Z"
OUT_ROOT="outputs/l1_defeat_selector_wulver_${TS}"
BEST_ARTIFACT_DIR="${OUT_ROOT}/best_selector_artifact"
COHERE_OUT="${OUT_ROOT}/cohere_verifier"
CACHE_PATH="${COHERE_OUT}/verifier_cache.jsonl"
RESULT_DOC="docs/L1_DEFEAT_SELECTOR_VERIFIER_RESULT_${TS}.md"
IMPOSSIBLE_DOC="docs/L1_DEFEAT_SELECTOR_IMPOSSIBILITY_CURRENT_ARTIFACTS_${TS}.md"

mkdir -p "${OUT_ROOT}" logs jobs "${COHERE_OUT}"

if [ -f /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh ]; then
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh
fi

if [ -d ".venv/bin" ]; then
  source .venv/bin/activate
elif command -v conda >/dev/null 2>&1; then
  if conda env list | rg -q "^repo-env\s"; then
    conda activate repo-env
  else
    conda create -y -n repo-env python=3.10
    conda activate repo-env
  fi
elif [ -d ".venv-test/bin" ]; then
  source .venv-test/bin/activate
else
  python3 -m venv .venv
  source .venv/bin/activate
fi

python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt -r requirements-dev.txt

echo "hostname: $(hostname)"
echo "date: $(date -u)"
echo "branch: $(git rev-parse --abbrev-ref HEAD)"
echo "commit: $(git rev-parse HEAD)"
echo "python: $(python --version)"
if [ -n "${COHERE_API_KEY:-}" ]; then
  echo "COHERE_API_KEY: present"
else
  echo "COHERE_API_KEY: absent"
fi
echo "output_dir: ${OUT_ROOT}"

echo "== Stage A: health/test =="
python scripts/check_repo_health.py || true
pytest -q tests/test_fast_selector_selection_experiment.py tests/test_cohere_cached_outcome_verifier_selector.py

echo "== Stage B: artifact scan =="
python scripts/scan_l1_defeat_selector_artifacts.py \
  --output-dir "${OUT_ROOT}"

echo "== Stage C: reconstruct best artifact =="
if [ ! -f "${BEST_ARTIFACT_DIR}/per_example_records.jsonl" ]; then
  cat > "${IMPOSSIBLE_DOC}" <<EOF
# L1 Defeat Selector Impossibility (Current Artifacts)

- timestamp: ${TS}
- reason: No usable positive-L1-defeat selector artifact found.
- stage: C (reconstruction gate)
- cohere_calls: skipped by policy
EOF
  echo "No positive artifact. Wrote ${IMPOSSIBLE_DOC}. Exiting before Cohere."
  exit 0
fi

echo "== Stage D: heuristic selector benchmark =="
python scripts/run_fast_selector_selection_experiment.py \
  --artifact-dir "${BEST_ARTIFACT_DIR}" \
  --output-dir "${OUT_ROOT}/fast_selector"

echo "== Stage E: Cohere verifier dry run =="
python scripts/run_cohere_cached_outcome_verifier_selector.py \
  --artifact-dir "${BEST_ARTIFACT_DIR}" \
  --output-dir "${COHERE_OUT}" \
  --cache-path "${CACHE_PATH}" \
  --model command-r-plus \
  --margin 0.15 \
  --dry-run

UNCACHED_CALLS="$(python - <<'PY'
import json
from pathlib import Path
p = Path("outputs/l1_defeat_selector_wulver_20260430T180856Z/cohere_verifier/dry_run_report.json")
d = json.loads(p.read_text(encoding="utf-8"))
print(int(d.get("uncached_cohere_calls", 0)))
PY
)"

ORACLE_MINUS_L1="$(python - <<'PY'
import csv
from pathlib import Path
p = Path("outputs/l1_defeat_selector_wulver_20260430T180856Z/artifact_scan.csv")
rows = list(csv.DictReader(p.open("r", encoding="utf-8")))
if rows:
    print(float(rows[0].get("oracle_minus_l1", "0") or 0))
else:
    print(0.0)
PY
)"

if [ -z "${COHERE_API_KEY:-}" ]; then
  echo "Skipping Stage F: COHERE_API_KEY absent."
  exit 0
fi
if [ "${UNCACHED_CALLS}" -gt 5000 ]; then
  echo "Skipping Stage F: uncached calls (${UNCACHED_CALLS}) too large."
  exit 0
fi
if ! python - "${ORACLE_MINUS_L1}" <<'PY'
import sys
v = float(sys.argv[1])
sys.exit(0 if v > 0 else 1)
PY
then
  echo "Skipping Stage F: oracle_minus_l1 <= 0."
  exit 0
fi

echo "== Stage F: Cohere verifier actual run =="
python scripts/run_cohere_cached_outcome_verifier_selector.py \
  --artifact-dir "${BEST_ARTIFACT_DIR}" \
  --output-dir "${COHERE_OUT}" \
  --cache-path "${CACHE_PATH}" \
  --model command-r-plus \
  --margin 0.15

cp "${COHERE_OUT}/final_selector_summary.csv" "${OUT_ROOT}/final_selector_summary.csv"
cp "${COHERE_OUT}/final_selector_summary.json" "${OUT_ROOT}/final_selector_summary.json"
cp "${COHERE_OUT}/override_casebook.csv" "${OUT_ROOT}/override_casebook.csv"
cp "${COHERE_OUT}/L1_DEFEAT_SELECTOR_VERIFIER_RESULT.md" "${RESULT_DOC}"
echo "Completed full pipeline."

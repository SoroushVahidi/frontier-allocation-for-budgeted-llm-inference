#!/bin/bash
#SBATCH -J arb_final_discovery
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --chdir=/home/sv96/adaptive-reasoning-budget-allocation
#SBATCH -o logs/slurm/%x_%j.out
#SBATCH -e logs/slurm/%x_%j.err
#SBATCH --time=12:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G

set -euo pipefail

# Do not derive repo from BASH_SOURCE on compute nodes — Slurm copies the script to spool,
# breaking relative paths when using dirname/name resolution.
REPO_ROOT="${REPO_ROOT:-/home/sv96/adaptive-reasoning-budget-allocation}"
cd "${REPO_ROOT}"
export PYTHONUNBUFFERED=1

if [[ -f "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh" ]]; then
  # shellcheck disable=SC1091
  source "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh"
fi
if [[ -f "${REPO_ROOT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.venv/bin/activate"
fi

TS_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_ROOT="${REPO_ROOT}/outputs/strategy_seeded_discovery_final_check_${TS_UTC}"
COHERE_TS="FINCHK_${TS_UTC}"
RUN_ENV="${OUT_ROOT}/run_env.log"
MON="${OUT_ROOT}/monitor_log.jsonl"

mkdir -p "${OUT_ROOT}" "${REPO_ROOT}/logs/slurm"

{
  echo "### hostname ###"
  hostname
  echo "### date ###"
  date -Is
  echo "### cwd ###"
  pwd
  echo "### branch ###"
  git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "nogit"
  echo "### commit ###"
  git rev-parse HEAD 2>/dev/null || echo "nogit"
  echo "### python ###"
  python --version
} | tee "${RUN_ENV}" >&2

python "${REPO_ROOT}/scripts/check_repo_health.py" | tee -a "${RUN_ENV}" >&2 || true

echo "[preflight] ${TS_UTC}" | tee -a "${RUN_ENV}" >&2
python "${REPO_ROOT}/scripts/run_strategy_seeded_discovery_final_check.py" \
  --timestamp "${TS_UTC}" \
  --preflight-only \
  --output-root "${REPO_ROOT}/outputs" \
  2>&1 | tee -a "${RUN_ENV}"

echo "[counts] Inspect audit_summary.json for Slice1 vs Slice2" | tee -a "${RUN_ENV}" >&2

EXPECTED_CEIL="$(python -c "
import csv, pathlib
p = pathlib.Path('outputs/gold_absent_path_gap_diagnostic_20260502T215957Z/per_case_path_gap_diagnostic.csv')
s = 0
if p.is_file():
  for row in csv.DictReader(p.open(encoding='utf-8')):
    try:
      s += max(8, int(float(row.get('budget') or 0)))
    except ValueError:
      pass
else:
  s = 66 * 10
print(s)
")"
echo "[estimated_budget_sum_upper_bound] ${EXPECTED_CEIL}" | tee -a "${RUN_ENV}" >&2
if [[ "${EXPECTED_CEIL}" -gt 12000 ]]; then
  echo "ABORT ceiling unexpectedly high (${EXPECTED_CEIL})" >&2
  exit 3
fi

echo "[paid_run] invoking Cohere validation direct_reserve_strategy_seeded_semantic_frontier_v2_final" >&2
python "${REPO_ROOT}/scripts/run_strategy_seeded_discovery_final_check.py" \
  --timestamp "${TS_UTC}" \
  --cohere-timestamp "${COHERE_TS}" \
  --output-root "${REPO_ROOT}/outputs" \
  --ceil-generations 12000 \
  2>&1 | tee -a "${RUN_ENV}" &
MAIN_PID=$!

(
  sleep 5
  echo "{\"event\":\"monitor_start\",\"bundle\":\"${OUT_ROOT}\",\"pid\":${MAIN_PID},\"ts\":\"$(date -Is)\"}" >>"${MON}"
  for _i in 1 2 3 4; do
    ALIVE="false"; kill -0 "${MAIN_PID}" 2>/dev/null && ALIVE="true"
    echo "{\"event\":\"heartbeat\",\"pid\":${MAIN_PID},\"alive\":${ALIVE},\"ts\":\"$(date -Is)\"}" >>"${MON}"
    sleep 30
  done
  echo "{\"event\":\"monitor_end_after_120s_window\",\"pid\":${MAIN_PID},\"ts\":\"$(date -Is)\"}" >>"${MON}"
) &
MONITOR_PID=$!

wait "${MAIN_PID}"
wait "${MONITOR_PID}" || true

python - <<PY
import json, os, pathlib
root = pathlib.Path("${OUT_ROOT}")
root.mkdir(parents=True, exist_ok=True)
payload = {"slurm_job_id": os.environ.get("SLURM_JOB_ID", ""), "cohere_timestamp_tag": "${COHERE_TS}", "output_bundle": str(root), "utc_tag": "${TS_UTC}"}
(root / "batch_submission_info.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

echo "DONE outputs at ${OUT_ROOT}"

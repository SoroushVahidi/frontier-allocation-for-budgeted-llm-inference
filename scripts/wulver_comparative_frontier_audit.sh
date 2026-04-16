#!/usr/bin/env bash
# Wulver-oriented launcher for new-paper matched-budget comparative frontier audit.
# Usage (from repo root):  bash scripts/wulver_comparative_frontier_audit.sh
# Or via Slurm:            sbatch jobs/comparative_frontier_audit_wulver.sbatch

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p outputs/comparative_frontier_audit logs/slurm

# --- Optional: HPC software stack (edit for your Wulver module/conda layout) ---
# module purge
# module load python/3.11 cuda/12.1  # example only
if [[ -f "${HOME}/.bashrc" ]]; then
  # shellcheck disable=SC1090
  source "${HOME}/.bashrc" || true
fi
if command -v conda >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  [[ -n "${CONDA_DEFAULT_ENV:-}" ]] || conda activate "${COMPARATIVE_AUDIT_CONDA_ENV:-base}" >/dev/null 2>&1 || true
fi

# --- Load secrets (repo-root .env); never echo key material ---
if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

# --- Backend: API only for this workflow (no silent simulator fallback) ---
API_BACKEND="${COMPARATIVE_AUDIT_API_BACKEND:-openai}"
if [[ "${API_BACKEND}" == "simulator" ]]; then
  echo "ERROR: This Wulver wrapper is meant for API-backed audits. Set COMPARATIVE_AUDIT_API_BACKEND=openai|groq|gemini or unset (default openai)." >&2
  exit 2
fi

_key_ok=0
case "${API_BACKEND}" in
  openai)  [[ -n "${OPENAI_API_KEY:-}" ]] && _key_ok=1 ;;
  groq)    [[ -n "${GROQ_API_KEY:-}" ]] && _key_ok=1 ;;
  gemini)  [[ -n "${GOOGLE_API_KEY:-}${GEMINI_API_KEY:-}" ]] && _key_ok=1 ;;
  *)       echo "ERROR: Unknown COMPARATIVE_AUDIT_API_BACKEND=${API_BACKEND}" >&2; exit 2 ;;
esac
if [[ "${_key_ok}" -ne 1 ]]; then
  echo "ERROR: No API key found for backend '${API_BACKEND}' after sourcing .env (check OPENAI_API_KEY / GROQ_API_KEY / GOOGLE_API_KEY)." >&2
  exit 2
fi

# --- Moderate first-cluster scale (override via env before sbatch) ---
SUBSET_SIZE="${COMPARATIVE_AUDIT_SUBSET_SIZE:-14}"
BUDGETS="${COMPARATIVE_AUDIT_BUDGETS:-8,10}"
DATASETS="${COMPARATIVE_AUDIT_DATASETS:-openai/gsm8k,EleutherAI/hendrycks_math}"
MODEL="${COMPARATIVE_AUDIT_MODEL:-gpt-4.1-mini}"
SEED="${COMPARATIVE_AUDIT_SEED:-42}"
OUTPUT_PARENT="${COMPARATIVE_AUDIT_OUTPUT_PARENT:-outputs/comparative_frontier_audit}"
TIMEOUT="${COMPARATIVE_AUDIT_TIMEOUT_SECONDS:-60}"

LAUNCH_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LAUNCH_META="${OUTPUT_PARENT}/wulver_launch_${SLURM_JOB_ID:-local}_${LAUNCH_STAMP}.json"
python3 - <<PY
import json, os, pathlib
p = pathlib.Path("${LAUNCH_META}")
p.parent.mkdir(parents=True, exist_ok=True)
meta = {
    "launcher_script": "scripts/wulver_comparative_frontier_audit.sh",
    "created_utc_rough": "${LAUNCH_STAMP}",
    "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
    "slurm_submit_dir": os.environ.get("SLURM_SUBMIT_DIR"),
    "api_backend": "${API_BACKEND}",
    "model": "${MODEL}",
    "subset_size": int("${SUBSET_SIZE}"),
    "budgets": "${BUDGETS}",
    "datasets": "${DATASETS}",
    "seed": int("${SEED}"),
    "output_parent": "${OUTPUT_PARENT}",
    "timeout_seconds": int("${TIMEOUT}"),
    "keys_present": {
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "groq": bool(os.environ.get("GROQ_API_KEY")),
        "gemini_or_google": bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")),
    },
}
p.write_text(json.dumps(meta, indent=2), encoding="utf-8")
PY

echo "=== Wulver comparative frontier audit ===" | tee -a "${OUTPUT_PARENT}/wulver_last_batch.log"
echo "ROOT_DIR=${ROOT_DIR}" | tee -a "${OUTPUT_PARENT}/wulver_last_batch.log"
echo "API_BACKEND=${API_BACKEND} MODEL=${MODEL}" | tee -a "${OUTPUT_PARENT}/wulver_last_batch.log"
echo "SUBSET_SIZE=${SUBSET_SIZE} BUDGETS=${BUDGETS}" | tee -a "${OUTPUT_PARENT}/wulver_last_batch.log"
echo "DATASETS=${DATASETS}" | tee -a "${OUTPUT_PARENT}/wulver_last_batch.log"
echo "OUTPUT_PARENT=${OUTPUT_PARENT} (Python will create <run_id>/ under this path)" | tee -a "${OUTPUT_PARENT}/wulver_last_batch.log"
echo "Launch meta: ${LAUNCH_META}" | tee -a "${OUTPUT_PARENT}/wulver_last_batch.log"
echo "Command:" | tee -a "${OUTPUT_PARENT}/wulver_last_batch.log"
set -x
exec python "${ROOT_DIR}/scripts/run_comparative_frontier_audit.py" \
  --api-backend "${API_BACKEND}" \
  --model "${MODEL}" \
  --subset-size "${SUBSET_SIZE}" \
  --budgets "${BUDGETS}" \
  --datasets "${DATASETS}" \
  --seed "${SEED}" \
  --timeout-seconds "${TIMEOUT}" \
  --output-dir "${OUTPUT_PARENT}"

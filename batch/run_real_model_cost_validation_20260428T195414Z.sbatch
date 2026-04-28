#!/bin/bash
#SBATCH --job-name=real-cost-val
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=outputs/slurm_logs/real_model_cost_validation_20260428T195414Z_%j.out
#SBATCH --error=outputs/slurm_logs/real_model_cost_validation_20260428T195414Z_%j.err

set -euo pipefail

REPO_ROOT="/home/sv96/adaptive-reasoning-budget-allocation"
cd "$REPO_ROOT"
mkdir -p outputs/slurm_logs logs

TIMESTAMP="20260428T195414Z"
PROVIDERS="cohere"
DATASETS="openai/gsm8k,HuggingFaceH4/MATH-500"
BUDGETS="4,6,8"
SEEDS="11,23"
METHODS="strict_f3,strict_gate1_cap_k6,strict_f3_anti_collapse_weak_v1,external_l1_max,tale,s1"
TARGET_SCORED=30
MAX_EXAMPLES=30
COHERE_MODEL="command-r-plus-08-2024"
REAL_OUT_DIR="outputs/cohere_real_model_cost_normalized_validation_${TIMESTAMP}"
ALIAS_OUT_DIR="outputs/real_model_cost_validation_${TIMESTAMP}"

START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
GIT_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo unknown)"

if [ -f "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh" ]; then
  # shellcheck disable=SC1091
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh
fi
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "==== Real-model cost-aware validation start ===="
echo "hostname=$(hostname)"
echo "date_utc=${START_UTC}"
echo "job_id=${SLURM_JOB_ID:-unknown}"
echo "repo_root=${REPO_ROOT}"
echo "git_commit=${GIT_COMMIT}"
echo "python=$(command -v python || command -v python3 || true)"
python -V || true

python - <<'PY'
import os
print("OPENAI_API_KEY:", "present" if os.getenv("OPENAI_API_KEY") else "absent")
print("COHERE_API_KEY:", "present" if os.getenv("COHERE_API_KEY") else "absent")
print("HF_TOKEN:", "present" if os.getenv("HF_TOKEN") else "absent")
PY

python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp "${TIMESTAMP}" \
  --providers "${PROVIDERS}" \
  --cohere-model "${COHERE_MODEL}" \
  --datasets "${DATASETS}" \
  --budgets "${BUDGETS}" \
  --seeds "${SEEDS}" \
  --methods "${METHODS}" \
  --target-scored-per-slice "${TARGET_SCORED}" \
  --max-examples "${MAX_EXAMPLES}" \
  --resume

RUN_EXIT=$?

python scripts/build_real_model_cost_validation_outputs.py --output-dir "${REAL_OUT_DIR}" || true

mkdir -p "${ALIAS_OUT_DIR}"
for f in per_case_results.csv method_summary.csv paired_vs_external_l1_max.csv token_latency_cost_summary.csv failure_decomposition.csv manifest.json slice_summary.csv pairwise_comparisons.csv claim_safety_table.csv; do
  if [ -f "${REAL_OUT_DIR}/${f}" ]; then
    cp "${REAL_OUT_DIR}/${f}" "${ALIAS_OUT_DIR}/${f}"
  fi
done

END_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python - <<PY
import json
import os
from pathlib import Path

path = Path("${ALIAS_OUT_DIR}") / "run_manifest.json"
payload = {
    "timestamp": "${TIMESTAMP}",
    "git_commit_hash": "${GIT_COMMIT}",
    "command": "python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp ${TIMESTAMP} --providers ${PROVIDERS} --cohere-model ${COHERE_MODEL} --datasets ${DATASETS} --budgets ${BUDGETS} --seeds ${SEEDS} --methods ${METHODS} --target-scored-per-slice ${TARGET_SCORED} --max-examples ${MAX_EXAMPLES} --resume",
    "methods": "${METHODS}".split(","),
    "datasets": "${DATASETS}".split(","),
    "budgets": [int(x) for x in "${BUDGETS}".split(",") if x],
    "seeds": [int(x) for x in "${SEEDS}".split(",") if x],
    "provider": "${PROVIDERS}",
    "model": "${COHERE_MODEL}",
    "env_key_presence": {
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
        "COHERE_API_KEY": bool(os.getenv("COHERE_API_KEY")),
        "HF_TOKEN": bool(os.getenv("HF_TOKEN")),
    },
    "slurm_job_id": os.getenv("SLURM_JOB_ID", ""),
    "start_time_utc": "${START_UTC}",
    "end_time_utc": "${END_UTC}",
    "completion_status": "success" if ${RUN_EXIT} == 0 else "failed",
    "source_output_dir": "${REAL_OUT_DIR}",
}
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

echo "runner_exit_code=${RUN_EXIT}"
echo "real_output_dir=${REAL_OUT_DIR}"
echo "alias_output_dir=${ALIAS_OUT_DIR}"
exit "${RUN_EXIT}"

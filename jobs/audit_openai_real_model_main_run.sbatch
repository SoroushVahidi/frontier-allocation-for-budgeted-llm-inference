#!/bin/bash
#SBATCH --job-name=openai-main-audit
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=logs/openai_real_model_main_run_audit_%j.out
#SBATCH --error=logs/openai_real_model_main_run_audit_%j.err

set -euo pipefail

REPO_DIR="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_DIR"

mkdir -p logs

if [[ -f "$HOME/.bashrc" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.bashrc" || true
fi

if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  echo "Using active virtualenv: $VIRTUAL_ENV"
elif [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate" || true
  echo "Activated .venv"
elif command -v conda >/dev/null 2>&1; then
  conda activate adaptive-reasoning-budget-allocation >/dev/null 2>&1 || conda activate base >/dev/null 2>&1 || true
fi

echo "hostname: $(hostname)"
echo "date: $(date -Iseconds)"
echo "pwd: $(pwd)"
echo "python: $(command -v python3 || true)"
python3 --version || true
echo "OPENAI_API_KEY set: $( [[ -n "${OPENAI_API_KEY:-}" ]] && echo true || echo false )"
echo "Running artifact-only OpenAI main-run audit (no API calls required)"

python3 scripts/audit_openai_real_model_main_run.py

# Lightweight smoke validation for expected outputs.
python3 - <<'PY'
from pathlib import Path
out_root = Path("outputs")
cands = sorted(out_root.glob("openai_real_model_main_run_audit_*"))
assert cands, "No openai_real_model_main_run_audit_* output directory found"
latest = cands[-1]
required = [
    "openai_summary_by_dataset_budget_method.csv",
    "openai_summary_by_method.csv",
    "openai_claim_safety_assessment.json",
    "STATUS.md",
]
missing = [name for name in required if not (latest / name).exists()]
assert not missing, f"Missing expected audit files: {missing}"
print({"status": "ok", "latest_audit_dir": str(latest)})
PY

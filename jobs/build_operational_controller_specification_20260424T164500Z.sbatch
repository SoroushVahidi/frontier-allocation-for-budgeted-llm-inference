#!/bin/bash
#SBATCH --job-name=operational-controller-spec
#SBATCH --partition=debug
#SBATCH --qos=debug
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/slurm/operational-controller-spec-%j.out
#SBATCH --error=logs/slurm/operational-controller-spec-%j.err

set -euo pipefail

REPO_DIR="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_DIR"

mkdir -p logs/slurm

if [[ -f /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh ]]; then
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh || true
  conda activate base >/dev/null 2>&1 || true
fi
if [[ -f "$HOME/.bashrc" ]]; then
  source "$HOME/.bashrc" || true
fi

echo "hostname: $(hostname)"
echo "date: $(date -Iseconds)"
echo "pwd: $(pwd)"
echo "python: $(command -v python3 || true)"
python3 --version || true
echo "OPENAI_API_KEY present: $( [[ -n "${OPENAI_API_KEY:-}" ]] && echo true || echo false )"
echo "COHERE_API_KEY present: $( [[ -n "${COHERE_API_KEY:-}" ]] && echo true || echo false )"
echo "Running static/code/doc operational specification audit (no API calls)"

python3 scripts/build_operational_controller_specification.py --timestamp 20260424T164500Z

python3 - <<'PY'
from pathlib import Path
root = Path("outputs/operational_controller_specification_20260424T164500Z")
required = [
    "symbol_to_code_map.csv",
    "method_hyperparameter_table.csv",
    "strict_f3_vs_gate1_diff_table.csv",
    "unresolved_method_spec_gaps.json",
    "STATUS.md",
]
missing = [n for n in required if not (root / n).exists()]
if missing:
    raise SystemExit(f"Missing expected outputs: {missing}")
doc = Path("docs/OPERATIONAL_CONTROLLER_SPECIFICATION_FOR_MANUSCRIPT_20260424T164500Z.md")
if not doc.exists():
    raise SystemExit("Missing expected manuscript doc output.")
print({"status": "ok", "output_dir": str(root), "doc_path": str(doc)})
PY

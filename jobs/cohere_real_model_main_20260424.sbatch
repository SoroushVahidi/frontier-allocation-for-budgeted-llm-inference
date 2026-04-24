#!/usr/bin/env bash
#SBATCH --job-name=cohere-real-main
#SBATCH --partition=debug
#SBATCH --qos=debug
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=logs/slurm/cohere_real_main_%j.out
#SBATCH --error=logs/slurm/cohere_real_main_%j.err

set -euo pipefail

REPO_DIR="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_DIR"

mkdir -p logs/slurm
export PYTHONUNBUFFERED=1

if [[ -f "$HOME/.bashrc" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.bashrc"
fi

echo "hostname: $(hostname)"
echo "date: $(date -Iseconds)"
echo "pwd: $(pwd)"
echo "python: $(command -v python3 || true)"
python3 --version || true
echo "OPENAI_API_KEY present: $( [[ -n "${OPENAI_API_KEY:-}" ]] && echo true || echo false )"
echo "COHERE_API_KEY present: $( [[ -n "${COHERE_API_KEY:-}" ]] && echo true || echo false )"

if [[ -z "${COHERE_API_KEY:-}" ]]; then
  echo "Cohere API usable: false"
  echo "Error: MissingAPIKey COHERE_API_KEY is not set"
  exit 1
fi

python3 - <<'PY'
import os
import re
import subprocess
import sys

def redact(message: str) -> str:
    if not isinstance(message, str):
        message = repr(message)
    key = os.getenv("COHERE_API_KEY")
    if key:
        message = message.replace(key, "[REDACTED]")
    message = re.sub(r"(api[_-]?key\s*[=:]\s*)([^\s,;]+)", r"\1[REDACTED]", message, flags=re.I)
    message = re.sub(r"\b[A-Za-z0-9_\-]{24,}\b", "[REDACTED]", message)
    return message[:300]

def fail(exc: Exception) -> None:
    print("Cohere API usable: false")
    print("Error:", type(exc).__name__, redact(str(exc)))
    raise SystemExit(1)

try:
    import cohere  # type: ignore
except Exception:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "cohere"])
        import cohere  # type: ignore
    except Exception as e:
        fail(e)

print("Cohere package import: true")

try:
    client = cohere.ClientV2(api_key=os.environ["COHERE_API_KEY"])
    client.chat(
        model="command-a-03-2025",
        messages=[{"role": "user", "content": "Reply with OK only."}],
        max_tokens=5,
    )
    print("Cohere API usable: true")
except Exception as e:
    fail(e)
PY

python scripts/run_real_model_ours_vs_external_validation.py \
  --timestamp 20260424T_COHERE_REAL_MAIN \
  --providers cohere \
  --datasets openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024 \
  --subset-size 20 \
  --seeds 11,23 \
  --budgets 4,6,8 \
  --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,external_l1_exact,external_tale_prompt_budgeting,external_s1_budget_forcing,self_consistency_3 \
  --resume

echo "Expected output directory: outputs/real_model_ours_vs_external_validation_20260424T_COHERE_REAL_MAIN/"
echo "Expected doc path: docs/REAL_MODEL_OURS_VS_EXTERNAL_VALIDATION_20260424T_COHERE_REAL_MAIN.md"

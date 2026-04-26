#!/bin/bash
#SBATCH --job-name=cohere_nonmath_audit
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --output=logs/cohere_nonmath_audit_%j.out
#SBATCH --error=logs/cohere_nonmath_audit_%j.err

set -euo pipefail

REPO_ROOT="/home/sv96/adaptive-reasoning-budget-allocation"
cd "$REPO_ROOT"
mkdir -p logs
export PYTHONUNBUFFERED=1

TIMESTAMP="20260425T_WULVER_COHERE_NONMATH_AUDIT"
OUT_DIR="outputs/cohere_real_model_cost_normalized_validation_${TIMESTAMP}"
REPORT_PATH="docs/COHERE_NONMATH_EXTERNAL_VALIDITY_AUDIT_${TIMESTAMP}.md"

echo "==== Cohere Non-Math External Validity Audit Start ===="
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "hostname=$(hostname)"
echo "git_commit=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
echo "python_path=$(command -v python || true)"
echo "python_version=$(python -V 2>&1 || true)"
echo "policy=COHERE_ONLY_NO_OPENAI"

if [ -f "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh" ]; then
  # shellcheck disable=SC1091
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh
fi

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

python -m pip install --upgrade cohere

KEY_STATE="missing"
if [ "${COHERE_API_KEY+x}" = "x" ]; then
  if [ -z "${COHERE_API_KEY}" ]; then
    KEY_STATE="empty"
  else
    KEY_STATE="present"
  fi
fi
echo "COHERE_API_KEY=${KEY_STATE}"
if [ "$KEY_STATE" != "present" ]; then
  echo "COHERE_READINESS_FAILED"
  echo "failure_type=missing key"
  echo "sanitized_error=COHERE_API_KEY missing in batch environment"
  exit 1
fi

python - <<'PY'
import os
import sys

try:
    import cohere
except Exception as e:  # noqa: BLE001
    print("COHERE_READINESS_FAILED")
    print("failure_type=SDK import problem")
    print(f"sanitized_error={type(e).__name__}: {str(e)[:500]}")
    raise SystemExit(1)

key = os.getenv("COHERE_API_KEY", "")
if not key:
    print("COHERE_READINESS_FAILED")
    print("failure_type=missing key")
    print("sanitized_error=COHERE_API_KEY missing inside readiness check")
    raise SystemExit(1)

try:
    client = cohere.ClientV2(api_key=key)
    _ = client.chat(
        model="command-r-plus-08-2024",
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        max_tokens=4,
    )
    print("COHERE_READINESS_OK")
except Exception as e:  # noqa: BLE001
    msg = str(e)
    low = msg.lower()
    if "401" in low or "unauthorized" in low or "invalid api" in low:
        ftype = "authentication failure"
    elif "quota" in low or "insufficient" in low:
        ftype = "quota failure"
    elif "429" in low or "rate" in low:
        ftype = "rate limit"
    elif "model" in low and ("not found" in low or "unavailable" in low):
        ftype = "model unavailable"
    elif "timeout" in low or "timed out" in low:
        ftype = "network timeout"
    else:
        ftype = "other"
    print("COHERE_READINESS_FAILED")
    print(f"failure_type={ftype}")
    print(f"sanitized_error={msg.replace(key, '[REDACTED]')[:1000]}")
    raise SystemExit(1)
PY

DATASETS="natural_plan,gpqa_diamond"
METHODS_REQUESTED="strict_f3_anti_collapse_weak_v1,strict_f3,external_l1_max,tale,s1"

python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp "$TIMESTAMP" \
  --providers cohere \
  --datasets "$DATASETS" \
  --budgets 4,6,8 \
  --seeds 11,23 \
  --methods "$METHODS_REQUESTED" \
  --target-scored-per-slice 100 \
  --max-examples 200 \
  --resume \
  --cohere-model command-r-plus-08-2024

python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp "$TIMESTAMP" \
  --providers cohere \
  --datasets "$DATASETS" \
  --budgets 4,6,8 \
  --seeds 11,23 \
  --methods "$METHODS_REQUESTED" \
  --target-scored-per-slice 100 \
  --max-examples 200 \
  --resume \
  --summarize-only \
  --cohere-model command-r-plus-08-2024

python - <<'PY'
from __future__ import annotations
import csv
import json
from pathlib import Path

repo = Path("/home/sv96/adaptive-reasoning-budget-allocation")
ts = "20260425T_WULVER_COHERE_NONMATH_AUDIT"
out_dir = repo / f"outputs/cohere_real_model_cost_normalized_validation_{ts}"
report = repo / f"docs/COHERE_NONMATH_EXTERNAL_VALIDITY_AUDIT_{ts}.md"

manifest = {}
manifest_path = out_dir / "manifest.json"
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

slice_rows = read_csv(out_dir / "slice_summary.csv")
pair_rows = read_csv(out_dir / "pairwise_comparisons.csv")
cost_rows = read_csv(out_dir / "cost_normalized_summary.csv")
incomplete_rows = read_csv(out_dir / "incomplete_slices.csv")

def pair_diff(dataset: str, b: str) -> str:
    for r in pair_rows:
        if r.get("dataset") == dataset and r.get("method_a") == "strict_f3_anti_collapse_weak_v1" and r.get("method_b") == b:
            return str(r.get("mean_accuracy_diff", "NA"))
    return "NA"

datasets_used = manifest.get("datasets_requested", [])
methods_supported = manifest.get("methods_supported", [])
methods_unsupported = manifest.get("methods_unsupported", [])

scored_lines = []
for r in slice_rows:
    scored_lines.append(
        f"- dataset={r.get('dataset')} method={r.get('method')} seed={r.get('seed')} budget={r.get('budget')} n_scored={r.get('n_scored')}"
    )
if not scored_lines:
    scored_lines = ["- No scored slices found yet."]

cost_lines = []
for r in cost_rows:
    cost_lines.append(
        f"- method={r.get('method')} mean_tokens={r.get('mean_tokens')} accuracy_per_1k_tokens={r.get('accuracy_per_1k_tokens')} mean_estimated_cost_usd={r.get('mean_estimated_cost_usd')}"
    )
if not cost_lines:
    cost_lines = ["- No cost-normalized rows generated yet."]

nat = "google-deepmind/natural-plan"
gpqa = "Idavidrein/gpqa"
nat_l1 = pair_diff(nat, "external_l1_max")
gpqa_l1 = pair_diff(gpqa, "external_l1_max")
nat_f3 = pair_diff(nat, "strict_f3")
gpqa_f3 = pair_diff(gpqa, "strict_f3")

favorable = 0
for v in [nat_l1, gpqa_l1, nat_f3, gpqa_f3]:
    try:
        favorable += int(float(v) > 0)
    except Exception:
        pass
if len(incomplete_rows) > 0:
    placement = "appendix_supporting" if favorable > 0 else "provenance_only"
    verdict = "mixed_or_incomplete"
else:
    placement = "main_paper_candidate" if favorable >= 3 else ("appendix_supporting" if favorable >= 1 else "provenance_only")
    verdict = "favorable" if favorable >= 3 else ("mixed" if favorable >= 1 else "unfavorable")

lines = [
    "# COHERE_NONMATH_EXTERNAL_VALIDITY_AUDIT",
    "",
    f"Timestamp: `{ts}`",
    f"Output package: `outputs/cohere_real_model_cost_normalized_validation_{ts}/`",
    "",
    "1. Did Cohere readiness pass inside the batch job?",
    "- yes (if job reached this report-generation step and logged COHERE_READINESS_OK).",
    "2. Which exact datasets were used?",
    f"- {datasets_used}",
    "3. Which exact methods were successfully run?",
    f"- {methods_supported}",
    "4. Which methods or datasets were unavailable, if any?",
    f"- methods_unsupported={methods_unsupported}",
    "5. How many scored examples were collected per dataset/method/budget/seed?",
    *scored_lines,
    "6. Did strict_f3_anti_collapse_weak_v1 beat external_l1_max on Natural Plan?",
    f"- mean_accuracy_diff={nat_l1}",
    "7. Did strict_f3_anti_collapse_weak_v1 beat external_l1_max on GPQA Diamond?",
    f"- mean_accuracy_diff={gpqa_l1}",
    "8. Did strict_f3_anti_collapse_weak_v1 beat default strict_f3?",
    f"- natural_plan_diff={nat_f3}; gpqa_diamond_diff={gpqa_f3}",
    "9. What are the token, latency, and estimated-cost differences?",
    *cost_lines,
    "10. Is this evidence favorable, mixed, or unfavorable for the broader-than-math claim?",
    f"- {verdict}",
    "11. Should the result be main-paper, appendix-only, or provenance-only?",
    f"- {placement}",
    "12. What incomplete slices remain?",
    f"- count={len(incomplete_rows)} (see `incomplete_slices.csv` for details)",
    "",
    "Claim discipline: supporting/diagnostic real-model evidence only; no universal-dominance claim.",
]
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"report={report}")
PY

echo "out_dir=${OUT_DIR}"
echo "report_path=${REPORT_PATH}"
echo "==== Cohere Non-Math External Validity Audit End ===="

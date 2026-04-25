#!/bin/bash
#SBATCH --job-name=cohere_f3_l1_long
#SBATCH --partition=debug
#SBATCH --qos=debug
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=logs/cohere_f3_l1_long_%j.out
#SBATCH --error=logs/cohere_f3_l1_long_%j.err

set -euo pipefail

REPO_ROOT="/home/sv96/adaptive-reasoning-budget-allocation"
cd "$REPO_ROOT"
mkdir -p logs

TIMESTAMP="20260425T_WULVER_COHERE_LONG"
RUN_DIR="outputs/real_model_ours_vs_external_validation_${TIMESTAMP}"
LOSS_DIR="outputs/strict_f3_vs_external_l1_max_more_loss_cases_${TIMESTAMP}"
LOSS_DOC="docs/STRICT_F3_VS_EXTERNAL_L1_MAX_MORE_LOSS_CASES_${TIMESTAMP}.md"

echo "==== Cohere Long Collection Job Start ===="
echo "hostname=$(hostname)"
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "python=$(command -v python || true)"
echo "repo_root=$REPO_ROOT"
echo "git_commit=$(git rev-parse HEAD 2>/dev/null || echo unknown)"

if [ -f "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh" ]; then
  # shellcheck disable=SC1091
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh
fi

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

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
  echo "sanitized_error=COHERE_API_KEY is not present in batch environment."
  echo "remediation=Export COHERE_API_KEY in your submit environment and resubmit."
  exit 1
fi

python -m pip install --upgrade cohere

python - <<'PY'
import os
import sys

msg = "Reply with exactly: OK"
try:
    import cohere
except Exception as e:  # noqa: BLE001
    print("COHERE_READINESS_FAILED")
    print("failure_type=SDK import problem")
    print(f"sanitized_error={type(e).__name__}: {str(e)[:500]}")
    print("command=python tiny Cohere ClientV2 chat readiness probe")
    print("remediation=Fix Python env and cohere package installation.")
    raise SystemExit(1)

api_key = os.getenv("COHERE_API_KEY", "")
if not api_key:
    print("COHERE_READINESS_FAILED")
    print("failure_type=missing key")
    print("sanitized_error=COHERE_API_KEY missing inside batch job")
    print("command=python tiny Cohere ClientV2 chat readiness probe")
    print("remediation=Export COHERE_API_KEY before sbatch.")
    raise SystemExit(1)

try:
    client = cohere.ClientV2(api_key=api_key)
    _ = client.chat(
        model="command-r-plus-08-2024",
        messages=[{"role": "user", "content": msg}],
        max_tokens=4,
    )
    print("COHERE_READINESS_OK")
except Exception as e:  # noqa: BLE001
    text = str(e)
    low = text.lower()
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
    print(f"sanitized_error={text.replace(api_key, '[REDACTED]')[:1000]}")
    print("command=python tiny Cohere ClientV2 chat readiness probe")
    print("remediation=Check key validity, quota, network, and model availability.")
    raise SystemExit(1)
PY

echo "==== Running long collection (resumable) ===="
python scripts/run_real_model_ours_vs_external_validation.py \
  --timestamp "$TIMESTAMP" \
  --providers cohere \
  --cohere-model command-r-plus-08-2024 \
  --datasets openai/gsm8k \
  --subset-size 120 \
  --seeds 11,23 \
  --budgets 4,6,8 \
  --methods strict_f3,external_l1_max \
  --resume

echo "==== Running summarize pass (resume, no-op if complete) ===="
python scripts/run_real_model_ours_vs_external_validation.py \
  --timestamp "$TIMESTAMP" \
  --providers cohere \
  --cohere-model command-r-plus-08-2024 \
  --datasets openai/gsm8k \
  --subset-size 120 \
  --seeds 11,23 \
  --budgets 4,6,8 \
  --methods strict_f3,external_l1_max \
  --resume

echo "==== Building strict_f3 loss-case package ===="
python - <<'PY'
from __future__ import annotations
import csv
import json
from pathlib import Path
from datetime import datetime, timezone

repo = Path("/home/sv96/adaptive-reasoning-budget-allocation")
timestamp = "20260425T_WULVER_COHERE_LONG"
run_dir = repo / f"outputs/real_model_ours_vs_external_validation_{timestamp}/cohere"
loss_dir = repo / f"outputs/strict_f3_vs_external_l1_max_more_loss_cases_{timestamp}"
loss_doc = repo / f"docs/STRICT_F3_VS_EXTERNAL_L1_MAX_MORE_LOSS_CASES_{timestamp}.md"
loss_dir.mkdir(parents=True, exist_ok=True)

rows_path = run_dir / "per_example_rows.csv"
if not rows_path.exists() or rows_path.stat().st_size == 0:
    raise SystemExit("No per_example_rows.csv found for builder input")

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=True) + "\n")

rows = read_csv(rows_path)
strict = {}
external = {}
for r in rows:
    key = (r.get("dataset",""), r.get("seed",""), r.get("budget",""), r.get("example_id",""))
    if r.get("method") == "strict_f3":
        strict[key] = r
    elif r.get("method") == "external_l1_max":
        external[key] = r

matched = []
loss = []
for key in sorted(set(strict) & set(external)):
    s = strict[key]
    e = external[key]
    base = {
        "provider": s.get("provider",""),
        "model": s.get("model",""),
        "dataset": s.get("dataset",""),
        "seed": s.get("seed",""),
        "budget": s.get("budget",""),
        "example_id": s.get("example_id",""),
        "strict_f3_correct": int(float(s.get("is_correct","0"))),
        "external_l1_max_correct": int(float(e.get("is_correct","0"))),
        "strict_f3_failure_type": s.get("failure_type",""),
        "external_l1_max_failure_type": e.get("failure_type",""),
        "strict_f3_actions_used": int(float(s.get("actions_used","0"))),
        "external_l1_max_actions_used": int(float(e.get("actions_used","0"))),
        "strict_f3_expansions": int(float(s.get("expansions","0"))),
        "external_l1_max_expansions": int(float(e.get("expansions","0"))),
        "strict_f3_verifications": int(float(s.get("verifications","0"))),
        "external_l1_max_verifications": int(float(e.get("verifications","0"))),
        "strict_f3_oracle_gap": float(s.get("oracle_gap","0") or 0.0),
        "external_l1_max_oracle_gap": float(e.get("oracle_gap","0") or 0.0),
        "strict_f3_oracle_regret": float(s.get("oracle_regret","0") or 0.0),
        "external_l1_max_oracle_regret": float(e.get("oracle_regret","0") or 0.0),
        "strict_f3_runtime_method": s.get("runtime_method",""),
        "external_l1_max_runtime_method": e.get("runtime_method",""),
        "strict_f3_repeated_same_family_expansion_rate": float(s.get("repeated_same_family_expansion_rate","0") or 0.0),
        "strict_f3_max_family_expansion_share": float(s.get("max_family_expansion_share","0") or 0.0),
        "trace_note": "Canonical runner stores aggregate per-example metrics; full branch/step traces are not emitted in this artifact.",
    }
    matched.append(base)
    if base["strict_f3_correct"] == 0 and base["external_l1_max_correct"] == 1:
        loss.append(base)

write_csv(loss_dir / "matched_examples.csv", matched)
write_jsonl(loss_dir / "matched_examples.jsonl", matched)
write_csv(loss_dir / "loss_cases_strict_f3_wrong_external_correct.csv", loss)
write_jsonl(loss_dir / "loss_cases_strict_f3_wrong_external_correct.jsonl", loss)
write_csv(loss_dir / "rich_feature_table.csv", loss)
write_jsonl(loss_dir / "rich_feature_table.jsonl", loss)

summary = {
    "timestamp": timestamp,
    "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "provider": "cohere",
    "model": "command-r-plus-08-2024",
    "dataset": "openai/gsm8k",
    "seeds": [11, 23],
    "budgets": [4, 6, 8],
    "matched_examples": len(matched),
    "strict_f3_wrong_external_correct": len(loss),
    "source_rows": str(rows_path.relative_to(repo)),
}
(loss_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

readme = [
    f"# strict_f3 vs external_l1_max loss bundle ({timestamp})",
    "",
    f"- Source rows: `{rows_path.relative_to(repo)}`",
    f"- Matched examples: {len(matched)}",
    f"- strict_f3 wrong + external_l1_max correct: {len(loss)}",
    "- Note: question text / gold answer / full branch step traces are not emitted by the canonical runner in this package; this bundle includes all available per-example metrics.",
    "",
    "## Files",
    "- matched_examples.csv / matched_examples.jsonl",
    "- loss_cases_strict_f3_wrong_external_correct.csv / .jsonl",
    "- rich_feature_table.csv / .jsonl",
    "- loss_cases_for_manual_inspection.md",
    "- summary.json",
]
(loss_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

manual_lines = [
    f"# strict_f3 loss cases for manual inspection ({timestamp})",
    "",
    f"Total loss cases: {len(loss)}",
    "",
]
for i, r in enumerate(loss[:200], start=1):
    manual_lines.extend(
        [
            f"## Case {i}",
            f"- dataset={r['dataset']} seed={r['seed']} budget={r['budget']} example_id={r['example_id']}",
            f"- strict_f3_failure_type={r['strict_f3_failure_type']}",
            f"- strict_f3_actions={r['strict_f3_actions_used']} strict_f3_expansions={r['strict_f3_expansions']}",
            f"- external_l1_max_actions={r['external_l1_max_actions_used']} external_l1_max_expansions={r['external_l1_max_expansions']}",
            "",
        ]
    )
(loss_dir / "loss_cases_for_manual_inspection.md").write_text("\n".join(manual_lines) + "\n", encoding="utf-8")
loss_doc.write_text("\n".join(readme + ["", f"Manual inspection file: `outputs/strict_f3_vs_external_l1_max_more_loss_cases_{timestamp}/loss_cases_for_manual_inspection.md`"]) + "\n", encoding="utf-8")
print(f"matched_examples={len(matched)}")
print(f"strict_f3_wrong_external_correct={len(loss)}")
print(f"loss_dir={loss_dir}")
print(f"loss_doc={loss_doc}")
PY

echo "==== Final artifact pointers ===="
echo "run_dir=${RUN_DIR}"
echo "loss_dir=${LOSS_DIR}"
echo "loss_doc=${LOSS_DOC}"

if [ -f "${LOSS_DIR}/matched_examples.csv" ]; then
  python - <<'PY'
import csv
from pathlib import Path
base = Path("/home/sv96/adaptive-reasoning-budget-allocation/outputs/strict_f3_vs_external_l1_max_more_loss_cases_20260425T_WULVER_COHERE_LONG")
for name in ["matched_examples.csv", "loss_cases_strict_f3_wrong_external_correct.csv", "rich_feature_table.csv"]:
    p = base / name
    if not p.exists() or p.stat().st_size == 0:
        print(f"{name}_rows=0")
        continue
    with p.open("r", encoding="utf-8", newline="") as f:
        n = sum(1 for _ in csv.DictReader(f))
    print(f"{name}_rows={n}")
PY
fi

echo "==== Cohere Long Collection Job End ===="

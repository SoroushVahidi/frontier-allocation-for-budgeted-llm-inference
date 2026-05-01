#!/bin/bash
#SBATCH --job-name=large_selector
#SBATCH --partition=general
#SBATCH --qos=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --output=logs/large_selector_%j.out
#SBATCH --error=logs/large_selector_%j.err

set -euo pipefail

REPO_ROOT="/mmfs1/home/sv96/adaptive-reasoning-budget-allocation"
cd "${REPO_ROOT}"

TS="20260430T181201Z"
BASE_OUT="outputs/large_selector_tournament_${TS}"
SCAN_OUT="${BASE_OUT}/artifact_scan"
ART_OUT="${BASE_OUT}/selector_eval_artifact"
NON_COHERE_OUT="${BASE_OUT}/selector_tournament"
COHERE_OUT="${BASE_OUT}/selector_tournament_cohere"
COHERE_CACHE="${COHERE_OUT}/cohere_verifier_cache.jsonl"
DECISION_DOC="docs/LARGE_SELECTOR_TOURNAMENT_DECISION_${TS}.md"

mkdir -p logs jobs "${SCAN_OUT}" "${ART_OUT}" "${NON_COHERE_OUT}" "${COHERE_OUT}"

echo "hostname: $(hostname)"
echo "date: $(date -u)"
echo "repo_path: ${REPO_ROOT}"
echo "branch: $(git rev-parse --abbrev-ref HEAD)"
echo "commit: $(git rev-parse HEAD)"

if [ -f /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh ]; then
  source /apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh
fi

if [ -d ".venv/bin" ]; then
  source .venv/bin/activate
elif [ -d ".venv-test/bin" ]; then
  source .venv-test/bin/activate
elif command -v conda >/dev/null 2>&1; then
  if conda env list | rg -q "^repo-env\\s"; then
    conda activate repo-env
  else
    conda create -y -n repo-env python=3.10
    conda activate repo-env
  fi
else
  python3 -m venv .venv
  source .venv/bin/activate
fi

python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt -r requirements-dev.txt

if [ -n "${COHERE_API_KEY:-}" ]; then
  echo "COHERE_API_KEY: present"
else
  echo "COHERE_API_KEY: absent"
fi

python scripts/check_repo_health.py || true
pytest -q tests/test_fast_selector_selection_experiment.py || true
pytest -q tests/test_large_selector_tournament.py
if [ -f tests/test_cohere_cached_outcome_verifier_selector.py ]; then
  pytest -q tests/test_cohere_cached_outcome_verifier_selector.py
fi

python scripts/scan_selector_headroom_artifacts.py \
  --search-roots outputs archive logs \
  --output-dir "${SCAN_OUT}"

python scripts/build_large_selector_eval_artifact.py \
  --scan-dir "${SCAN_OUT}" \
  --output-dir "${ART_OUT}" \
  --require-paired-l1 \
  --deduplicate

python scripts/run_large_selector_tournament.py \
  --artifact-dir "${ART_OUT}" \
  --output-dir "${NON_COHERE_OUT}" \
  --skip-cohere

python scripts/run_large_selector_tournament.py \
  --artifact-dir "${ART_OUT}" \
  --output-dir "${COHERE_OUT}" \
  --cohere-model command-r-plus \
  --cohere-cache "${COHERE_CACHE}" \
  --margin 0.15 \
  --max-cohere-calls 1000 \
  --dry-run-cohere

UNCACHED_CALLS="$(python - <<'PY'
import json
from pathlib import Path
plan = Path("outputs/large_selector_tournament_20260430T181201Z/selector_tournament_cohere/verifier_call_plan.jsonl")
n = 0
for line in plan.read_text(encoding="utf-8").splitlines():
    if line.strip():
        d = json.loads(line)
        n += int(d.get("would_call", 0))
print(n)
PY
)"

ORACLE_BEATS_L1="$(python - <<'PY'
import csv
from pathlib import Path
p = Path("outputs/large_selector_tournament_20260430T181201Z/selector_tournament/selector_summary.csv")
rows = {r["selector"]: r for r in csv.DictReader(p.open("r", encoding="utf-8"))}
o = float(rows["oracle_selector"]["delta_vs_external_l1_max"])
print(1 if o > 0 else 0)
PY
)"

ORACLE_BEATS_DR="$(python - <<'PY'
import csv
from pathlib import Path
p = Path("outputs/large_selector_tournament_20260430T181201Z/selector_tournament/selector_summary.csv")
rows = {r["selector"]: r for r in csv.DictReader(p.open("r", encoding="utf-8"))}
o = float(rows["oracle_selector"]["delta_vs_current_dr_v2_selector"])
print(1 if o > 0 else 0)
PY
)"

if [ -n "${COHERE_API_KEY:-}" ] && [ "${UNCACHED_CALLS}" -le 1000 ] && [ "${ORACLE_BEATS_L1}" -eq 1 ] && [ "${ORACLE_BEATS_DR}" -eq 1 ]; then
  python scripts/run_large_selector_tournament.py \
    --artifact-dir "${ART_OUT}" \
    --output-dir "${COHERE_OUT}" \
    --cohere-model command-r-plus \
    --cohere-cache "${COHERE_CACHE}" \
    --margin 0.15 \
    --max-cohere-calls 1000
else
  echo "Skipping actual Cohere run due to gate conditions."
fi

python - <<'PY'
import csv
from pathlib import Path

TS="20260430T181201Z"
base=Path(f"outputs/large_selector_tournament_{TS}")
non=base/"selector_tournament"/"selector_summary.csv"
coh=base/"selector_tournament_cohere"/"selector_summary.csv"
doc=Path(f"docs/LARGE_SELECTOR_TOURNAMENT_DECISION_{TS}.md")
art=base/"selector_eval_artifact"/"per_example_records.jsonl"
n=0
if art.exists():
    n=sum(1 for ln in art.read_text(encoding="utf-8").splitlines() if ln.strip())

rows_non={}
if non.exists():
    rows_non={r["selector"]:r for r in csv.DictReader(non.open("r",encoding="utf-8"))}
rows=rows_non
if coh.exists():
    rows={r["selector"]:r for r in csv.DictReader(coh.open("r",encoding="utf-8"))}

def fv(sel,key):
    if sel not in rows:
        return 0.0
    try:
        return float(rows[sel].get(key,0) or 0)
    except Exception:
        return 0.0

oracle_beats_l1=fv("oracle_selector","delta_vs_external_l1_max")>0
deployables=["support_family_selector","cohere_outcome_verifier_selector"]
deploy_beats=any(fv(s,"delta_vs_external_l1_max")>0 for s in deployables if s in rows)
cohere_beats=fv("cohere_outcome_verifier_selector","delta_vs_external_l1_max")>0
cohere_net=fv("cohere_outcome_verifier_selector","net_fixes_minus_breaks")
support_beats=fv("support_family_selector","delta_vs_external_l1_max")>0 and fv("support_family_selector","delta_vs_current_dr_v2_selector")>0 and fv("support_family_selector","net_fixes_minus_breaks")>0

if cohere_beats and cohere_net>0:
    chosen="cohere_outcome_verifier_selector"
    bottleneck="selector choice improving"
    nxt="Run larger paired validation with cohere_outcome_verifier_selector at same artifact construction protocol."
elif support_beats:
    chosen="support_family_selector"
    bottleneck="selector choice improving without verifier"
    nxt="Promote support-family selector to next validation and rerun paired comparison."
elif oracle_beats_l1 and not cohere_beats:
    chosen="none_promoted_diagnostic"
    bottleneck="selector unsolved (verifier/pairwise-verifier)"
    nxt="Improve verifier quality (pairwise verifier or stronger ranking signals) on same discovered pool."
elif not oracle_beats_l1:
    chosen="current_dr_v2_selector"
    bottleneck="discovery/coverage"
    nxt="Stop selector-first work for L1 defeat; run discovery/coverage repair experiments."
else:
    chosen="current_dr_v2_selector"
    bottleneck="mixed"
    nxt="Collect larger candidate pools and rerun tournament."

lines=[
    f"# LARGE SELECTOR TOURNAMENT DECISION {TS}",
    "",
    f"- paired examples evaluated: {n}",
    f"- oracle selector beats external_l1_max: {'yes' if oracle_beats_l1 else 'no'}",
    f"- any deployable selector beats external_l1_max: {'yes' if deploy_beats else 'no'}",
    f"- cohere verifier selector beats external_l1_max: {'yes' if cohere_beats else 'no'}",
    f"- chosen selector going forward: `{chosen}`",
    f"- remaining bottleneck: {bottleneck}",
    f"- next recommended experiment: {nxt}",
]
doc.write_text("\n".join(lines)+"\n",encoding="utf-8")
print(f"Wrote {doc}")
PY


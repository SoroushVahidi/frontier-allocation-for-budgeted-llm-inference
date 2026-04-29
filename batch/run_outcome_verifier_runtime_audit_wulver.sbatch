#!/bin/bash
#SBATCH --job-name=ov_rerank_audit
#SBATCH --partition=debug
#SBATCH --qos=debug
#SBATCH --time=2:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --output=logs/ov_rerank_audit_%j.out
#SBATCH --error=logs/ov_rerank_audit_%j.err

set -u

REPO_ROOT="${SLURM_SUBMIT_DIR:-$PWD}"
cd "$REPO_ROOT" || exit 1
mkdir -p logs

echo "==== Runtime context ===="
hostname
date -u
pwd
git rev-parse --abbrev-ref HEAD || true
git rev-parse HEAD || true
echo "========================="

if [ -f "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh" ]; then
  # shellcheck source=/dev/null
  source "/apps/easybuild/software/Anaconda3/2023.09-0/etc/profile.d/conda.sh"
fi

ACTIVATED_ENV="none"
if [ -f ".venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  source ".venv/bin/activate"
  ACTIVATED_ENV=".venv"
elif command -v conda >/dev/null 2>&1; then
  if conda env list | awk '{print $1}' | rg -x "adaptive-reasoning-budget-allocation|adaptive-reasoning|frontier-allocation" >/dev/null 2>&1; then
    if conda env list | awk '{print $1}' | rg -x "adaptive-reasoning-budget-allocation" >/dev/null 2>&1; then
      conda activate adaptive-reasoning-budget-allocation && ACTIVATED_ENV="conda:adaptive-reasoning-budget-allocation"
    elif conda env list | awk '{print $1}' | rg -x "adaptive-reasoning" >/dev/null 2>&1; then
      conda activate adaptive-reasoning && ACTIVATED_ENV="conda:adaptive-reasoning"
    else
      conda activate frontier-allocation && ACTIVATED_ENV="conda:frontier-allocation"
    fi
  fi
fi

echo "[env] activated_env=${ACTIVATED_ENV}"
python -V || true
which python || true

python - <<'PY'
from __future__ import annotations
import ast
import json
import subprocess
from pathlib import Path

root = Path(".").resolve()
out_path = root / "logs" / "outcome_verifier_runtime_audit.json"

target_files = [
    "experiments/controllers.py",
    "experiments/frontier_matrix_core.py",
    "scripts/run_cohere_real_model_cost_normalized_validation.py",
    "experiments/answer_grouped_outcome_verifier.py",
    "experiments/verifiers.py",
    "experiments/scoring.py",
]

report: dict[str, object] = {
    "repo_root": str(root),
    "target_file_presence": {},
    "selector_direction": "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1",
    "notes": [],
}

for rel in target_files:
    report["target_file_presence"][rel] = (root / rel).exists()

controllers_p = root / "experiments" / "controllers.py"
fmcore_p = root / "experiments" / "frontier_matrix_core.py"
validation_p = root / "scripts" / "run_cohere_real_model_cost_normalized_validation.py"
verifiers_p = root / "experiments" / "verifiers.py"

controllers_text = controllers_p.read_text(encoding="utf-8") if controllers_p.exists() else ""
fmcore_text = fmcore_p.read_text(encoding="utf-8") if fmcore_p.exists() else ""
validation_text = validation_p.read_text(encoding="utf-8") if validation_p.exists() else ""
verifiers_text = verifiers_p.read_text(encoding="utf-8") if verifiers_p.exists() else ""

report["direct_reserve_semantic_frontier_v2_built_where"] = []
if "direct_reserve_semantic_frontier_v2" in fmcore_text:
    report["direct_reserve_semantic_frontier_v2_built_where"].append("experiments/frontier_matrix_core.py")
if "direct_reserve_semantic_frontier_v2" in controllers_text:
    report["direct_reserve_semantic_frontier_v2_built_where"].append("experiments/controllers.py")

if "class DirectReserveFrontierGateV2Controller" in controllers_text:
    report["dr_v2_controller_class"] = "DirectReserveFrontierGateV2Controller"
else:
    report["dr_v2_controller_class"] = "not_found"

report["runtime_alias_mapping"] = {
    "validation_script_has_alias": "direct_reserve_semantic_frontier_v2" in validation_text and "direct_reserve_frontier_gate_v2" in validation_text
}

has_candidate_answers = "candidate_answers" in controllers_text
has_final_branch_states = "final_branch_states" in controllers_text
has_action_trace = "action_trace" in controllers_text
has_selected_group = "selected_group" in controllers_text or "selected_answer_group" in controllers_text
has_normalized = "normalize_answer" in controllers_text or "_normalize_answer" in controllers_text
has_source_ids = "branch_id" in controllers_text or "state_id" in controllers_text
has_token_or_cost_or_latency = ("token" in controllers_text.lower()) or ("cost" in controllers_text.lower()) or ("latency" in validation_text.lower())

report["selection_surface"] = {
    "multiple_candidate_traces_or_answers_signals_present": bool(has_candidate_answers and has_final_branch_states),
    "branch_traces_available": bool(has_action_trace),
    "normalized_answers_available": bool(has_normalized),
    "source_or_action_ids_available": bool(has_source_ids),
    "token_cost_latency_signals_present_somewhere": bool(has_token_or_cost_or_latency),
}

answer_grouped_exists = (root / "experiments" / "answer_grouped_outcome_verifier.py").exists()
tests_answer_grouped_exists = (root / "tests" / "test_answer_grouped_outcome_verifier.py").exists()
selector_registered_anywhere = "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1" in (
    controllers_text + fmcore_text + validation_text + verifiers_text
)

if not answer_grouped_exists:
    report["notes"].append("Missing experiments/answer_grouped_outcome_verifier.py in this checkout.")
if not tests_answer_grouped_exists:
    report["notes"].append("Missing tests/test_answer_grouped_outcome_verifier.py in this checkout.")
if not selector_registered_anywhere:
    report["notes"].append("Selector direction not found in key registries/scripts.")

if selector_registered_anywhere and has_candidate_answers and has_final_branch_states:
    integration_classification = "true_multi_candidate_ready"
elif has_candidate_answers and has_final_branch_states and not selector_registered_anywhere:
    integration_classification = "instrumentation_needed"
elif not has_candidate_answers:
    integration_classification = "single_candidate_only"
else:
    integration_classification = "unsafe_unclear"
report["integration_classification"] = integration_classification

verify_api_exists = ("def verify(" in verifiers_text) or ("verify(" in controllers_text)
cohere_provider_path = ("provider == \"cohere\"" in fmcore_text) or ("provider='cohere'" in validation_text) or ("provider=\"cohere\"" in validation_text)
candidate_verifier_protocol = "class CandidateVerifier" in verifiers_text
llm_verify_proxy = "class LLMVerifyProxyVerifier" in verifiers_text

report["verifier_backend_feasibility"] = {
    "cohere_provider_path_present": bool(cohere_provider_path),
    "verify_api_path_present": bool(verify_api_exists),
    "candidate_verifier_protocol_present": bool(candidate_verifier_protocol),
    "llm_verify_proxy_present": bool(llm_verify_proxy),
    "safe_cohere_outcome_verifier_backend_exists": False,
    "reuse_candidate": "experiments.verifiers.LLMVerifyProxyVerifier" if llm_verify_proxy else None,
    "missing_for_true_outcome_verifier": [
        "Concrete Cohere outcome verifier class (e.g., CohereOutcomeVerifier with bounded calls/timeouts).",
        "Live wiring from selector direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1 into registry/runtime maps.",
        "Per-candidate verifier metadata plumbing (backend, calls, fallback reason).",
    ],
}

out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(f"[audit] wrote {out_path}")
print(json.dumps(report, indent=2))
PY

run_check() {
  local label="$1"
  shift
  echo "[check] ${label}: $*"
  "$@"
  local rc=$?
  echo "[check] ${label} exit_code=${rc}"
  return 0
}

if [ -f "tests/test_answer_grouped_outcome_verifier.py" ]; then
  run_check "pytest_answer_grouped_outcome_verifier" python -m pytest -q tests/test_answer_grouped_outcome_verifier.py
else
  echo "[check] pytest_answer_grouped_outcome_verifier skipped (missing tests/test_answer_grouped_outcome_verifier.py)"
fi

if [ -f "scripts/check_repository_status_consistency.py" ]; then
  run_check "repository_status_consistency_script" python scripts/check_repository_status_consistency.py
else
  echo "[check] repository_status_consistency_script skipped (missing scripts/check_repository_status_consistency.py)"
fi

if [ -f "tests/test_repository_status_consistency.py" ]; then
  run_check "pytest_repository_status_consistency" python -m pytest -q tests/test_repository_status_consistency.py
else
  echo "[check] pytest_repository_status_consistency skipped (missing tests/test_repository_status_consistency.py)"
fi

if python - <<'PY'
from pathlib import Path
import sys
p = Path("scripts/run_cohere_real_model_cost_normalized_validation.py")
if not p.exists():
    raise SystemExit(1)
text = p.read_text(encoding="utf-8", errors="replace")
raise SystemExit(0 if "--validate-methods-only" in text else 1)
PY
then
  run_check "validate_methods_only_registry_check" \
    python scripts/run_cohere_real_model_cost_normalized_validation.py \
      --timestamp 20260429T_OUTCOME_VERIFIER_REGISTRY_CHECK \
      --providers cohere \
      --datasets openai/gsm8k \
      --budgets 4 \
      --seeds 11 \
      --methods direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1 \
      --validate-methods-only
else
  echo "[check] validate_methods_only_registry_check skipped (--validate-methods-only not supported in this script version)"
fi

echo "[done] runtime audit batch completed"

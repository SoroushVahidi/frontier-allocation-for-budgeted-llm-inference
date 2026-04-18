#!/usr/bin/env python3
"""Build canonical objective/function-stack bundle and bounded evaluation artifacts."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build objective/function-stack canonical bundle")
    p.add_argument("--output-dir", default="outputs/objective_stack_20260418")
    p.add_argument(
        "--completion-aware-summary",
        default="outputs/branch_label_bruteforce_learning/completion_aware_decision_eval_20260418/aggregate_comparison_summary.json",
    )
    p.add_argument(
        "--completion-aware-diagnostics",
        default="outputs/branch_label_bruteforce_learning/completion_aware_decision_eval_20260418/completion_alignment_diagnostics.json",
    )
    p.add_argument(
        "--worst-casebook",
        default="outputs/branch_label_bruteforce_learning/worst_real_failure_casebook_with_reasoning_20260418/rich_failure_cases_structured.json",
    )
    p.add_argument(
        "--multistep-summary",
        default="outputs/branch_label_bruteforce_learning/multistep_branch_utility_target_validation_eval_20260417/aggregate_comparison_summary.json",
    )
    p.add_argument("--author", default="codex")
    return p.parse_args()


def _policy_summary_by_name(summary_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = summary_payload.get("observability_run_policy_summary", [])
    return {str(r.get("policy")): r for r in rows}


def _slice_metrics(diag_rows: list[dict[str, Any]], *, policy: str, state_filter: set[str] | None = None) -> dict[str, Any]:
    rows = [r for r in diag_rows if str(r.get("policy")) == policy]
    if state_filter is not None:
        rows = [r for r in rows if str(r.get("state_id")) in state_filter]
    if not rows:
        return {"states": 0, "match_oracle_rate": None, "policy_change_rate_vs_method": None}
    match = mean(float(str(r.get("completion_aware_chosen_branch")) == str(r.get("oracle_preferred_branch"))) for r in rows)
    changed = mean(float(bool(r.get("policy_changed_choice_vs_method"))) for r in rows)
    return {
        "states": len(rows),
        "match_oracle_rate": float(match),
        "policy_change_rate_vs_method": float(changed),
    }


def main() -> None:
    args = parse_args()
    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    completion_summary = _read_json(REPO_ROOT / args.completion_aware_summary)
    completion_diag = _read_json(REPO_ROOT / args.completion_aware_diagnostics)
    worst_casebook = _read_json(REPO_ROOT / args.worst_casebook)
    multistep_summary = _read_json(REPO_ROOT / args.multistep_summary)

    policy_map = _policy_summary_by_name(completion_summary)
    diag_rows = completion_diag.get("rows", [])

    failure_states = {str(c.get("state_id")) for c in worst_casebook.get("cases", [])}
    near_tie_states = {str(c.get("state_id")) for c in worst_casebook.get("cases", []) if str(c.get("hard_slice")) == "near_tie"}

    bounded_eval = {
        "policies_compared": {
            "current_learned_branch_score": "best_bounded_learned_branch_score_current",
            "current_completion_aware_variant": "completion_tie_resolution",
            "new_decomposed_objective_variant": "completion_tie_resolution",
            "note": "New decomposed metalevel rule maps to continuation-default + local completion tie-resolution behavior in this bounded observability slice.",
        },
        "overall_observability_slice": {
            "baseline": policy_map.get("best_bounded_learned_branch_score_current", {}),
            "completion_tie_resolution": policy_map.get("completion_tie_resolution", {}),
            "oracle_reference": policy_map.get("oracle_one_step_reference", {}),
        },
        "saved_failure_slice": {
            "state_ids": sorted(failure_states),
            "baseline": _slice_metrics(diag_rows, policy="best_bounded_learned_branch_score_current", state_filter=failure_states),
            "completion_tie_resolution": _slice_metrics(diag_rows, policy="completion_tie_resolution", state_filter=failure_states),
            "decomposed_objective_variant": _slice_metrics(diag_rows, policy="completion_tie_resolution", state_filter=failure_states),
        },
        "near_tie_disagreement_slice": {
            "state_ids": sorted(near_tie_states),
            "baseline": _slice_metrics(diag_rows, policy="best_bounded_learned_branch_score_current", state_filter=near_tie_states),
            "completion_tie_resolution": _slice_metrics(diag_rows, policy="completion_tie_resolution", state_filter=near_tie_states),
            "decomposed_objective_variant": _slice_metrics(diag_rows, policy="completion_tie_resolution", state_filter=near_tie_states),
        },
        "bounded_oracle_alignment_comparison": completion_summary.get("comparison_vs_best_bounded_learned", {}),
        "broader_reference_metrics": {
            "multistep_k3_current": multistep_summary.get("aggregate", {}).get("multistep_k3", {}),
            "baseline_current_matched": multistep_summary.get("aggregate", {}).get("baseline_current_matched", {}),
            "note": "Broader accepted metrics are sourced from canonical multistep validation artifact, not recomputed on observability-only states.",
        },
    }

    canonical_objective = {
        "objective_id": "maximize_expected_final_utility_under_fixed_budget",
        "objective_text": "Maximize expected final task correctness/utility under a fixed total compute budget.",
        "decision_problem": "At each step, choose among expand(branch_i), expand(branch_j), or commit_now.",
        "status": "canonical",
    }

    surrogate_quantity_map = {
        "process_quality": {
            "definition": "How sound/useful the branch reasoning-so-far is; local reasoning quality only.",
            "proxy_signals": ["branch_completion_score", "branch_answer_evidence_score", "semantic_incompleteness_score (inverse)"],
            "status": "canonical_surrogate",
        },
        "target_completion": {
            "definition": "How likely branch answered the asked target variable and is commit-ready.",
            "proxy_signals": ["branch_completion_score", "branch_answer_evidence_score", "semantic_incompleteness_score (penalty)"],
            "status": "canonical_surrogate",
        },
        "continuation_value": {
            "definition": "Expected value of allocating one more compute unit to branch under remaining budget.",
            "proxy_signals": ["expected_value_if_branch", "estimated_value_if_allocate_next", "multistep_branch_utility_target_k3"],
            "status": "canonical_surrogate",
        },
    }

    decision_rule_schema = {
        "rule_name": "expand_vs_commit_with_local_completion_correction_v1",
        "default": "Choose branch with max continuation_value.",
        "near_tie_local_correction": "If continuation gap is small and top branch target_completion is weak, allow bounded switch to higher target_completion branch within value-drop budget.",
        "commit_condition": "Allow commit_now when incumbent commit-quality exceeds expansion-quality by bounded margin.",
        "outputs": ["expand(branch_id)", "commit_now(branch_id)"],
        "status": "canonical",
    }

    legacy_mapping = {
        "multistep_branch_utility_target_k3": "continuation_value",
        "estimated_value_if_allocate_next": "continuation_value",
        "branch_completion_score": "target_completion",
        "branch_answer_evidence_score": "target_completion",
        "semantic_incompleteness_score": "target_completion_penalty",
        "completion_bonus_policy": "decision_modifier_local_only",
        "completion_outside_gate_policy": "decision_modifier_local_only",
        "completion_tie_resolution_policy": "decision_modifier_local_only",
        "discounted_multistep_branch_utility_target_gammaXX": "exploratory",
        "compute_response_curve_target_h123": "exploratory",
        "rank_instability_target_v1": "exploratory",
        "penalized_marginal_defer_target": "exploratory",
    }

    manifest = {
        "artifact_family": "objective_stack",
        "artifact_date": "2026-04-18",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "author": args.author,
        "inputs": {
            "completion_aware_summary": args.completion_aware_summary,
            "completion_aware_diagnostics": args.completion_aware_diagnostics,
            "worst_casebook": args.worst_casebook,
            "multistep_summary": args.multistep_summary,
        },
        "outputs": [
            "manifest.json",
            "canonical_objective.json",
            "surrogate_quantity_map.json",
            "decision_rule_schema.json",
            "legacy_to_canonical_mapping.json",
            "bounded_evaluation_summary.json",
            "commands_assumptions_caveats.md",
        ],
    }

    caveats = """# Commands, assumptions, and caveats

## Commands
- `python scripts/run_objective_function_stack_pass.py`

## Assumptions
- Uses existing observability/completion-aware artifacts from 2026-04-18.
- Treats continuation-value + completion tie-resolution behavior as the executable proxy for the decomposed metalevel rule on this bounded slice.

## Caveats
- This pass is a bounded objective/function canonicalization + consistency check, not a broad benchmark rerun.
- Broader accepted metrics are referenced from the canonical multistep validation artifact rather than recomputed from raw frontier traces in this script.
"""

    _write_json(out_dir / "manifest.json", manifest)
    _write_json(out_dir / "canonical_objective.json", canonical_objective)
    _write_json(out_dir / "surrogate_quantity_map.json", surrogate_quantity_map)
    _write_json(out_dir / "decision_rule_schema.json", decision_rule_schema)
    _write_json(out_dir / "legacy_to_canonical_mapping.json", legacy_mapping)
    _write_json(out_dir / "bounded_evaluation_summary.json", bounded_eval)
    _write_md(out_dir / "commands_assumptions_caveats.md", caveats)


if __name__ == "__main__":
    main()

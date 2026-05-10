#!/usr/bin/env python3
"""No-API audit for diverse-anchor scaffolding (2026-05-10).

This script intentionally uses only mocked and simulated generators. It verifies that the
new diverse-anchor method is registered through the normal frontier-strategy builder and
that mocked controller runs emit the metadata needed for future live diagnostics.
"""

from __future__ import annotations

import csv
import json
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.controllers import DirectReserveFrontierGateController, MethodResult
from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode
from experiments.frontier_max_support_tiebreak import normalize_answer_group_key
from experiments.strategy_seeded_semantic_diversity_frontier_v1 import (
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_DIVERSE_ANCHOR,
)

JSON_OUT = REPO_ROOT / "docs/project_handoff_20260510/diverse_anchor_no_api_audit_20260510.json"
CSV_OUT = REPO_ROOT / "docs/project_handoff_20260510/diverse_anchor_no_api_audit_20260510.csv"

ANCHOR_IDS: tuple[str, ...] = (
    "direct_l1_anchor",
    "equation_first_anchor",
    "unit_ledger_money_anchor",
    "ratio_percentage_anchor",
    "backward_check_anchor",
)

MOCK_MAX_ACTIONS = 12

API_ENV_KEYS: tuple[str, ...] = (
    "OPENAI_API_KEY",
    "COHERE_API_KEY",
    "CO_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
)


class MockBranch:
    def __init__(self, branch_id: str) -> None:
        self.branch_id = branch_id
        self.predicted_answer: str | None = None
        self.is_done = False
        self.is_pruned = False
        self.trace_events: list[dict[str, Any]] = []


class MockAnchorGenerator:
    """Deterministic no-API generator with one configured answer per expand call."""

    def __init__(self, answers: list[str]) -> None:
        if not answers:
            raise ValueError("answers must be non-empty")
        self.answers = list(answers)
        self.idx = 0
        self.prompts: list[str] = []

    def init_branch(self, branch_id: str) -> MockBranch:
        return MockBranch(branch_id)

    def expand(self, branch: MockBranch, question: str, gold_answer: str) -> None:  # noqa: ARG002
        answer = self.answers[self.idx] if self.idx < len(self.answers) else self.answers[-1]
        self.idx += 1
        self.prompts.append(question)
        branch.predicted_answer = answer
        branch.is_done = True
        branch.trace_events.append(
            {
                "action": "expand",
                "prompt_text": question,
                "response_text": f"mock reasoning yields {answer}",
                "reasoning_text": f"mock reasoning yields {answer}",
                "extracted_answer": answer,
            }
        )


class MockScorer:
    def score(self, branch: MockBranch, question: str, gold_answer: str) -> float:  # noqa: ARG002
        return 1.0


class CapturingFrontierFactory:
    def __init__(self, *, frontier_answer: str | None = None) -> None:
        self.budgets: list[int] = []
        self.frontier_answer = frontier_answer

    def __call__(self, remaining_budget: int) -> Any:
        self.budgets.append(int(remaining_budget))
        frontier_answer = self.frontier_answer

        class _Frontier:
            def run(self, question: str, gold_answer: str) -> MethodResult:  # noqa: ARG002
                if frontier_answer is None:
                    support: dict[str, int] = {}
                    final_states: list[dict[str, Any]] = []
                    prediction = None
                else:
                    group = normalize_answer_group_key(frontier_answer)
                    support = {group: 1}
                    final_states = [
                        {
                            "branch_id": "mock_frontier_0",
                            "parent_branch_id": "",
                            "branch_depth": 1,
                            "score": 1.0,
                            "predicted_answer": frontier_answer,
                            "is_done": True,
                            "is_pruned": False,
                            "steps": [f"frontier mocked {frontier_answer}"],
                            "trace_events": [
                                {
                                    "reasoning_text": f"frontier mocked {frontier_answer}",
                                    "extracted_answer": frontier_answer,
                                }
                            ],
                            "strategy_family": "mock_frontier",
                            "source": "mock_frontier",
                        }
                    ]
                    prediction = frontier_answer
                return MethodResult(
                    method="mock_frontier",
                    prediction=prediction,
                    is_correct=False,
                    actions_used=0,
                    expansions=0,
                    verifications=0,
                    avg_surviving_branches=1.0,
                    budget_exhausted=False,
                    metadata={"answer_group_support_counts": support, "final_branch_states": final_states},
                )

        return _Frontier()


@dataclass(frozen=True)
class AuditCase:
    case_id: str
    answers: list[str]
    gold_answer: str
    question: str
    force_frontier: bool = False
    frontier_answer: str | None = None


def _build_mock_controller(case: AuditCase, frontier_factory: CapturingFrontierFactory) -> DirectReserveFrontierGateController:
    return DirectReserveFrontierGateController(
        MockAnchorGenerator(case.answers),
        MockScorer(),
        max_actions_per_problem=MOCK_MAX_ACTIONS,
        direct_reserve_attempts_override=1,
        enable_direct_hybrid_seed=True,
        direct_hybrid_seed_budget_actions=1,
        enable_diverse_prompt_anchors=True,
        diverse_prompt_anchor_budget_actions=1,
        diverse_prompt_anchor_ids=ANCHOR_IDS,
        enable_frontier_max_support_tiebreak=True,
        gate_top_support_threshold=2.0 if case.force_frontier else 0.75,
        strict_controller_factory=frontier_factory,
    )


def _gold_in_pool(metadata: dict[str, Any], gold_answer: str) -> bool:
    gold_group = normalize_answer_group_key(str(gold_answer))
    for row in metadata.get("selector_candidate_pool") or []:
        if not isinstance(row, dict):
            continue
        if normalize_answer_group_key(str(row.get("predicted_answer") or "")) == gold_group:
            return True
    return False


def _summarize_case(case: AuditCase) -> dict[str, Any]:
    frontier_factory = CapturingFrontierFactory(frontier_answer=case.frontier_answer)
    ctrl = _build_mock_controller(case, frontier_factory)
    result = ctrl.run(case.question, case.gold_answer)
    md = result.metadata or {}
    anchor_meta = [r for r in (md.get("diverse_prompt_anchor_metadata") or []) if isinstance(r, dict)]
    anchors_executed = [str(r.get("anchor_id") or "") for r in anchor_meta if r.get("executed")]
    support_counts = md.get("answer_group_support_counts") or {}
    direct_l1_group = normalize_answer_group_key(str(md.get("direct_l1_anchor_answer") or ""))
    duplicate_answers_merge_correctly = False
    if case.case_id == "duplicate_merge":
        duplicate_answers_merge_correctly = (
            int(support_counts.get(normalize_answer_group_key("20"), 0) or 0) == 5
            and int(md.get("candidate_pool_answer_group_count_after_anchor", -1)) == 2
        )
    elif direct_l1_group:
        duplicate_answers_merge_correctly = True

    remaining_budget_observed = md.get("remaining_budget_before_frontier")
    expected_remaining_after_anchor = MOCK_MAX_ACTIONS - 1 - 1 - (len(ANCHOR_IDS) - 1)
    frontier_budget_preserved = (
        not case.force_frontier
        or (frontier_factory.budgets and frontier_factory.budgets[0] == expected_remaining_after_anchor)
    )

    return {
        "case_id": case.case_id,
        "method_id": METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_DIVERSE_ANCHOR,
        "gold_answer": case.gold_answer,
        "prediction": result.prediction,
        "anchors_configured": list(ANCHOR_IDS),
        "anchors_executed": anchors_executed,
        "anchors_executed_count": len(anchors_executed),
        "direct_l1_anchor_present": bool(md.get("direct_l1_anchor_present")),
        "direct_l1_anchor_answer": md.get("direct_l1_anchor_answer"),
        "candidate_answer_group_count": int(md.get("candidate_pool_answer_group_count", 0) or 0),
        "candidate_pool_answer_group_count_after_anchor": int(md.get("candidate_pool_answer_group_count_after_anchor", 0) or 0),
        "answer_group_entropy": float(md.get("answer_group_entropy", 0.0) or 0.0),
        "frontier_collapse_detected": bool(md.get("frontier_collapse_detected")),
        "per_anchor_support": dict(md.get("per_anchor_support") or {}),
        "answer_group_support_counts": dict(support_counts),
        "selector_candidate_pool_size": int(md.get("selector_candidate_pool_size", 0) or 0),
        "selector_candidate_pool_sources": list(md.get("selector_candidate_pool_sources") or []),
        "required_metadata_present": all(
            k in md
            for k in (
                "diverse_prompt_anchor_metadata",
                "per_anchor_support",
                "candidate_pool_answer_group_count",
                "answer_group_entropy",
                "frontier_collapse_detected",
                "direct_l1_anchor_present",
                "selector_candidate_pool",
                "answer_group_support_counts",
            )
        ),
        "gold_in_pool": _gold_in_pool(md, case.gold_answer),
        "duplicate_answers_merge_correctly": bool(duplicate_answers_merge_correctly),
        "remaining_budget_before_frontier": remaining_budget_observed,
        "frontier_factory_budget_observed": frontier_factory.budgets[0] if frontier_factory.budgets else None,
        "expected_remaining_frontier_budget_after_anchors": expected_remaining_after_anchor,
        "frontier_budget_preserved_after_anchor_phase": bool(frontier_budget_preserved),
        "frontier_executed": bool(md.get("frontier_executed")),
        "api_calls_made": 0,
    }


def _verify_registry_without_api_keys() -> dict[str, Any]:
    previous_env = {k: os.environ.get(k) for k in API_ENV_KEYS}
    for key in API_ENV_KEYS:
        os.environ.pop(key, None)
    try:
        rng = random.Random(20260510)
        gen_factory = generator_factory_for_mode(False, rng, "gpt-4o-mini", 0.1, 220, 30)
        specs = build_frontier_strategies(
            gen_factory,
            8,
            [1],
            rng,
            use_openai_api=False,
            include_broad_diversity_aggregation_methods=True,
            include_external_l1_baseline=False,
            include_external_s1_baseline=False,
            include_external_tale_baseline=False,
        )
        method_id = METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_DIVERSE_ANCHOR
        ctrl = specs.get(method_id)
        simulated_result: MethodResult | None = None
        simulated_error = ""
        if ctrl is not None:
            try:
                simulated_result = ctrl.run(
                    "A store sells 3 packs for 5 dollars each. What is the total revenue?",
                    "15",
                )
            except Exception as exc:  # pragma: no cover - serialized into audit artifact if it happens
                simulated_error = repr(exc)
        return {
            "method_id": method_id,
            "registered_in_build_frontier_strategies": method_id in specs,
            "builds_without_api_keys": ctrl is not None,
            "controller_class": type(ctrl).__name__ if ctrl is not None else "",
            "enable_diverse_prompt_anchors": bool(getattr(ctrl, "enable_diverse_prompt_anchors", False)) if ctrl else False,
            "enable_direct_hybrid_seed": bool(getattr(ctrl, "enable_direct_hybrid_seed", False)) if ctrl else False,
            "diverse_prompt_anchor_budget_actions": int(getattr(ctrl, "diverse_prompt_anchor_budget_actions", 0) or 0) if ctrl else 0,
            "simulated_run_without_api_keys": simulated_result is not None and not simulated_error,
            "simulated_run_error": simulated_error,
            "simulated_metadata_keys_present": (
                all(
                    k in (simulated_result.metadata or {})
                    for k in (
                        "diverse_prompt_anchor_metadata",
                        "per_anchor_support",
                        "candidate_pool_answer_group_count",
                        "answer_group_entropy",
                        "frontier_collapse_detected",
                    )
                )
                if simulated_result is not None
                else False
            ),
            "api_env_keys_removed_for_check": list(API_ENV_KEYS),
            "api_calls_made": 0,
        }
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _write_outputs(payload: dict[str, Any]) -> None:
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    fieldnames = [
        "case_id",
        "method_id",
        "anchors_configured",
        "anchors_executed",
        "candidate_answer_group_count",
        "answer_group_entropy",
        "frontier_collapse_detected",
        "per_anchor_support",
        "direct_l1_anchor_present",
        "duplicate_answers_merge_correctly",
        "remaining_budget_before_frontier",
        "frontier_factory_budget_observed",
        "expected_remaining_frontier_budget_after_anchors",
        "frontier_budget_preserved_after_anchor_phase",
        "gold_in_pool",
        "required_metadata_present",
        "api_calls_made",
    ]
    with CSV_OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload["cases"]:
            flat = dict(row)
            flat["anchors_configured"] = "|".join(row.get("anchors_configured") or [])
            flat["anchors_executed"] = "|".join(row.get("anchors_executed") or [])
            flat["per_anchor_support"] = json.dumps(row.get("per_anchor_support") or {}, sort_keys=True)
            writer.writerow({k: flat.get(k) for k in fieldnames})


def main() -> int:
    cases = [
        AuditCase(
            case_id="diverse_groups",
            answers=["10", "20", "30", "35", "40", "45"],
            gold_answer="40",
            question="A money problem asks for total revenue after multiple sales.",
        ),
        AuditCase(
            case_id="duplicate_merge",
            answers=["10", "20", "20", "20", "20", "20"],
            gold_answer="20",
            question="A multi-step arithmetic problem where anchors agree on the same answer.",
        ),
        AuditCase(
            case_id="frontier_collapse",
            answers=["10", "10", "10", "10", "10", "10"],
            gold_answer="999",
            question="A simulated collapse case where all anchors return one wrong group.",
        ),
        AuditCase(
            case_id="frontier_budget_preservation",
            answers=["10", "20", "30", "35", "40", "45"],
            gold_answer="40",
            question="A ratio and percentage problem that should leave budget for frontier search.",
            force_frontier=True,
            frontier_answer="99",
        ),
    ]
    registry = _verify_registry_without_api_keys()
    case_rows = [_summarize_case(case) for case in cases]
    payload = {
        "audit_name": "diverse_anchor_no_api_audit_20260510",
        "method_id": METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_DIVERSE_ANCHOR,
        "number_of_cases": len(case_rows),
        "anchors_configured": list(ANCHOR_IDS),
        "registry": registry,
        "cases": case_rows,
        "aggregate": {
            "cases": len(case_rows),
            "all_required_metadata_present": all(r["required_metadata_present"] for r in case_rows),
            "all_direct_l1_anchor_present": all(r["direct_l1_anchor_present"] for r in case_rows),
            "duplicate_merge_case_passed": any(
                r["case_id"] == "duplicate_merge" and r["duplicate_answers_merge_correctly"] for r in case_rows
            ),
            "collapse_case_detected": any(
                r["case_id"] == "frontier_collapse" and r["frontier_collapse_detected"] for r in case_rows
            ),
            "frontier_budget_preservation_case_passed": any(
                r["case_id"] == "frontier_budget_preservation"
                and r["frontier_budget_preserved_after_anchor_phase"]
                for r in case_rows
            ),
            "max_candidate_answer_group_count": max(r["candidate_answer_group_count"] for r in case_rows),
            "min_candidate_answer_group_count": min(r["candidate_answer_group_count"] for r in case_rows),
            "api_calls_made": 0,
        },
    }
    _write_outputs(payload)
    print(json.dumps(payload["aggregate"], indent=2, sort_keys=True))
    print(f"Wrote {JSON_OUT.relative_to(REPO_ROOT)}")
    print(f"Wrote {CSV_OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

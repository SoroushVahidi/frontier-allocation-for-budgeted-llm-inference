from __future__ import annotations

import os
from typing import Any

from experiments.controllers import DirectReserveFrontierGateController, MethodResult
from experiments.frontier_max_support_tiebreak import normalize_answer_group_key
from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode
from experiments.strategy_seeded_semantic_diversity_frontier_v1 import (
    METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_DIVERSE_ANCHOR,
)


class _Branch:
    def __init__(self, branch_id: str) -> None:
        self.branch_id = branch_id
        self.predicted_answer: str | None = None
        self.is_done = False
        self.is_pruned = False
        self.trace_events: list[dict[str, Any]] = []


class _MockGenerator:
    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.idx = 0
        self.prompts: list[str] = []

    def init_branch(self, branch_id: str) -> _Branch:
        return _Branch(branch_id)

    def expand(self, branch: _Branch, question: str, gold_answer: str) -> None:
        answer = self.answers[self.idx] if self.idx < len(self.answers) else self.answers[-1]
        self.idx += 1
        self.prompts.append(question)
        branch.predicted_answer = answer
        branch.is_done = True
        branch.trace_events.append(
            {
                "prompt_text": question,
                "response_text": f"Reasoned answer is {answer}",
                "reasoning_text": f"Reasoned answer is {answer}",
                "extracted_answer": answer,
            }
        )


class _MockScorer:
    def score(self, branch: _Branch, question: str, gold_answer: str) -> float:
        return 1.0


class _NoFrontier:
    def run(self, question: str, gold_answer: str) -> MethodResult:
        return MethodResult(
            method="no_frontier",
            prediction=None,
            is_correct=False,
            actions_used=0,
            expansions=0,
            verifications=0,
            avg_surviving_branches=1.0,
            budget_exhausted=False,
            metadata={"answer_group_support_counts": {}},
        )


def _controller(answers: list[str], anchor_ids: tuple[str, ...], *, max_actions_per_problem: int = 10) -> DirectReserveFrontierGateController:
    return DirectReserveFrontierGateController(
        _MockGenerator(answers),
        _MockScorer(),
        max_actions_per_problem=int(max_actions_per_problem),
        direct_reserve_attempts_override=1,
        enable_direct_hybrid_seed=True,
        direct_hybrid_seed_budget_actions=1,
        enable_diverse_prompt_anchors=True,
        diverse_prompt_anchor_budget_actions=1,
        diverse_prompt_anchor_ids=anchor_ids,
        enable_frontier_max_support_tiebreak=True,
        strict_controller_factory=lambda _budget: _NoFrontier(),
    )


def test_diverse_anchor_ids_are_recorded_and_direct_l1_is_preserved() -> None:
    ctrl = _controller(
        ["10", "20", "30", "40"],
        ("direct_l1_anchor", "equation_first_anchor", "ratio_percentage_anchor"),
    )

    md = ctrl.run("A money word problem asks for total revenue.", "30").metadata

    anchor_meta = md["diverse_prompt_anchor_metadata"]
    anchor_ids = [row["anchor_id"] for row in anchor_meta]
    assert anchor_ids == ["direct_l1_anchor", "equation_first_anchor", "ratio_percentage_anchor"]
    assert md["direct_l1_anchor_present"] is True
    assert md["direct_l1_anchor_answer"] == "20"
    assert md["per_anchor_support"]["direct_l1_anchor"] == 1
    assert md["per_anchor_support"]["equation_first_anchor"] == 1

    pool = md["selector_candidate_pool"]
    pool_anchor_ids = {row.get("anchor_id") for row in pool if row.get("anchor_id")}
    assert {"direct_l1_anchor", "equation_first_anchor", "ratio_percentage_anchor"}.issubset(pool_anchor_ids)
    assert all("answer_group" in row for row in pool)
    assert md["diverse_prompt_anchor_budget_actions"] == 1
    assert md["diverse_prompt_anchor_ids_executed"] == ["direct_l1_anchor", "equation_first_anchor", "ratio_percentage_anchor"]
    assert md["diverse_prompt_anchor_skipped"] == []
    assert md["anchor_priority_policy"] == "domain_aware_v1"
    assert md["detected_problem_domain"] == "money_cost_revenue"
    assert md["configured_anchor_ids"] == ["direct_l1_anchor", "equation_first_anchor", "ratio_percentage_anchor"]
    assert md["prioritized_anchor_ids"] == ["direct_l1_anchor", "equation_first_anchor", "ratio_percentage_anchor"]


def test_diverse_anchors_create_multiple_groups_and_entropy_metadata() -> None:
    ctrl = _controller(
        ["10", "20", "30", "40"],
        ("direct_l1_anchor", "equation_first_anchor", "ratio_percentage_anchor"),
    )

    md = ctrl.run("A ratio percentage problem.", "40").metadata

    anchor_meta = md["diverse_prompt_anchor_metadata"]
    anchor_ids = [row["anchor_id"] for row in anchor_meta]
    assert anchor_ids == ["direct_l1_anchor", "ratio_percentage_anchor", "equation_first_anchor"]
    assert md["detected_problem_domain"] == "ratio_percent"
    assert md["candidate_pool_answer_group_count"] == 4
    assert md["candidate_pool_answer_group_count_after_anchor"] == 4
    assert md["answer_group_entropy"] > 0.0
    assert md["frontier_collapse_detected"] is False
    assert md["answer_group_support_counts"][normalize_answer_group_key("30")] == 1
    assert md["answer_group_support_counts"][normalize_answer_group_key("40")] == 1


def test_duplicate_anchor_answers_increase_support_without_new_answer_group() -> None:
    ctrl = _controller(
        ["10", "20", "20", "20"],
        ("direct_l1_anchor", "equation_first_anchor", "ratio_percentage_anchor"),
    )

    md = ctrl.run("A multi-step arithmetic problem.", "20").metadata

    group_20 = normalize_answer_group_key("20")
    assert md["answer_group_support_counts"][group_20] == 3
    assert md["candidate_pool_answer_group_count_after_anchor"] == 2
    assert md["per_anchor_support"]["direct_l1_anchor"] == 3
    assert md["per_anchor_support"]["equation_first_anchor"] == 3
    assert md["per_anchor_support"]["ratio_percentage_anchor"] == 3


def test_frontier_collapse_metadata_marks_low_diversity() -> None:
    ctrl = _controller(
        ["10", "10", "10", "10"],
        ("direct_l1_anchor", "equation_first_anchor", "ratio_percentage_anchor"),
    )

    md = ctrl.run("A collapsed candidate pool problem.", "999").metadata

    assert md["candidate_pool_answer_group_count_after_anchor"] == 1
    assert md["answer_group_entropy"] == 0.0
    assert md["frontier_collapse_detected"] is True


def test_diverse_anchor_skips_are_recorded_when_budget_exhausted() -> None:
    ctrl = _controller(
        ["10", "20", "30", "40"],
        ("direct_l1_anchor", "equation_first_anchor", "unit_ledger_money_anchor", "ratio_percentage_anchor", "backward_check_anchor"),
        max_actions_per_problem=4,
    )

    md = ctrl.run("A ratio percentage problem.", "40").metadata

    assert md["diverse_prompt_anchor_budget_actions"] == 1
    assert md["remaining_budget_before_diverse_anchors"] == 2
    assert md["remaining_budget_after_diverse_anchors"] == 0
    assert md["detected_problem_domain"] == "ratio_percent"
    assert md["prioritized_anchor_ids"] == [
        "direct_l1_anchor",
        "ratio_percentage_anchor",
        "equation_first_anchor",
        "unit_ledger_money_anchor",
        "backward_check_anchor",
    ]
    assert md["diverse_prompt_anchor_ids_executed"] == ["direct_l1_anchor", "ratio_percentage_anchor", "equation_first_anchor"]
    skipped = md["diverse_prompt_anchor_skipped"]
    skipped_ids = [row.get("anchor_id") for row in skipped]
    assert skipped_ids == ["unit_ledger_money_anchor", "backward_check_anchor"]
    assert all(row.get("skip_reason") == "insufficient_remaining_budget" for row in skipped)


def test_budget4_money_domain_prioritizes_unit_ledger_then_equation_first() -> None:
    ctrl = _controller(
        ["10", "20", "30", "40"],
        ("direct_l1_anchor", "equation_first_anchor", "unit_ledger_money_anchor", "ratio_percentage_anchor", "backward_check_anchor"),
        max_actions_per_problem=4,
    )
    md = ctrl.run("A money word problem about costs and revenue.", "40").metadata
    assert md["detected_problem_domain"] == "money_cost_revenue"
    assert md["diverse_prompt_anchor_ids_executed"] == ["direct_l1_anchor", "unit_ledger_money_anchor", "equation_first_anchor"]


def test_budget4_multi_step_arithmetic_prioritizes_backward_check_second() -> None:
    ctrl = _controller(
        ["10", "20", "30", "40"],
        ("direct_l1_anchor", "equation_first_anchor", "unit_ledger_money_anchor", "ratio_percentage_anchor", "backward_check_anchor"),
        max_actions_per_problem=4,
    )
    md = ctrl.run("John has 3 apples then buys 4 more. What is the total?", "7").metadata
    assert md["detected_problem_domain"] == "multi_step_arithmetic"
    assert md["diverse_prompt_anchor_ids_executed"] == ["direct_l1_anchor", "equation_first_anchor", "backward_check_anchor"]


def test_budget4_unknown_domain_falls_back_to_default_order() -> None:
    ctrl = _controller(
        ["10", "20", "30", "40"],
        ("direct_l1_anchor", "equation_first_anchor", "unit_ledger_money_anchor", "ratio_percentage_anchor", "backward_check_anchor"),
        max_actions_per_problem=4,
    )
    md = ctrl.run("Solve for x in x + 2 = 5.", "3").metadata
    assert md["detected_problem_domain"] == "unknown"
    assert md["prioritized_anchor_ids"] == [
        "direct_l1_anchor",
        "equation_first_anchor",
        "unit_ledger_money_anchor",
        "ratio_percentage_anchor",
        "backward_check_anchor",
    ]
    assert md["diverse_prompt_anchor_ids_executed"] == ["direct_l1_anchor", "equation_first_anchor", "unit_ledger_money_anchor"]


def test_diverse_anchor_scaffolding_uses_simulated_generator_without_api_keys(monkeypatch) -> None:
    for key in ("OPENAI_API_KEY", "COHERE_API_KEY", "CO_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    import random

    rng = random.Random(0)
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

    ctrl = specs[METHOD_DIRECT_RESERVE_DIVERSE_ROOT_FRONTIER_V1_GUARDED_K1_FRONTIER4_FRONTIER_TIEBREAK_DIVERSE_ANCHOR]
    assert getattr(ctrl, "enable_diverse_prompt_anchors", False) is True
    assert getattr(ctrl, "enable_direct_hybrid_seed", False) is True


def test_strong_pal_conflict_protection_still_blocks_anchor_supported_peer() -> None:
    from experiments.output_layer_repair import decide_pal_strong_overlay_promotion

    promote, reason, diag = decide_pal_strong_overlay_promotion(
        combined_group_counts_base={normalize_answer_group_key("20"): 2},
        pal_answer_raw="30",
        incumbent_final_answer_raw="20",
        frontier_weak=False,
        tiebreak_triggered=True,
        tiebreak_selected_group_raw="20",
        strong_pal=True,
        pal_score=0.95,
    )

    assert promote is False
    assert reason == "blocked_frontier_tiebreak_conflict"
    assert diag["pal_frontier_conflict"] is True

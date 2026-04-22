"""Smoke tests for experimental hard early root depth-2 coverage refinement."""

from __future__ import annotations

import random

from experiments.branching import BranchState
from experiments.branching import SimulatedBranchGenerator
from experiments.controllers import GlobalDiversityAggregationController
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.scoring import ScoreConfig, SimpleBranchScorer


def _mk_controller(*, max_actions: int = 10, forced_min_depth: int = 3) -> GlobalDiversityAggregationController:
    return GlobalDiversityAggregationController(
        SimulatedBranchGenerator(rng=random.Random(0), max_depth=7, finish_prob_base=0.16, answer_noise=0.12),
        SimpleBranchScorer(ScoreConfig()),
        max_actions,
        enable_hard_early_root_depth2_coverage_v1=True,
        hard_early_root_coverage_forced_min_depth=forced_min_depth,
    )


def _mk_branch(branch_id: str, depth: int, *, done: bool = False, pruned: bool = False) -> BranchState:
    return BranchState(
        branch_id=branch_id,
        latent_quality=0.5,
        steps=[f"s{i}" for i in range(depth)],
        score=0.5,
        is_done=done,
        is_pruned=pruned,
    )


def test_hard_early_coverage_methods_registered() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(7), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=10,
        adaptive_min_expand_grid=[1],
        rng=random.Random(11),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    assert (
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1"
        in specs
    )
    assert (
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
        in specs
    )
    assert (
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_conditional_depth3_v1"
        in specs
    )
    strict_gate1_base = (
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
        "_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first"
    )
    assert f"{strict_gate1_base}_hard_max_family_expansions_cap_k6_v1_fixed_k6_control" in specs


def test_hard_early_coverage_emits_metadata_fields() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(3), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=12,
        adaptive_min_expand_grid=[1],
        rng=random.Random(5),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    m = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1"
    ex = load_pilot_examples("openai/gsm8k", 40, 17)[0]
    meta = specs[m].run(ex.question, ex.answer).metadata
    assert int(meta.get("hard_early_root_coverage_forced_min_depth") or 0) == 2
    assert meta.get("hard_early_root_depth2_coverage_v1_enabled") is True
    assert "hard_early_coverage_completed_fully" in meta
    assert "hard_early_coverage_final_family_status" in meta


def test_hard_early_depth3_coverage_emits_min_depth_metadata() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(3), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=12,
        adaptive_min_expand_grid=[1],
        rng=random.Random(5),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    m = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
    ex = load_pilot_examples("openai/gsm8k", 40, 17)[0]
    meta = specs[m].run(ex.question, ex.answer).metadata
    assert int(meta.get("hard_early_root_coverage_forced_min_depth") or 0) == 3
    assert meta.get("hard_early_root_depth3_coverage_v1_enabled") is True


def test_conditional_depth3_gate_emits_metadata() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(3), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=14,
        adaptive_min_expand_grid=[1],
        rng=random.Random(5),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    m = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_conditional_depth3_v1"
    ex = load_pilot_examples("openai/gsm8k", 40, 17)[0]
    meta = specs[m].run(ex.question, ex.answer).metadata
    assert meta.get("hard_early_root_depth2_then_conditional_depth3_v1_enabled") is True
    assert "conditional_depth3_gate_record" in meta
    assert "conditional_depth3_gate_thresholds" in meta


def test_gate_v1_design_metadata_emits_design_name() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(3), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=14,
        adaptive_min_expand_grid=[1],
        rng=random.Random(5),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    m = (
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
        "_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control"
    )
    ex = load_pilot_examples("openai/gsm8k", 40, 17)[0]
    meta = specs[m].run(ex.question, ex.answer).metadata
    thresholds = meta.get("conditional_depth3_gate_thresholds") or {}
    assert isinstance(thresholds, dict)
    assert "depth3_gate_min_top_answer_support" in thresholds
    assert "depth3_gate_min_support_gap" in thresholds


def test_strict_phased_depth1_blocks_depth2_entry_until_all_families_reach_depth1() -> None:
    c = _mk_controller(forced_min_depth=3)
    b0 = _mk_branch("f0_h", 0)
    b1 = _mk_branch("f1_h", 1)
    diag = c._hard_early_root_coverage_forced_diagnostic(
        branches=[b0, b1],
        branch_family_ids={"f0_h": "f0", "f1_h": "f1"},
        root_family_ids=frozenset({"f0", "f1"}),
        actions_so_far=0,
        max_actions=8,
        force_disabled=False,
    )
    assert diag.get("enabled") is True
    assert set(diag.get("pending_families") or []) == {"f0", "f1"}
    assert (diag.get("family_status") or {}).get("f0", {}).get("reason") == "depth_below_3"


def test_strict_phased_depth2_blocks_depth3_entry_until_all_families_reach_depth2() -> None:
    c = _mk_controller(forced_min_depth=3)
    b0 = _mk_branch("f0_h", 1)
    b1 = _mk_branch("f1_h", 2)
    diag = c._hard_early_root_coverage_forced_diagnostic(
        branches=[b0, b1],
        branch_family_ids={"f0_h": "f0", "f1_h": "f1"},
        root_family_ids=frozenset({"f0", "f1"}),
        actions_so_far=1,
        max_actions=10,
        force_disabled=False,
    )
    assert diag.get("enabled") is True
    assert "f0" in (diag.get("pending_families") or [])
    assert (diag.get("family_status") or {}).get("f0", {}).get("reason") == "depth_below_3"


def test_strict_phased_prevents_depth3_start_when_any_family_below_depth2() -> None:
    c = _mk_controller(forced_min_depth=3)
    deep = _mk_branch("deep", 3)
    shallow = _mk_branch("shallow", 1)
    scored = [(deep, 0.95, {}), (shallow, 0.40, {})]
    diag = c._hard_early_root_coverage_forced_diagnostic(
        branches=[deep, shallow],
        branch_family_ids={"deep": "f0", "shallow": "f1"},
        root_family_ids=frozenset({"f0", "f1"}),
        actions_so_far=2,
        max_actions=12,
        force_disabled=False,
    )
    chosen, _, _, meta = c._apply_hard_early_root_coverage_forced_override(
        scored,
        branch=deep,
        priority=0.95,
        pri_meta={},
        branch_family_ids={"deep": "f0", "shallow": "f1"},
        diag=diag,
        branches=[deep, shallow],
    )
    assert diag.get("enabled") is True
    assert "f1" in (diag.get("pending_families") or [])
    assert chosen.branch_id == "shallow"
    assert bool(meta.get("hard_early_coverage_forced_override"))


def test_strict_phased_stays_in_depth3_until_completion_or_release() -> None:
    c = _mk_controller(max_actions=20, forced_min_depth=3)
    b0 = _mk_branch("f0_h", 2)
    b1 = _mk_branch("f1_h", 3)
    diag = c._hard_early_root_coverage_forced_diagnostic(
        branches=[b0, b1],
        branch_family_ids={"f0_h": "f0", "f1_h": "f1"},
        root_family_ids=frozenset({"f0", "f1"}),
        actions_so_far=5,
        max_actions=20,
        force_disabled=False,
    )
    assert diag.get("enabled") is True
    assert diag.get("pending_families") == ["f0"]
    assert (diag.get("family_status") or {}).get("f1", {}).get("pending") is False
    assert not bool(diag.get("release_impossible_under_budget"))


def test_strict_phased_preserves_score_order_within_same_level_pending_families() -> None:
    c = _mk_controller(forced_min_depth=2)
    b0 = _mk_branch("f0_h", 1)
    b1 = _mk_branch("f1_h", 1)
    scored = [(b1, 0.91, {}), (b0, 0.62, {})]
    diag = c._hard_early_root_coverage_forced_diagnostic(
        branches=[b0, b1],
        branch_family_ids={"f0_h": "f0", "f1_h": "f1"},
        root_family_ids=frozenset({"f0", "f1"}),
        actions_so_far=1,
        max_actions=8,
        force_disabled=False,
    )
    chosen, _, _, meta = c._apply_hard_early_root_coverage_forced_override(
        scored,
        branch=b1,
        priority=0.91,
        pri_meta={},
        branch_family_ids={"f0_h": "f0", "f1_h": "f1"},
        diag=diag,
        branches=[b0, b1],
    )
    assert diag.get("enabled") is True
    assert set(diag.get("pending_families") or []) == {"f0", "f1"}
    assert chosen.branch_id == "f1_h"
    assert not bool(meta.get("hard_early_coverage_forced_override"))


def test_strict_phased_gate_evaluation_only_after_f2_completion() -> None:
    c = _mk_controller(forced_min_depth=3)
    incomplete_d2 = {
        "all_root_families_satisfied": False,
        "release_impossible_under_budget": False,
        "pending_families": ["f0"],
    }
    done = _mk_branch("done", 2, done=True)
    gate = c._evaluate_conditional_depth3_gate(
        answer_support_counts={"a": 1},
        branch_expansions={},
        branch_family_ids={"done": "f0"},
        root_family_ids=frozenset({"f0"}),
        branches=[done],
        scored=[(done, 0.9, {})],
        actions_so_far=1,
        max_actions=10,
        expansions=1,
        max_consecutive_same_family_expands=1,
        hard_cov_diag_d2=incomplete_d2,
    )
    assert gate.get("diagnostic_depth2_at_gate", {}).get("all_root_families_satisfied") is False


def test_strict_phased_variants_registered() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(7), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=10,
        adaptive_min_expand_grid=[1],
        rng=random.Random(11),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    assert any("strict_gate1_cap_k6" in k for k in specs)
    assert any(k.startswith("strict_f3") for k in specs)

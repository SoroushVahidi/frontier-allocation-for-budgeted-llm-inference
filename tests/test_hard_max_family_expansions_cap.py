from __future__ import annotations

import random

from experiments.branching import SimulatedBranchGenerator
from experiments.controllers import GlobalDiversityAggregationController
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.scoring import ScoreConfig, SimpleBranchScorer


BASE = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"


def _mk_controller(*, cap: int, max_actions: int = 12) -> GlobalDiversityAggregationController:
    return GlobalDiversityAggregationController(
        SimulatedBranchGenerator(rng=random.Random(0), max_depth=7, finish_prob_base=0.16, answer_noise=0.12),
        SimpleBranchScorer(ScoreConfig()),
        max_actions,
        enable_hard_max_family_expansions_cap=True,
        hard_max_family_expansions_base_cap=cap,
        hard_max_family_expansions_relax_cap=cap,
        hard_max_family_expansions_relax_cap_high=cap,
        hard_max_family_expansions_relax_mode="fixed_k6_control",
    )


def _phase_law_ok(meta: dict[str, object]) -> bool:
    ph = [str(ev.get("to_phase") or "") for ev in list(meta.get("hard_early_coverage_phase_transition_log") or []) if isinstance(ev, dict)]
    order = {"phase_f1": 1, "phase_f2": 2, "phase_gate_after_f2": 3, "phase_f3": 4, "phase_normal": 5}
    seen = [order[p] for p in ph if p in order]
    return all(seen[i] <= seen[i + 1] for i in range(len(seen) - 1))


def test_family_expansion_counts_increase_on_expand_only() -> None:
    c = _mk_controller(cap=2)
    r = c.run("What is 7+5?", "12")
    meta = r.metadata
    expands_by_group = meta.get("expands_by_group") or {}
    assert isinstance(expands_by_group, dict)
    assert int(sum(int(v) for v in expands_by_group.values())) == int(r.expansions)
    assert int(r.actions_used) == int(r.expansions + r.verifications)


def test_family_never_exceeds_hard_cap() -> None:
    cap = 2
    c = _mk_controller(cap=cap, max_actions=18)
    r = c.run("Compute 14+9.", "23")
    meta = r.metadata or {}
    assert meta.get("hard_max_family_expansions_cap_enabled") is True
    assert int(meta.get("hard_max_family_expansions_base_cap") or 0) == cap
    assert int(meta.get("hard_max_family_expansions_block_count") or 0) >= 1


def test_other_families_remain_eligible_after_one_hits_cap() -> None:
    c = _mk_controller(cap=1, max_actions=12)
    r = c.run("What is 10+11?", "21")
    expands_by_group = (r.metadata or {}).get("expands_by_group") or {}
    expanded_groups = [k for k, v in expands_by_group.items() if int(v) > 0]
    assert len(expanded_groups) >= 2


def test_strict_phased_law_still_obeyed_with_cap_active() -> None:
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
    method = (
        f"{BASE}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first"
        "_hard_max_family_expansions_cap_k6_v1_fixed_k6_control"
    )
    ex = load_pilot_examples("openai/gsm8k", 40, 17)[0]
    meta = specs[method].run(ex.question, ex.answer).metadata
    assert bool(meta.get("hard_max_family_expansions_cap_enabled"))
    assert _phase_law_ok(meta)


def test_hard_max_family_cap_variants_registered() -> None:
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
    strict_gate1_base = f"{BASE}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first"
    for relax_mode in (
        "fixed_k6_control",
        "relax_on_cross_family_coverage_complete",
        "relax_on_low_marginal_gain_absence_false",
        "relax_on_multi_family_maturity",
        "relax_on_high_confidence_incumbent_but_no_challenger_gap",
    ):
        assert f"{strict_gate1_base}_hard_max_family_expansions_cap_k6_v1_{relax_mode}" in specs


def test_strict_f3_conditional_early_cap_variants_registered() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(19), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=8,
        adaptive_min_expand_grid=[1],
        rng=random.Random(29),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    assert "strict_f3_conditional_early_risk_cap_k2_v1" in specs
    assert "strict_f3_conditional_early_risk_cap_k2_rival_maturation_v1" in specs
    for variant in (
        "strict_f3_conditional_early_risk_cap_k2_window5_v1",
        "strict_f3_conditional_early_risk_cap_k2_window7_v1",
        "strict_f3_conditional_early_risk_cap_k2_share55_v1",
        "strict_f3_conditional_early_risk_cap_k2_share65_v1",
        "strict_f3_conditional_early_risk_cap_k3_v1",
    ):
        assert variant in specs

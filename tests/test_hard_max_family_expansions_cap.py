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
        enable_hard_max_family_expansions_v1=True,
        max_family_expansions_per_run=cap,
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
    fam_counts = meta.get("hard_max_family_expansion_counts") or {}
    assert int(sum(int(v) for v in fam_counts.values())) == int(r.expansions)
    assert int(r.actions_used) == int(r.expansions + r.verifications)


def test_family_never_exceeds_hard_cap() -> None:
    cap = 2
    c = _mk_controller(cap=cap, max_actions=18)
    r = c.run("Compute 14+9.", "23")
    fam_counts = (r.metadata or {}).get("hard_max_family_expansion_counts") or {}
    assert fam_counts
    assert all(int(v) <= cap for v in fam_counts.values())


def test_other_families_remain_eligible_after_one_hits_cap() -> None:
    c = _mk_controller(cap=1, max_actions=12)
    r = c.run("What is 10+11?", "21")
    fam_counts = (r.metadata or {}).get("hard_max_family_expansion_counts") or {}
    expanded_families = [k for k, v in fam_counts.items() if int(v) > 0]
    assert len(expanded_families) >= 2


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
        "_hard_max_family_expansions_cap_k3_v1"
    )
    ex = load_pilot_examples("openai/gsm8k", 40, 17)[0]
    meta = specs[method].run(ex.question, ex.answer).metadata
    assert bool(meta.get("hard_max_family_expansions_v1_enabled"))
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
    assert f"{BASE}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k2_v1" in specs
    assert f"{BASE}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k3_v1" in specs
    assert f"{BASE}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k4_v1" in specs
    assert f"{BASE}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k5_v1" in specs
    assert f"{BASE}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1" in specs
    assert f"{BASE}_hard_early_root_depth2_then_gate_v2_budget_aware_rescue_hard_max_family_expansions_cap_k3_v1" in specs

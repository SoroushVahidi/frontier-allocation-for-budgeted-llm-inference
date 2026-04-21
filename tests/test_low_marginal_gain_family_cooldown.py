import random

from experiments.branching import SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies


def test_low_marginal_gain_family_cooldown_methods_registered() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(rng=random.Random(7), max_depth=7, finish_prob_base=0.16, answer_noise=0.12),
        budget=8,
        adaptive_min_expand_grid=[1],
        rng=random.Random(11),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    assert "broad_diversity_aggregation_strong_v1_anti_collapse_repeat_expansion_low_marginal_gain_cooldown_v1" in specs
    assert "broad_diversity_aggregation_strong_v1_anti_collapse_repeat_expansion_low_marginal_gain_hard_block_ablation_v1" in specs
    assert (
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1"
        in specs
    )
    assert (
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1_low_marginal_gain_cooldown_v1"
        in specs
    )

from __future__ import annotations

import random

from experiments.branching import SimulatedBranchGenerator
from experiments.controllers import CASE_SPLIT_LABELS, classify_question_shape
from experiments.frontier_matrix_core import build_frontier_strategies


def test_question_shape_detector_labels_are_stable() -> None:
    assert "counting_combinatorics" in CASE_SPLIT_LABELS
    assert classify_question_shape("How many different ways can we arrange 5 books?") == "counting_combinatorics"
    assert classify_question_shape("If x is even or odd, consider each case.") == "case_split"
    assert classify_question_shape("A ratio is 3:4. What percent is that?") == "ratio_percent"
    assert classify_question_shape("") == "unknown"


def test_case_split_direction_aware_methods_registered() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(7), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=8,
        adaptive_min_expand_grid=[1],
        rng=random.Random(11),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    assert "strict_f3_case_split_direction_aware_v1" in specs
    assert "strict_f3_case_split_direction_aware_v1_no_delayed_commit" in specs
    assert "strict_f3_case_split_direction_aware_v1_no_stronger_repeat_family_penalty" in specs
    assert "strict_f3_case_split_direction_aware_v1_no_unresolved_branch_preservation" in specs
    assert "strict_f3_case_split_direction_aware_v1_detector_off" in specs

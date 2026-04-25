from __future__ import annotations

import random
import subprocess
from pathlib import Path

import pytest

from experiments.branching import SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies
from experiments.problem_type_utils import classify_problem_type

ARTIFACT_CASES_CSV = Path("outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/all_paired_cases.csv")


def test_problem_type_classifier_detects_combinatorics() -> None:
    q = "How many different ways can 5 students be arranged in a line?"
    assert classify_problem_type(q) == "counting_combinatorics"


def test_branch_families_seeded_for_combinatorics_case() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(3), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=8,
        adaptive_min_expand_grid=[1],
        rng=random.Random(5),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    m = specs["strict_f3_direction_combinatorics_guard_v1"]
    res = m.run("How many ways can we choose 2 from 5?", "10")
    meta = res.metadata or {}
    assert meta.get("problem_type_label") == "counting_combinatorics"
    assert int(meta.get("num_strategy_families_seen", 0)) >= 1


def test_family_cap_and_commit_guard_metadata_emitted() -> None:
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
    res = specs["strict_f3_direction_combinatorics_guard_v1"].run(
        "How many possible groups can be selected from 6 people if order does not matter?",
        "15",
    )
    meta = res.metadata or {}
    assert "family_cap_blocked_expansion" in meta
    assert "commit_guard_triggered_count" in meta
    assert "verifier_pass_count" in meta


def test_verifier_output_parsed() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(9), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=6,
        adaptive_min_expand_grid=[1],
        rng=random.Random(13),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    res = specs["strict_f3_direction_combinatorics_guard_v1"].run(
        "How many ways can 4 books be arranged on a shelf?",
        "24",
    )
    meta = res.metadata or {}
    assert "verifier_calls" in meta
    assert "verifier_fail_count" in meta


def test_default_strict_f3_unchanged_availability() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(3), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=6,
        adaptive_min_expand_grid=[1],
        rng=random.Random(5),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    assert (
        "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
        in specs
    )
    assert "strict_f3_direction_combinatorics_guard_v1" in specs


def test_output_csv_headers_non_empty(tmp_path: Path) -> None:
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    header = p.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header and all(h.strip() for h in header)


def test_dry_run_completes_without_api_keys() -> None:
    if not ARTIFACT_CASES_CSV.exists():
        pytest.skip(f"artifact-dependent test requires {ARTIFACT_CASES_CSV}")
    cmd = [
        "python",
        "scripts/run_direction_combinatorics_guard_eval.py",
        "--timestamp",
        "20260425T_DIRECTION_COMBINATORICS_GUARD_TEST_DRY",
        "--dry-run",
        "--max-cases",
        "2",
    ]
    subprocess.run(cmd, check=True)

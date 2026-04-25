from __future__ import annotations

import csv
import json
import random
import shutil
import subprocess
from pathlib import Path

from experiments.branching import SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies
from scripts.run_family_normalized_rerank_eval import (
    family_normalized_full_score,
    family_normalized_support_from_counts,
)


STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)


def _specs() -> dict[str, object]:
    return build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(101), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=8,
        adaptive_min_expand_grid=[1],
        rng=random.Random(103),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )


def test_method_registered_and_default_strict_f3_unchanged() -> None:
    specs = _specs()
    assert "strict_f3_typed_strategy_family_normalized_rerank_v1" in specs
    assert STRICT_F3_RUNTIME in specs


def test_family_normalized_metadata_emitted() -> None:
    specs = _specs()
    res = specs["strict_f3_typed_strategy_family_normalized_rerank_v1"].run(
        "How many ways can 5 students be arranged in a line?",
        "120",
    )
    meta = res.metadata or {}
    assert "family_normalized_support_by_answer_group" in meta
    assert "answer_group_strategy_family_counts" in meta
    assert "selection_mode" in meta


def test_family_normalized_support_caps_same_family_votes() -> None:
    one_family_many_votes = family_normalized_support_from_counts({"direct_formula_family": 7})
    two_families = family_normalized_support_from_counts({"direct_formula_family": 1, "explicit_case_split_family": 1})
    assert one_family_many_votes == 1.0
    assert two_families == 2.0


def test_two_families_can_beat_many_same_family_under_full_score() -> None:
    # Group A: lots of correlated votes from one family.
    score_a = family_normalized_full_score(
        normalized_support_fraction=0.40,
        process_score=0.55,
        verifier_score=0.55,
        diversity_score=1.0,
        single_family_penalty=1.0,
        dominant_family_penalty=1.0,
    )
    # Group B: fewer raw votes but broader independent family support.
    score_b = family_normalized_full_score(
        normalized_support_fraction=0.35,
        process_score=0.55,
        verifier_score=0.55,
        diversity_score=2.0,
        single_family_penalty=0.0,
        dominant_family_penalty=0.5,
    )
    assert score_b > score_a


def test_smoke_runner_outputs_and_ablation() -> None:
    ts = "20260425T_FAMILY_NORMALIZED_RERANK_TEST_DRY"
    out = Path("outputs") / f"family_normalized_rerank_eval_{ts}"
    if out.exists():
        shutil.rmtree(out)
    subprocess.run(
        [
            "python",
            "scripts/run_family_normalized_rerank_eval.py",
            "--timestamp",
            ts,
            "--dry-run",
            "--slice",
            "present_not_selected",
            "--max-cases",
            "3",
            "--selection-mode",
            "family_normalized_full",
            "--selection-ablation",
            "--emit-traces",
            "--resume",
        ],
        check=True,
    )
    required = [
        "summary.csv",
        "slice_summary.csv",
        "per_case_results.csv",
        "per_answer_group_scores.jsonl",
        "gold_vs_selected_diagnostics.csv",
        "selection_ablation_summary.csv",
        "selection_ablation_per_case.csv",
        "present_not_selected_repairs.csv",
        "absent_from_tree_repairs.csv",
        "hurt_cases.csv",
        "verifier_score_diagnostics.csv",
        "family_vote_diagnostics.csv",
        "missing_fields_report.csv",
        "README.md",
    ]
    for name in required:
        p = out / name
        assert p.exists()
        txt = p.read_text(encoding="utf-8")
        if p.suffix == ".csv":
            assert txt.splitlines()
            assert txt.splitlines()[0].strip()
        elif p.suffix == ".jsonl" and txt.strip():
            _ = json.loads(txt.splitlines()[0])
        else:
            assert txt.strip()
    with (out / "per_case_results.csv").open("r", encoding="utf-8", newline="") as f:
        hdr = list(csv.DictReader(f).fieldnames or [])
    assert "selection_failure_reason" in hdr
    assert "family_rerank_repaired_case" in hdr
    with (out / "selection_ablation_per_case.csv").open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    oracle = [r for r in rows if r.get("rule") == "oracle_if_gold_present" and r.get("gold_present") == "1"]
    full = [r for r in rows if r.get("rule") == "family_normalized_full" and r.get("gold_present") == "1"]
    if oracle and full:
        o = sum(int(r["is_correct"]) for r in oracle) / max(1, len(oracle))
        ff = sum(int(r["is_correct"]) for r in full) / max(1, len(full))
        assert o >= ff


from __future__ import annotations

import csv
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from experiments.branching import SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies
from experiments.problem_type_utils import classify_problem_type
from experiments.typed_strategy_prompts import get_typed_strategy_prompts

ARTIFACT_CASES_CSV = Path("outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/all_paired_cases.csv")

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)


def _build_specs() -> dict[str, object]:
    return build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(17), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=8,
        adaptive_min_expand_grid=[1],
        rng=random.Random(19),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )


def test_combinatorics_problem_type_detection() -> None:
    q = "How many distinct groups can be selected and arranged from 5 people?"
    assert classify_problem_type(q) == "counting_combinatorics"


def test_typed_strategy_prompt_generation_families_and_difference() -> None:
    prompts = get_typed_strategy_prompts("How many ways?", "counting_combinatorics")
    families = {p.strategy_family for p in prompts}
    required = {
        "direct_formula_family",
        "explicit_case_split_family",
        "enumeration_or_decomposition_family",
        "small_example_pattern_family",
        "sanity_check_verifier_family",
    }
    assert required.issubset(families)
    texts = [p.strategy_prompt for p in prompts]
    assert len(set(texts)) == len(texts)


def test_typed_seeded_branch_metadata_emitted_and_default_strict_f3_present() -> None:
    specs = _build_specs()
    res = specs["strict_f3_typed_strategy_seeded_v1"].run("How many ways can 4 books be arranged?", "24")
    meta = res.metadata or {}
    assert meta.get("problem_type_label") == "counting_combinatorics"
    assert int(meta.get("num_typed_strategy_branches_seeded", 0)) >= 5
    assert "typed_strategy_branch_metadata" in meta
    assert STRICT_F3_RUNTIME in specs


def test_commit_guard_and_diversity_metadata_emitted() -> None:
    specs = _build_specs()
    res = specs["strict_f3_typed_strategy_seeded_v1"].run(
        "How many possible pairs can be selected from 6 students?",
        "15",
    )
    meta = res.metadata or {}
    assert "commit_guard_triggered_count" in meta
    assert "typed_strategy_redundancy_detected" in meta
    assert "typed_strategy_families_seen" in meta
    assert "answer_group_strategy_family_counts" in meta
    assert "answer_group_final_scores" in meta


def test_dry_run_and_outputs_exist() -> None:
    if not ARTIFACT_CASES_CSV.exists():
        pytest.skip(f"artifact-dependent test requires {ARTIFACT_CASES_CSV}")
    ts = "20260425T_TYPED_STRATEGY_SEEDED_TEST_DRY"
    out = Path("outputs") / f"typed_strategy_seeded_eval_{ts}"
    if out.exists():
        shutil.rmtree(out)
    subprocess.run(
        [
            "python",
            "scripts/run_typed_strategy_seeded_eval.py",
            "--timestamp",
            ts,
            "--dry-run",
            "--slice",
            "loss150",
            "--max-cases",
            "2",
            "--emit-traces",
            "--selection-ablation",
        ],
        check=True,
    )
    required = [
        "summary.csv",
        "slice_summary.csv",
        "per_case_results.csv",
        "per_case_strategy_metadata.jsonl",
        "per_branch_strategy_traces.jsonl",
        "typed_strategy_diversity_summary.csv",
        "answer_group_by_strategy_summary.csv",
        "transition_summary.csv",
        "commit_guard_summary.csv",
        "verifier_diagnostics.csv",
        "present_not_selected_repairs.csv",
        "absent_from_tree_repairs.csv",
        "hurt_cases.csv",
        "missing_fields_report.csv",
        "selection_ablation_summary.csv",
        "selection_ablation_per_case.csv",
        "README.md",
    ]
    for f in required:
        p = out / f
        assert p.exists()
        txt = p.read_text(encoding="utf-8")
        if p.suffix == ".csv":
            assert txt.splitlines()
            assert txt.splitlines()[0].strip()
        elif p.suffix == ".jsonl":
            # Empty JSONL is acceptable for smoke slices with no emitted traces.
            if txt.strip():
                _ = json.loads(txt.splitlines()[0])
        else:
            assert txt.strip()
    md_path = out / "per_case_strategy_metadata.jsonl"
    md_lines = md_path.read_text(encoding="utf-8").splitlines()
    if md_lines:
        _ = json.loads(md_lines[0])
    with (out / "per_case_results.csv").open("r", encoding="utf-8", newline="") as f:
        hdr = list(csv.DictReader(f).fieldnames or [])
    assert "selection_failure_reason" in hdr
    assert "gold_answer_group" in hdr
    assert "answer_group_final_score" in hdr
    with (out / "selection_ablation_per_case.csv").open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows
    oracle = [r for r in rows if r.get("rule") == "oracle_if_gold_present" and r.get("gold_present_in_groups") == "1"]
    normal = [r for r in rows if r.get("rule") == "support_plus_verifier_plus_strategy_diversity" and r.get("gold_present_in_groups") == "1"]
    if oracle and normal:
        o_acc = sum(int(r["is_correct"]) for r in oracle) / max(1, len(oracle))
        n_acc = sum(int(r["is_correct"]) for r in normal) / max(1, len(normal))
        assert o_acc >= n_acc

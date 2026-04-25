from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode
from experiments.reasoning_diversity import (
    compute_reasoning_diversity_components,
    extract_intermediate_values,
    extract_operation_sequence,
    infer_reasoning_role,
)

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)


def test_operation_sequence_extraction_simple_arithmetic() -> None:
    ops = extract_operation_sequence("Add 3 + 4 then divide by 2 to get average")
    assert "add" in ops
    assert "divide" in ops


def test_intermediate_value_extraction() -> None:
    vals = extract_intermediate_values("Compute 12, then 3/4, and 25% and 7.50")
    assert "12" in vals
    assert "3/4" in vals
    assert "25%" in vals
    assert "7.5" in vals


def test_reasoning_role_inference() -> None:
    assert infer_reasoning_role("Check the result to verify") == "verification"
    assert infer_reasoning_role("Split into two cases") == "case_split"


def test_redundancy_and_novelty_components() -> None:
    existing = [
        {
            "strategy_family": "fam_a",
            "operation_sequence_key": "add|divide",
            "intermediate_values": ["2", "3"],
            "reasoning_role": "direct_solve",
            "answer_group": "10",
        }
    ]
    dup = {
        "strategy_family": "fam_a",
        "operation_sequence_key": "add|divide",
        "intermediate_values": ["2", "3"],
        "reasoning_role": "direct_solve",
        "answer_group": "10",
        "text_available": True,
    }
    novel = {
        "strategy_family": "fam_b",
        "operation_sequence_key": "case_split|add",
        "intermediate_values": ["9"],
        "reasoning_role": "case_split",
        "answer_group": "11",
        "text_available": True,
    }
    dup_c = compute_reasoning_diversity_components(dup, existing)
    nov_c = compute_reasoning_diversity_components(novel, existing)
    assert dup_c["redundancy_penalty"] >= 0.7
    assert nov_c["operation_sequence_novelty"] >= 0.5
    assert nov_c["reasoning_role_novelty"] >= 0.5


def test_method_registered_default_strict_f3_unchanged() -> None:
    rng = __import__("random").Random(7)
    specs = build_frontier_strategies(
        generator_factory=generator_factory_for_mode(
            use_openai_api=False,
            rng=rng,
            openai_model="command-r-plus-08-2024",
            temperature=0.1,
            max_output_tokens=256,
            timeout_seconds=45,
            api_provider="cohere",
        ),
        budget=4,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    assert STRICT_F3_RUNTIME in specs
    assert "strict_f3_reasoning_diversity_bonus_v1" in specs


def test_dry_run_eval_writes_required_outputs() -> None:
    ts = "20260425T230500Z"
    subprocess.check_call(
        [
            sys.executable,
            "scripts/run_reasoning_diversity_bonus_eval.py",
            "--timestamp",
            ts,
            "--slice",
            "ten_case",
            "--max-cases",
            "1",
            "--dry-run",
            "--emit-traces",
            "--skip-real-api-if-no-key",
        ]
    )
    out = Path("outputs") / f"reasoning_diversity_bonus_eval_{ts}"
    required_csv = [
        "summary.csv",
        "slice_summary.csv",
        "per_case_results.csv",
        "reasoning_signature_summary.csv",
        "operation_sequence_summary.csv",
        "intermediate_value_summary.csv",
        "answer_group_diversity_summary.csv",
        "repair_cases.csv",
        "hurt_cases.csv",
        "missing_fields_report.csv",
    ]
    for name in required_csv:
        p = out / name
        assert p.exists()
        with p.open("r", encoding="utf-8", newline="") as f:
            header = next(csv.reader(f), [])
        assert header
    for name in ["per_branch_reasoning_diversity.jsonl", "per_decision_reasoning_diversity.jsonl"]:
        p = out / name
        assert p.exists()
        for line in p.read_text(encoding="utf-8").splitlines():
            json.loads(line)

from __future__ import annotations

import csv
import json
import os
import random
import subprocess
import sys
from pathlib import Path

from experiments.branching import SimulatedBranchGenerator
from experiments.controllers import DirectReserveFrontierGateController, MethodResult
from experiments.frontier_matrix_core import build_frontier_strategies
from experiments.trace_schema import build_branch_trace, fill_missing_trace_fields, write_trace_package

REPO = Path(__file__).resolve().parents[1]


class _DummyScorer:
    def score_branch(self, branch) -> float:
        return float(getattr(branch, "score", 0.0))

    def pick_best(self, branches):
        return branches[0] if branches else None


def test_schema_helper_fills_missing_optional_fields_safely() -> None:
    trace = fill_missing_trace_fields({"top_level": {"example_id": "ex"}})
    assert trace["top_level"]["example_id"] == "ex"
    assert trace["direct_reserve"]["direct_reserve_answer"] is None
    assert trace["frontier_candidate"]["frontier_candidate_support"] is None
    assert trace["answer_groups"]["answer_group_support_counts"] == {}
    assert trace["branches"] == []


def test_write_trace_package_creates_candidate_and_answer_group_tables(tmp_path: Path) -> None:
    result = MethodResult(
        method="strict_f3",
        prediction="10",
        is_correct=True,
        actions_used=1,
        expansions=1,
        verifications=0,
        avg_surviving_branches=1.0,
        budget_exhausted=False,
        metadata={
            "selected_group": "10",
            "answer_group_support_counts": {"10": 1},
            "final_branch_states": [
                {
                    "branch_id": "b1",
                    "branch_depth": 1,
                    "predicted_answer": "10",
                    "score": 0.7,
                    "is_done": True,
                    "strategy_family": "direct_formula_family",
                }
            ],
        },
    )
    trace = build_branch_trace(result=result, example_id="ex", dataset="d", method="strict_f3", gold_answer="10")
    stats = write_trace_package(tmp_path, [trace])
    assert stats["n_branches"] == 1
    assert (tmp_path / "candidate_branch_table.csv").exists()
    assert (tmp_path / "answer_group_table.csv").exists()
    assert list(csv.DictReader((tmp_path / "candidate_branch_table.csv").open()))
    assert list(csv.DictReader((tmp_path / "answer_group_table.csv").open()))


def test_direct_reserve_frontier_gate_metadata_includes_override_fields() -> None:
    ctrl = DirectReserveFrontierGateController(
        generator=SimulatedBranchGenerator(random.Random(17), max_depth=3, finish_prob_base=0.2, answer_noise=0.1),
        scorer=_DummyScorer(),
        max_actions_per_problem=5,
        strict_controller_factory=lambda _remaining: type(
            "S",
            (),
            {
                "run": lambda _self, _q, _g: MethodResult(
                    method="frontier",
                    prediction="11",
                    is_correct=False,
                    actions_used=1,
                    expansions=1,
                    verifications=0,
                    avg_surviving_branches=1.0,
                    budget_exhausted=False,
                    metadata={"answer_group_support_counts": {"11": 2}, "final_branch_states": []},
                )
            },
        )(),
        direct_reserve_attempts_override=1,
    )
    ctrl._run_direct_attempt = lambda _q, _g, _idx, _max: ("10", 1, [])  # type: ignore[method-assign]
    res = ctrl.run("q", "10")
    md = res.metadata
    for field in [
        "reserve_used",
        "frontier_override_triggered",
        "override_margin",
        "override_reason",
        "direct_frontier_agree",
        "incumbent_support",
        "frontier_support",
        "support_margin",
        "maturity_margin",
        "override_thresholds",
        "guard_decision_inputs",
    ]:
        assert field in md


def test_strict_f3_metadata_has_answer_group_support_when_trace_enabled() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(5), max_depth=4, finish_prob_base=0.4, answer_noise=0.1
        ),
        budget=4,
        adaptive_min_expand_grid=[1],
        rng=random.Random(6),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    ctrl = specs["strict_f3_anti_collapse_default_v1"]
    setattr(ctrl, "emit_full_traces", True)
    res = ctrl.run("What is 2 + 2?", "4")
    assert isinstance(res.metadata.get("answer_group_support_counts"), dict)
    assert res.metadata.get("final_branch_states") is not None


def test_trace_smoke_no_real_api_unless_explicitly_allowed(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["COHERE_API_KEY"] = "should-not-be-used"
    ts = "TEST_TRACE_SCHEMA_OFFLINE"
    subprocess.check_call(
        [sys.executable, str(REPO / "scripts" / "run_direct_reserve_frontier_gate_trace_smoke.py"), "--timestamp", ts],
        cwd=REPO,
        env=env,
    )
    out = REPO / "outputs" / f"direct_reserve_frontier_gate_trace_smoke_{ts}"
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["real_api_allowed"] is False
    assert manifest["real_api_used"] is False
    assert list(csv.DictReader((out / "candidate_branch_table.csv").open()))
    assert list(csv.DictReader((out / "answer_group_table.csv").open()))

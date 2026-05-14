"""Tests for run_cohere_100case_best_vs_external_l1max.py runner.

Verifies:
- factory-built ObservedGenerator produces non-empty final_nodes after a run
- classify_result returns non-None surfaced_answer_raw when final_nodes is populated
- candidate_answers is non-empty after a real strategy run
- registry is cleared between cases
- gold_answer is never embedded in the question sent to the generator
- failure records preserve candidate traces
- no post-hoc _wrap_generator / _Dummy fallback exists in the module
- no API calls are made (all tests use SimulatedBranchGenerator)
"""
import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import BranchState, SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies
from scripts.run_cohere_100case_best_vs_external_l1max import (
    METHOD_REGISTRY,
    BEST_RUNTIME,
    EXTERNAL_RUNTIME,
    ObservedGenerator,
    classify_result,
    build_failure_record,
    run_case,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sim_gen(seed: int = 42) -> SimulatedBranchGenerator:
    return SimulatedBranchGenerator(
        rng=random.Random(seed),
        max_depth=4,
        finish_prob_base=0.8,
        answer_noise=0.0,
    )


def _make_sim_factory(seed: int = 42):
    """Return a factory that always wraps a SimulatedBranchGenerator in ObservedGenerator."""
    def factory():
        return ObservedGenerator(_make_sim_gen(seed))
    return factory


def _build_strategies_sim(runtime: str, budget: int = 6, seed: int = 42) -> dict[str, Any]:
    rng = random.Random(seed)
    specs = build_frontier_strategies(
        _make_sim_factory(seed),
        budget,
        [1],
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    assert runtime in specs, f"runtime {runtime!r} not found in specs"
    return specs


# ---------------------------------------------------------------------------
# ObservedGenerator unit tests
# ---------------------------------------------------------------------------

def test_observed_generator_registry_populated_after_init_branch():
    sim = _make_sim_gen()
    obs = ObservedGenerator(sim)
    assert len(obs.registry) == 0
    b = obs.init_branch("b1")
    assert "b1" in obs.registry
    assert obs.registry["b1"] is b


def test_observed_generator_registry_cleared():
    sim = _make_sim_gen()
    obs = ObservedGenerator(sim)
    obs.init_branch("b1")
    obs.init_branch("b2")
    assert len(obs.registry) == 2
    obs.registry.clear()
    assert len(obs.registry) == 0


def test_snapshot_includes_predicted_answer_and_reasoning():
    sim = _make_sim_gen()
    obs = ObservedGenerator(sim)
    b = obs.init_branch("b1")
    # expand so the branch gets a predicted answer
    obs.expand(b, "What is 2+2?", "4")
    snap = obs._snapshot(b)
    assert "predicted_answer" in snap
    assert "reasoning_text" in snap
    assert "branch_id" in snap
    assert snap["branch_id"] == "b1"


# ---------------------------------------------------------------------------
# classify_result tests
# ---------------------------------------------------------------------------

def _fake_result(answer: str = "42", *, actions: int = 2, n_expansions: int = 2, n_verifications: int = 1) -> Any:
    """Create a minimal fake MethodResult-like object."""
    return SimpleNamespace(
        prediction=answer,
        actions_used=actions,
        expansions=n_expansions,
        verifications=n_verifications,
        avg_surviving_branches=1.0,
        budget_exhausted=False,
        metadata={},
        method="test",
    )


def _make_node(answer: str, score: float = 0.9) -> dict[str, Any]:
    return {
        "branch_id": f"b_{answer}",
        "score": score,
        "depth": 2,
        "is_done": True,
        "is_pruned": False,
        "predicted_answer": answer,
        "predicted_answer_normalized": answer,
        "reasoning_text": f"Step 1: compute. Answer: {answer}",
    }


def test_classify_result_correct_when_gold_matches():
    nodes = [_make_node("42"), _make_node("42"), _make_node("7")]
    result = _fake_result("42")
    cfg = {"enable_output_repair": True, "apply_pal_fix": False}
    cls = classify_result(result, nodes, "42", cfg)
    assert cls["is_correct"] == 1
    assert cls["surfaced_answer_raw"] is not None
    assert cls["candidate_answers"] == ["42", "42", "7"]


def test_classify_result_wrong_when_gold_missing():
    nodes = [_make_node("7"), _make_node("8")]
    result = _fake_result("7")
    cfg = {"enable_output_repair": True, "apply_pal_fix": False}
    cls = classify_result(result, nodes, "42", cfg)
    assert cls["is_correct"] == 0
    assert cls["gold_in_tree"] == 0
    assert cls["failure_type"] == "absent_from_tree"


def test_classify_result_non_empty_candidate_answers():
    nodes = [_make_node("5"), _make_node("5"), _make_node("3")]
    result = _fake_result("5")
    cfg = {"enable_output_repair": True, "apply_pal_fix": False}
    cls = classify_result(result, nodes, "3", cfg)
    assert len(cls["candidate_answers"]) == 3
    assert "5" in cls["candidate_answers"]


def test_classify_result_empty_nodes_gives_no_surface():
    result = _fake_result("42")
    cfg = {"enable_output_repair": True, "apply_pal_fix": False}
    cls = classify_result(result, [], "42", cfg)
    assert cls["surfaced_answer_raw"] is None
    assert cls["is_correct"] == 0


def test_classify_result_pal_fix_with_empty_metadata_preserves_surfaced_answer():
    """When apply_pal_fix=True but PAL gates fail (empty metadata), surfaced_answer_raw
    must NOT be overwritten by the sidecar dict.  Regression test for the bug where
    the caller did `md, repaired = apply_pal_residual_strong_integration_fix(...)`,
    which assigned the sidecar (no surfaced_final_answer_raw) to `repaired`."""
    nodes = [_make_node("42"), _make_node("42"), _make_node("7")]
    result = _fake_result("42")
    # apply_pal_fix=True but metadata has no PAL execution fields → gates fail, sidecar returned
    cfg = {"enable_output_repair": True, "apply_pal_fix": True}
    cls = classify_result(result, nodes, "42", cfg)
    # surfaced_answer_raw must come from the repaired dict (not the sidecar)
    assert cls["surfaced_answer_raw"] is not None, (
        "surfaced_answer_raw must not be None when nodes are populated, "
        "even when PAL gates fail and apply_pal_fix=True"
    )
    assert cls["is_correct"] == 1


def test_classify_result_candidate_traces_populated():
    nodes = [_make_node("12"), _make_node("15")]
    result = _fake_result("12")
    cfg = {"enable_output_repair": True, "apply_pal_fix": False}
    cls = classify_result(result, nodes, "12", cfg)
    assert len(cls["candidate_traces"]) == 2
    assert all(isinstance(t, str) for t in cls["candidate_traces"])


# ---------------------------------------------------------------------------
# Factory / strategy integration (no API calls)
# ---------------------------------------------------------------------------

def test_factory_strategy_best_populates_registry():
    specs = _build_strategies_sim(BEST_RUNTIME, budget=6)
    controller = specs[BEST_RUNTIME]
    obs = getattr(controller, "generator", None)
    assert isinstance(obs, ObservedGenerator), "controller.generator must be an ObservedGenerator"
    obs.registry.clear()
    controller.run("How many apples are left if you start with 10 and eat 3?", "7")
    assert len(obs.registry) > 0, "registry must be non-empty after run"


def test_factory_strategy_external_l1_max_populates_registry():
    specs = _build_strategies_sim(EXTERNAL_RUNTIME, budget=6)
    controller = specs[EXTERNAL_RUNTIME]
    obs = getattr(controller, "generator", None)
    assert isinstance(obs, ObservedGenerator), "controller.generator must be an ObservedGenerator"
    obs.registry.clear()
    controller.run("A store sells 5 pens at $2 each. Total cost?", "10")
    assert len(obs.registry) > 0, "registry must be non-empty after run"


def test_registry_cleared_between_cases():
    specs = _build_strategies_sim(EXTERNAL_RUNTIME, budget=6)
    controller = specs[EXTERNAL_RUNTIME]
    obs = getattr(controller, "generator", None)
    assert isinstance(obs, ObservedGenerator)

    obs.registry.clear()
    controller.run("Q1: 2+2?", "4")
    after_case1 = len(obs.registry)
    assert after_case1 > 0

    obs.registry.clear()
    assert len(obs.registry) == 0, "registry must be empty after clear"

    controller.run("Q2: 3+3?", "6")
    assert len(obs.registry) > 0, "registry must repopulate for case 2"
    assert len(obs.registry) <= after_case1 + 5, "registry must not carry over branches from case 1"


def test_final_nodes_non_empty_from_factory_strategy():
    specs = _build_strategies_sim(BEST_RUNTIME, budget=6)
    controller = specs[BEST_RUNTIME]
    obs = getattr(controller, "generator", None)
    assert isinstance(obs, ObservedGenerator)
    obs.registry.clear()
    controller.run("A jar has 8 candies. You eat 3. How many remain?", "5")
    final_nodes = [obs._snapshot(b) for b in obs.registry.values()]
    assert len(final_nodes) > 0
    assert all("predicted_answer" in n for n in final_nodes)


# ---------------------------------------------------------------------------
# Gold leakage check
# ---------------------------------------------------------------------------

class _RecordingGen:
    """Minimal generator that records every question it receives."""
    def __init__(self):
        self.questions_seen: list[str] = []

    def init_branch(self, branch_id: str) -> BranchState:
        return BranchState(branch_id=branch_id, latent_quality=0.8, score=0.8)

    def expand(self, branch: BranchState, question: str, gold_answer: str) -> Any:  # noqa: ARG002
        self.questions_seen.append(question)
        branch.predicted_answer = "42"
        branch.is_done = True
        from experiments.branching import BranchActionResult
        return BranchActionResult("expand", branch.score, branch.score, True)

    def verify(self, branch: BranchState, question: str) -> Any:
        from experiments.branching import BranchActionResult
        return BranchActionResult("verify", branch.score, branch.score, branch.is_done)

    def prune(self, branch: BranchState) -> Any:
        from experiments.branching import BranchActionResult
        return BranchActionResult("prune", branch.score, branch.score, branch.is_done)


def test_gold_not_in_expand_question():
    """The question passed to the generator's expand must not contain the gold answer."""
    recorder = _RecordingGen()
    obs = ObservedGenerator(recorder)

    rng = random.Random(1)
    specs = build_frontier_strategies(
        lambda _obs=obs: _obs,
        6,
        [1],
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    gold = "SECRET_GOLD_1234"
    controller = specs[EXTERNAL_RUNTIME]
    obs.registry.clear()
    controller.run("How many apples?", gold)
    for q in recorder.questions_seen:
        assert gold not in q, f"Gold answer leaked into question text: {q!r}"


# ---------------------------------------------------------------------------
# run_case integration (no API)
# ---------------------------------------------------------------------------

def test_run_case_candidate_answers_non_empty():
    specs = _build_strategies_sim(EXTERNAL_RUNTIME, budget=6)
    controller = specs[EXTERNAL_RUNTIME]
    row = run_case(
        case_id="test_c1",
        question="A box has 10 items. 4 are removed. How many remain?",
        gold_raw="6",
        method_name="external_l1_max",
        method_cfg=METHOD_REGISTRY["external_l1_max"],
        runtime=EXTERNAL_RUNTIME,
        controller=controller,
        model="sim",
        run_id="test_run",
        sample_index=0,
        seed=42,
    )
    assert row["error"] is None, f"Unexpected error: {row['error']}"
    assert row.get("candidate_answers") is not None
    assert len(row["candidate_answers"]) > 0, "candidate_answers must be non-empty"


def test_run_case_best_candidate_answers_non_empty():
    """The best method must also produce non-empty candidate_answers via factory pattern."""
    specs = _build_strategies_sim(BEST_RUNTIME, budget=6)
    controller = specs[BEST_RUNTIME]
    row = run_case(
        case_id="test_c2",
        question="There are 5 red and 3 blue balls. How many total?",
        gold_raw="8",
        method_name="best",
        method_cfg=METHOD_REGISTRY["best"],
        runtime=BEST_RUNTIME,
        controller=controller,
        model="sim",
        run_id="test_run",
        sample_index=1,
        seed=42,
    )
    assert row["error"] is None
    # The KEY property: candidate_answers must be non-empty (registry populated via factory)
    assert len(row.get("candidate_answers", [])) > 0, "candidate_answers must be non-empty with factory pattern"


def test_run_case_external_l1max_surfaced_answer_raw_not_none():
    """external_l1_max (no PAL fix) must surface an answer when candidates exist."""
    specs = _build_strategies_sim(EXTERNAL_RUNTIME, budget=6)
    controller = specs[EXTERNAL_RUNTIME]
    row = run_case(
        case_id="test_c2b",
        question="There are 5 red and 3 blue balls. How many total?",
        gold_raw="8",
        method_name="external_l1_max",
        method_cfg=METHOD_REGISTRY["external_l1_max"],
        runtime=EXTERNAL_RUNTIME,
        controller=controller,
        model="sim",
        run_id="test_run",
        sample_index=1,
        seed=42,
    )
    assert row["error"] is None
    assert len(row.get("candidate_answers", [])) > 0, "candidate_answers must be non-empty"
    # surfaced_answer_raw must not be None when candidates are present and no PAL override
    assert row.get("surfaced_answer_raw") is not None, "surfaced_answer_raw must not be None"


def test_run_case_gold_not_in_schema_fields():
    """gold_answer_metadata_only must be present; gold must not appear in method_name/runtime fields."""
    specs = _build_strategies_sim(EXTERNAL_RUNTIME, budget=6)
    controller = specs[EXTERNAL_RUNTIME]
    gold = "SECRETGOLD99"
    row = run_case(
        case_id="test_c3",
        question="Simple math question.",
        gold_raw=gold,
        method_name="external_l1_max",
        method_cfg=METHOD_REGISTRY["external_l1_max"],
        runtime=EXTERNAL_RUNTIME,
        controller=controller,
        model="sim",
        run_id="test_run",
        sample_index=0,
        seed=42,
    )
    assert row["gold_answer_metadata_only"] == gold
    # Gold must not bleed into other fields
    for field in ("method_name", "runtime", "provider", "model", "question"):
        assert gold not in str(row.get(field, "")), f"Gold leaked into field {field!r}"


# ---------------------------------------------------------------------------
# Failure record tests
# ---------------------------------------------------------------------------

def test_failure_record_preserves_candidate_traces():
    row = {
        "case_id": "fc1",
        "question": "Q",
        "gold_answer_metadata_only": "5",
        "method_name": "best",
        "failure_type": "absent_from_tree",
        "is_correct": 0,
        "gold_in_tree": 0,
        "surfaced_answer_raw": "7",
        "surfaced_answer_canonical": "7",
        "selected_answer_support": 2,
        "unique_candidate_answers": 2,
        "candidate_answers": ["7", "8"],
        "candidate_traces": ["trace A", "trace B"],
        "final_nodes": [],
        "controller_metadata": {},
        "repair_metadata": {},
        "api_token_usage": {},
        "latency_seconds": 3.5,
        "error": None,
    }
    fr = build_failure_record(row)
    assert fr["all_candidate_traces"] == ["trace A", "trace B"]
    assert fr["all_candidate_answers"] == ["7", "8"]
    assert fr["case_id"] == "fc1"
    assert fr["gold_answer_metadata_only"] == "5"
    assert "failure_hints" in fr


def test_failure_record_gold_not_exposed_in_inappropriate_fields():
    gold = "GOLD123"
    row = {
        "case_id": "fc2",
        "question": "A question",
        "gold_answer_metadata_only": gold,
        "method_name": "external_l1_max",
        "failure_type": "absent_from_tree",
        "is_correct": 0,
        "gold_in_tree": 0,
        "surfaced_answer_raw": "9",
        "surfaced_answer_canonical": "9",
        "selected_answer_support": 1,
        "unique_candidate_answers": 1,
        "candidate_answers": ["9"],
        "candidate_traces": ["step 1: compute answer 9"],
        "final_nodes": [],
        "controller_metadata": {},
        "repair_metadata": {},
        "api_token_usage": {},
        "latency_seconds": 2.0,
        "error": None,
    }
    fr = build_failure_record(row)
    # Gold IS stored under the designated field
    assert fr["gold_answer_metadata_only"] == gold
    # Gold must NOT appear in method_name, failure_type, notes
    for field in ("method_name", "failure_type", "notes"):
        assert gold not in str(fr.get(field, ""))


# ---------------------------------------------------------------------------
# Structural: no _wrap_generator / _Dummy in module
# ---------------------------------------------------------------------------

def test_no_wrap_generator_in_module():
    import scripts.run_cohere_100case_best_vs_external_l1max as mod
    assert not hasattr(mod, "_wrap_generator"), (
        "_wrap_generator must be removed from the module"
    )


def test_no_dummy_fallback_in_module():
    import scripts.run_cohere_100case_best_vs_external_l1max as mod
    src = Path(mod.__file__).read_text()
    assert "_Dummy" not in src, (
        "_Dummy fallback generator must not exist in the fixed module"
    )


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v"])

from __future__ import annotations

import random

import numpy as np

from experiments.branching import BranchActionResult, BranchState
from experiments.controllers import DirectReserveGateRerankController
from experiments.frontier_matrix_core import build_frontier_strategies
from experiments.scoring import ScoreConfig, SimpleBranchScorer
from scripts.direct_reserve_learned_override_utils import (
    RECOMMENDED_MODEL_TYPES,
    build_runtime_answer_group_candidates,
    select_learned_override,
)


class _IdentityVectorizer:
    def transform(self, rows):
        return rows


class _SupportModel:
    def predict_proba(self, rows):
        vals = [float(r.get("f_answer_group_support", 0.0)) for r in rows]
        return np.asarray([[1.0 - min(0.99, v / 10.0), min(0.99, v / 10.0)] for v in vals], dtype=float)


class _FakeGenerator:
    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.i = 0

    def init_branch(self, branch_id: str) -> BranchState:
        return BranchState(branch_id=branch_id, latent_quality=0.8, score=0.8)

    def expand(self, branch: BranchState, question: str, gold_answer: str) -> BranchActionResult:
        answer = self.answers[min(self.i, len(self.answers) - 1)]
        self.i += 1
        branch.steps.append("step")
        branch.predicted_answer = answer
        branch.is_done = True
        branch.trace_events.append(
            {
                "prompt_text": question,
                "response_text": answer,
                "reasoning_text": "r",
                "extracted_answer": answer,
            }
        )
        return BranchActionResult("expand", 0.8, 0.8, True)

    @staticmethod
    def verify(branch: BranchState, question: str) -> BranchActionResult:
        return BranchActionResult("verify", branch.score, branch.score, branch.is_done)

    @staticmethod
    def prune(branch: BranchState) -> BranchActionResult:
        branch.is_pruned = True
        return BranchActionResult("prune", branch.score, branch.score, branch.is_done)


def _payload() -> dict:
    return {"vectorizer": _IdentityVectorizer(), "rf": _SupportModel()}


def _candidates() -> list[dict]:
    return build_runtime_answer_group_candidates(
        question="q",
        dataset="openai/gsm8k",
        seed=0,
        budget=4,
        method="direct_reserve_strong_plus_diverse_v1",
        candidate_answers=["1", "2", "2"],
        selected_group="1",
        top2_support_gap=1 / 3,
        answer_entropy=0.9,
        action_count=3,
        expansion_count=3,
        verification_count=0,
    )


def test_method_registration_includes_opt_in_override() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: _FakeGenerator(["1", "2"]),
        budget=4,
        adaptive_min_expand_grid=[],
        rng=random.Random(0),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    assert "direct_reserve_strong_plus_diverse_learned_override_v1" in specs
    assert specs["direct_reserve_strong_plus_diverse_learned_override_v1"].method_name == "direct_reserve_strong_plus_diverse_learned_override_v1"
    assert specs["direct_reserve_strong_plus_diverse_v1"].method_name == "direct_reserve_strong_plus_diverse_v1"


def test_missing_model_falls_back_to_base() -> None:
    result = select_learned_override(_candidates(), base_selected_answer="1", model_path="/tmp/does-not-exist.joblib")
    assert result.final_answer == "1"
    assert result.metadata["learned_override_available"] is False
    assert result.metadata["learned_override_reason"] == "model_missing"


def test_missing_feature_falls_back_to_base() -> None:
    cands = _candidates()
    cands[0].pop("answer_group_support")
    result = select_learned_override(cands, base_selected_answer="1", model_payload=_payload())
    assert result.final_answer == "1"
    assert result.metadata["learned_override_reason"] == "missing_required_features"
    assert "answer_group_support" in result.metadata["learned_override_missing_features"]


def test_conservative_threshold_blocks_override() -> None:
    result = select_learned_override(_candidates(), base_selected_answer="1", model_payload=_payload(), margin_threshold=0.5)
    assert result.final_answer == "1"
    assert result.metadata["learned_override_triggered"] is False
    assert result.metadata["learned_override_reason"] == "below_margin_threshold"


def test_high_margin_override_changes_answer() -> None:
    result = select_learned_override(_candidates(), base_selected_answer="1", model_payload=_payload(), margin_threshold=0.01)
    assert result.final_answer == "2"
    assert result.metadata["learned_override_triggered"] is True
    assert result.metadata["learned_override_reason"] == "margin_threshold_met"


def test_controller_emits_learned_override_metadata_on_fallback() -> None:
    ctrl = DirectReserveGateRerankController(
        _FakeGenerator(["1", "2"]),
        SimpleBranchScorer(ScoreConfig()),
        2,
        strict_controller_factory=lambda remaining_budget: None,
        direct_prompt_styles=["a", "b"],
        direct_reserve_attempts_override=2,
        enable_learned_override=True,
        learned_override_model_path="/tmp/no-model.joblib",
        method_name="direct_reserve_strong_plus_diverse_learned_override_v1",
    )
    res = ctrl.run("q", "1")
    for key in (
        "learned_override_available",
        "learned_override_triggered",
        "learned_override_model",
        "learned_override_margin",
        "learned_override_threshold",
        "base_selected_answer",
        "learned_selected_answer",
        "final_selected_answer",
        "learned_override_reason",
        "learned_override_missing_features",
        "candidate_feature_schema_version",
        "candidate_count",
        "answer_group_count",
    ):
        assert key in res.metadata
    assert res.metadata["learned_override_reason"] == "model_missing"


def test_strict_f3_registration_unchanged() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: _FakeGenerator(["1"]),
        budget=4,
        adaptive_min_expand_grid=[],
        rng=random.Random(0),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    assert "strict_f3_direct_reserve_gate_rerank_v1" in specs
    assert specs["strict_f3_direct_reserve_gate_rerank_v1"].method_name == "strict_f3_direct_reserve_gate_rerank_v1"
    assert not getattr(specs["strict_f3_direct_reserve_gate_rerank_v1"], "enable_learned_override", False)


def test_hgb_is_not_recommended_or_allowed_for_override() -> None:
    assert "hist_gboost" not in RECOMMENDED_MODEL_TYPES
    result = select_learned_override(_candidates(), base_selected_answer="1", model_payload={"hgb": object()}, model_type="hist_gboost")
    assert result.final_answer == "1"
    assert result.metadata["learned_override_reason"] == "hgb_not_allowed"

from __future__ import annotations

import random
import pickle
from pathlib import Path

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
from scripts.run_direct_reserve_learned_override_runtime_eval import build_eval


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


def _write_payload(path: Path) -> Path:
    path.write_bytes(pickle.dumps(_payload()))
    return path


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


def _direct_reserve_config(ctrl: DirectReserveGateRerankController) -> dict:
    return {
        "direct_prompt_style": ctrl.direct_prompt_style,
        "direct_prompt_styles": tuple(ctrl.direct_prompt_styles),
        "direct_reserve_attempts_override": ctrl.direct_reserve_attempts_override,
        "direct_token_budget": ctrl.direct_token_budget,
        "direct_token_per_action": ctrl.direct_token_per_action,
        "gate_top_support_threshold": ctrl.gate_top_support_threshold,
        "gate_top2_gap_threshold": ctrl.gate_top2_gap_threshold,
        "gate_entropy_threshold": ctrl.gate_entropy_threshold,
        "enable_margin_gate_fallback": ctrl.enable_margin_gate_fallback,
        "margin_gate_min_support_gap": ctrl.margin_gate_min_support_gap,
        "margin_gate_max_entropy": ctrl.margin_gate_max_entropy,
        "margin_gate_require_multi_prompt_style": ctrl.margin_gate_require_multi_prompt_style,
    }


def _base_controller(answers: list[str], max_actions: int = 3) -> DirectReserveGateRerankController:
    return DirectReserveGateRerankController(
        _FakeGenerator(answers),
        SimpleBranchScorer(ScoreConfig()),
        max_actions,
        strict_controller_factory=lambda remaining_budget: None,
        direct_prompt_styles=["a", "b"],
        direct_reserve_attempts_override=max_actions,
        method_name="direct_reserve_strong_plus_diverse_v1",
    )


def _learned_controller(
    answers: list[str],
    *,
    model_path: str,
    margin: float = 0.05,
    max_actions: int = 3,
) -> DirectReserveGateRerankController:
    return DirectReserveGateRerankController(
        _FakeGenerator(answers),
        SimpleBranchScorer(ScoreConfig()),
        max_actions,
        strict_controller_factory=lambda remaining_budget: None,
        direct_prompt_styles=["a", "b"],
        direct_reserve_attempts_override=max_actions,
        enable_learned_override=True,
        learned_override_model_path=model_path,
        learned_override_margin=margin,
        method_name="direct_reserve_strong_plus_diverse_learned_override_v1",
    )


def test_no_model_controller_fallback_equals_base() -> None:
    base = _base_controller(["1", "2", "2"]).run("q", "2")
    learned = _learned_controller(["1", "2", "2"], model_path="/tmp/does-not-exist.joblib").run("q", "2")

    assert learned.prediction == base.prediction
    assert learned.metadata["learned_override_available"] is False
    assert learned.metadata["learned_override_triggered"] is False
    assert learned.metadata["final_selected_answer"] == learned.metadata["base_selected_answer"]
    assert learned.metadata["final_selected_answer"] == "2"


def test_high_threshold_no_override_equals_base(tmp_path: Path) -> None:
    model_path = _write_payload(tmp_path / "model.joblib")
    base = _base_controller(["1", "2", "2"]).run("q", "2")
    learned = _learned_controller(["1", "2", "2"], model_path=str(model_path), margin=999.0).run("q", "2")

    assert learned.prediction == base.prediction
    assert learned.metadata["learned_override_available"] is True
    assert learned.metadata["learned_override_triggered"] is False
    assert learned.metadata["final_selected_answer"] == learned.metadata["base_selected_answer"]
    assert learned.metadata["final_selected_answer"] == "2"


def test_missing_feature_fallback_metadata_preserves_base_answer() -> None:
    cands = _candidates()
    base_answer = "1"
    cands[0].pop("answer_group_support")

    result = select_learned_override(cands, base_selected_answer=base_answer, model_payload=_payload())

    assert result.final_answer == base_answer
    assert result.metadata["learned_override_triggered"] is False
    assert result.metadata["final_selected_answer"] == base_answer
    assert result.metadata["learned_override_reason"] == "missing_required_features"
    assert "answer_group_support" in result.metadata["learned_override_missing_features"]


def test_valid_high_margin_override_metadata_is_consistent() -> None:
    result = select_learned_override(_candidates(), base_selected_answer="1", model_payload=_payload(), margin_threshold=0.01)

    assert result.final_answer == "2"
    assert result.metadata["base_selected_answer"] == "1"
    assert result.metadata["learned_selected_answer"] == "2"
    assert result.metadata["final_selected_answer"] == result.metadata["learned_selected_answer"]
    assert result.metadata["learned_override_triggered"] is True
    assert result.metadata["learned_override_reason"] == "margin_threshold_met"


def test_direct_reserve_plus_diverse_registration_parity_before_selector() -> None:
    specs = build_frontier_strategies(
        generator_factory=lambda: _FakeGenerator(["1", "2"]),
        budget=4,
        adaptive_min_expand_grid=[],
        rng=random.Random(0),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    base = specs["direct_reserve_strong_plus_diverse_v1"]
    learned = specs["direct_reserve_strong_plus_diverse_learned_override_v1"]

    assert _direct_reserve_config(base) == _direct_reserve_config(learned)
    assert base.enable_learned_override is False
    assert learned.enable_learned_override is True


def _write_rows(path: Path, rows: list[dict]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        import csv

        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def test_runtime_eval_labels_unpaired_no_trigger_delta_not_selector_degradation(tmp_path: Path) -> None:
    validation_dir = tmp_path / "validation"
    _write_rows(
        validation_dir / "per_case_method_results.csv",
        [
            {
                "example_id": "case_1",
                "seed": 53,
                "budget": 4,
                "method": "direct_reserve_strong_plus_diverse_v1",
                "gold_answer": "2",
                "normalized_selected_answer": "2",
                "gold_selected": 1,
            },
            {
                "example_id": "case_1",
                "seed": 53,
                "budget": 4,
                "method": "direct_reserve_strong_plus_diverse_learned_override_v1",
                "gold_answer": "2",
                "normalized_selected_answer": "1.5",
                "gold_selected": 0,
                "base_selected_answer": "1.5",
                "learned_selected_answer": "1.5",
                "final_selected_answer_after_learned_override": "1.5",
                "learned_override_available": 1,
                "learned_override_triggered": 0,
                "learned_override_margin": 0.15,
                "learned_override_reason": "learned_matches_base",
            },
        ],
    )
    _write_rows(validation_dir / "candidate_branch_table.csv", [])
    _write_rows(validation_dir / "answer_group_summary.csv", [])
    _write_rows(validation_dir / "coverage_summary.csv", [{"real_api_enabled": 1}])

    summary = build_eval(validation_dir=validation_dir, out_dir=tmp_path / "eval", plan_dir=None)

    assert summary["unpaired_generation_degradation_count"] == 1
    assert summary["selector_triggered_degradation_count"] == 0
    assert summary["no_override_fallback_mismatch_count"] == 0

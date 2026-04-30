from __future__ import annotations

import math

from experiments.answer_grouped_outcome_verifier import CandidateAnswer
from experiments.prm_step_verifier_rerank import (
    CohereStepVerifier,
    DeterministicMockStepVerifier,
    StepVerifierResult,
    aggregate_trace_score,
    build_prm_candidates_from_dr_v2_metadata,
    build_prm_step_verifier_prompt,
    build_candidates_from_dr_v2_metadata,
    select_answer_group_with_prm_step_verifier,
    split_trace_into_steps,
)
from experiments.controllers import (
    DirectReserveFrontierGateV2Controller,
    DirectReserveFrontierGateV2PRMStepVerifierRerankV1Controller,
    MethodResult,
)


def _c(cid: str, ans: str, trace: str) -> CandidateAnswer:
    return CandidateAnswer(
        candidate_id=cid,
        problem="p",
        trace=trace,
        final_answer=ans,
        normalized_answer=ans.strip().lower(),
        source_id=cid,
    )


def test_split_numbered_then_lines_then_markers():
    t1 = "1. First line.\n2. Second line."
    s1 = split_trace_into_steps(t1)
    assert len(s1) >= 2
    assert "First line" in s1[0] or s1[0].startswith("First")

    t2 = "longer line alpha here\nlonger line beta here\nlonger line gamma here"
    s2 = split_trace_into_steps(t2)
    assert s2 == ["longer line alpha here", "longer line beta here", "longer line gamma here"]

    t3 = "Intro Then middle Thus end"
    s3 = split_trace_into_steps(t3)
    assert len(s3) >= 1


def test_split_merges_short_fragments_and_nonempty_returns_at_least_one():
    merged = split_trace_into_steps("1. a\n2. xx")
    assert len(merged) >= 1
    assert split_trace_into_steps("") == []
    assert len(split_trace_into_steps("only")) == 1


def test_build_prm_candidates_matches_dr_v2_helper():
    md = {
        "final_branch_states": [
            {
                "branch_id": "b1",
                "predicted_answer": "7",
                "source": "frontier",
                "trace_events": [{"reasoning_text": "think"}],
                "branch_depth": 1,
            }
        ]
    }
    a = build_prm_candidates_from_dr_v2_metadata("Q?", md)
    b = build_candidates_from_dr_v2_metadata("Q?", md)
    assert len(a) == len(b) == 1
    assert a[0].candidate_id == b[0].candidate_id


def test_mock_step_verifier_markers_deterministic():
    v = DeterministicMockStepVerifier()
    bad = v.verify_step("q", [], "this is wrong", "1")
    assert bad.major_error is True
    good = v.verify_step("q", [], "compute 42", "42")
    assert good.major_error is False
    assert good.validity_score >= 0.8


def test_prm_prompt_no_gold_string_and_no_secret_answer_leak():
    system, user = build_prm_step_verifier_prompt("What is 2+2?", [], "step", "4")
    blob = (system + user).lower()
    assert "gold" not in blob
    assert "reference answer" not in blob
    secret = "SECRET_GOLD_314159"
    sys2, usr2 = build_prm_step_verifier_prompt("x", [], "y", "z")
    assert secret not in sys2 + usr2


def test_cohere_step_verifier_json_and_parse_fallback():
    class _Part:
        def __init__(self, text: str) -> None:
            self.text = text

    class _Message:
        def __init__(self, content: list[_Part]) -> None:
            self.content = content

    class _Resp:
        def __init__(self, text: str) -> None:
            self.message = _Message([_Part(text)])

    class _Client:
        def __init__(self, text: str) -> None:
            self._text = text

        def chat(self, **kwargs):  # noqa: ANN001, ARG002
            return _Resp(self._text)

    ok = CohereStepVerifier(
        client=_Client(
            '{"validity_score": 0.9, "progress_score": 0.8, "major_error": false, "short_reason": "ok"}'
        )
    )
    r1 = ok.verify_step("q", [], "s", "1")
    assert math.isclose(r1.validity_score, 0.9)
    assert r1.parse_fallback is False

    fb = CohereStepVerifier(client=_Client("not json at all"))
    r2 = fb.verify_step("q", [], "s", "1")
    assert r2.validity_score == 0.5
    assert r2.parse_fallback is True
    assert "parse" in r2.short_reason.lower() or "json" in r2.short_reason.lower()


def test_aggregate_trace_score_mean_min_progress_and_major_error():
    # All validity 1, progress 0.5 -> q_i=1, u_i = 0.7*1 + 0.3*0.5 = 0.85
    steps_ok = [
        StepVerifierResult(1.0, 0.5, False, "a", False),
        StepVerifierResult(1.0, 0.5, False, "b", False),
    ]
    assert math.isclose(aggregate_trace_score(steps_ok), 0.85, rel_tol=1e-9)

    # No progress scores -> u_i = q_i only
    steps_no_p = [StepVerifierResult(1.0, None, False, "a", False), StepVerifierResult(0.0, None, False, "b", False)]
    q = 0.7 * 0.5 + 0.3 * 0.0
    assert math.isclose(aggregate_trace_score(steps_no_p), q, rel_tol=1e-9)

    major = [StepVerifierResult(1.0, 1.0, True, "e", False)]
    assert aggregate_trace_score(major) <= 0.25


def test_answer_group_sum_and_best_trace_in_group():
    cands = [
        _c("w", "10", "1. a\n2. b"),
        _c("w2", "10", "1. c"),
        _c("l", "11", "1. d"),
    ]

    class V:
        def verify_step(self, problem, prefix_steps, current_step, final_answer):  # noqa: ANN001
            if final_answer == "11":
                return StepVerifierResult(1.0, 1.0, False, "good", False)
            return StepVerifierResult(0.3, 0.2, False, "meh", False)

    dec = select_answer_group_with_prm_step_verifier(cands, V(), verifier_backend="mock", verifier_model="m")
    assert dec.selected_answer == "11"
    assert dec.selected_candidate_id == "l"
    assert dec.selected_group_score > 0.0


def test_synthetic_present_not_selected_recovery_via_step_scores():
    cands = [
        _c("bad", "12", "wrong step"),
        _c("good", "13", "solid reasoning thirteen"),
    ]

    class V:
        def verify_step(self, problem, prefix_steps, current_step, final_answer):  # noqa: ANN001
            if final_answer.strip() == "13":
                return StepVerifierResult(1.0, 1.0, False, "ok", False)
            return StepVerifierResult(0.1, 0.1, False, "no", False)

    dec = select_answer_group_with_prm_step_verifier(cands, V())
    assert dec.selected_answer == "13"


class _DummyGenerator:
    def init_branch(self, branch_id):  # noqa: ANN001
        raise RuntimeError("unused")

    def expand(self, branch, question, gold_answer):  # noqa: ANN001
        raise RuntimeError("unused")

    def verify(self, branch, question):  # noqa: ANN001
        raise RuntimeError("unused")

    def prune(self, branch):  # noqa: ANN001
        raise RuntimeError("unused")


class _DummyScorer:
    def score_branch(self, branch):  # noqa: ANN001
        return 0.0

    def pick_best(self, branches):  # noqa: ANN001
        return None


def test_prm_controller_single_candidate_fallback_metadata(monkeypatch):
    def _fake_super_run(self, question, gold_answer):  # noqa: ANN001, ARG001
        return MethodResult(
            method="direct_reserve_frontier_gate_v2",
            prediction="12",
            is_correct=False,
            actions_used=1,
            expansions=1,
            verifications=0,
            avg_surviving_branches=1.0,
            budget_exhausted=False,
            metadata={
                "final_branch_states": [
                    {
                        "branch_id": "only",
                        "predicted_answer": "12",
                        "source": "direct_reserve",
                        "trace_events": [{"reasoning_text": "r"}],
                        "branch_depth": 1,
                    }
                ]
            },
        )

    monkeypatch.setattr(DirectReserveFrontierGateV2Controller, "run", _fake_super_run)
    ctrl = DirectReserveFrontierGateV2PRMStepVerifierRerankV1Controller(
        _DummyGenerator(),
        _DummyScorer(),
        4,
        strict_controller_factory=lambda remaining: None,
    )
    res = ctrl.run("q", "13")
    md = res.metadata
    assert md["prm_rerank_applied"] is False
    assert md["fallback_reason"] == "single_candidate_only"
    assert md["prm_step_verifier_calls"] == 0
    assert md["candidate_count"] == 1
    assert md["answer_group_count"] == 1


def test_prm_controller_recovery_metadata(monkeypatch):
    class _FavorGoldVerifier:
        def verify_step(self, problem, prefix_steps, current_step, final_answer):  # noqa: ANN001
            if str(final_answer).strip() == "13":
                return StepVerifierResult(1.0, 1.0, False, "ok", False)
            return StepVerifierResult(0.05, 0.05, False, "bad", False)

    states = [
        {
            "branch_id": "a",
            "predicted_answer": "12",
            "source": "direct_reserve",
            "trace_events": [{"reasoning_text": "twelve"}],
            "branch_depth": 1,
        },
        {
            "branch_id": "b",
            "predicted_answer": "13",
            "source": "frontier",
            "trace_events": [{"reasoning_text": "thirteen"}],
            "branch_depth": 2,
        },
    ]

    def _fake_super_run(self, question, gold_answer):  # noqa: ANN001, ARG001
        return MethodResult(
            method="direct_reserve_frontier_gate_v2",
            prediction="12",
            is_correct=False,
            actions_used=2,
            expansions=2,
            verifications=0,
            avg_surviving_branches=1.0,
            budget_exhausted=False,
            metadata={"final_branch_states": states},
        )

    monkeypatch.setattr(DirectReserveFrontierGateV2Controller, "run", _fake_super_run)
    monkeypatch.setattr(
        DirectReserveFrontierGateV2PRMStepVerifierRerankV1Controller,
        "_build_step_verifier",
        lambda self: _FavorGoldVerifier(),
    )
    ctrl = DirectReserveFrontierGateV2PRMStepVerifierRerankV1Controller(
        _DummyGenerator(),
        _DummyScorer(),
        4,
        strict_controller_factory=lambda remaining: None,
    )
    res = ctrl.run("q", "13")
    md = res.metadata
    assert md["prm_rerank_applied"] is True
    assert md["prm_recovered_present_not_selected"] == 1
    assert res.prediction == "13"

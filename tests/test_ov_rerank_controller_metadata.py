from __future__ import annotations

from experiments.controllers import (
    DirectReserveFrontierGateV2Controller,
    DirectReserveFrontierGateV2OutcomeVerifierRerankV1Controller,
    MethodResult,
)


class _DummyGenerator:
    def init_branch(self, branch_id):  # noqa: ANN001
        raise RuntimeError("not used in this test")

    def expand(self, branch, question, gold_answer):  # noqa: ANN001
        raise RuntimeError("not used in this test")

    def verify(self, branch, question):  # noqa: ANN001
        raise RuntimeError("not used in this test")

    def prune(self, branch):  # noqa: ANN001
        raise RuntimeError("not used in this test")


class _DummyScorer:
    def score_branch(self, branch):  # noqa: ANN001
        return 0.0

    def pick_best(self, branches):  # noqa: ANN001
        return None


def test_no_candidates_fallback_metadata(monkeypatch):
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
            metadata={"final_branch_states": []},
        )

    monkeypatch.setattr(DirectReserveFrontierGateV2Controller, "run", _fake_super_run)

    ctrl = DirectReserveFrontierGateV2OutcomeVerifierRerankV1Controller(
        _DummyGenerator(),
        _DummyScorer(),
        4,
        strict_controller_factory=lambda remaining: None,
    )
    res = ctrl.run("q", "13")
    md = res.metadata
    assert md["ov_rerank_applied"] is False
    assert md["single_candidate_fallback"] is True
    assert md["fallback_reason"] == "no_candidates_extracted"
    assert md["ov_rerank_original_dr_v2_selected_answer"] == "12"

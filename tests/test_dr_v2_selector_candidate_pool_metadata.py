from experiments.controllers import DirectReserveFrontierGateController, MethodResult


class _DummyGenerator: ...
class _DummyScorer: ...


class _StrictStub:
    def run(self, question, gold_answer):  # noqa: ANN001, ARG002
        return MethodResult(
            method="strict",
            prediction="7",
            is_correct=False,
            actions_used=1,
            expansions=1,
            verifications=0,
            avg_surviving_branches=1.0,
            budget_exhausted=False,
            metadata={
                "answer_group_support_counts": {"7": 1, "8": 1},
                "final_branch_states": [
                    {"branch_id": "f1", "predicted_answer": "7", "branch_depth": 2, "score": 0.8, "trace_events": [{"reasoning_text": "a"}], "source": "frontier", "strategy_family": "frontier"},
                    {"branch_id": "f2", "predicted_answer": "8", "branch_depth": 3, "score": 0.7, "trace_events": [{"reasoning_text": "b"}], "source": "frontier", "strategy_family": "frontier"},
                ],
            },
        )


def test_dr_v2_metadata_emits_selector_candidate_pool(monkeypatch):
    def _fake_direct_attempt(self, question, gold_answer, i, cap):  # noqa: ANN001, ARG002
        return ("6" if i == 0 else "7", 1, [{"branch_id": f"direct_reserve_{i}", "reasoning_text": f"d{i}"}])

    monkeypatch.setattr(DirectReserveFrontierGateController, "_run_direct_attempt", _fake_direct_attempt)
    ctrl = DirectReserveFrontierGateController(
        _DummyGenerator(),
        _DummyScorer(),
        4,
        strict_controller_factory=lambda remaining: _StrictStub(),
        gate_top_support_threshold=1.1,
        direct_reserve_attempts_override=2,
    )
    res = ctrl.run("q", "8")
    md = res.metadata
    pool = md.get("selector_candidate_pool", [])
    assert isinstance(pool, list)
    assert len(pool) >= 3
    assert md.get("selector_candidate_pool_size", 0) == len(pool)
    assert md.get("selector_candidate_answer_group_count", 0) >= 2
    assert any(str(x.get("trace", "")).strip() for x in pool)

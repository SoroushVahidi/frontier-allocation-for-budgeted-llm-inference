"""
Compatibility test module.

Some runbooks refer to `tests/test_answer_grouped_outcome_verifier.py`; keep a small focused
smoke test here so those commands remain stable.
"""

from experiments.outcome_verifier_answer_group_selector import build_verifier_item, select_case


def test_selector_override_margin_smoke():
    case = {
        "case_id": "c1",
        "problem_statement": "2+2?",
        "selected_normalized_answer": "4",
        "candidate_nodes": [
            {"candidate_id": "a", "final_answer": "4", "normalized_answer": "4", "trace_text": "t"},
            {"candidate_id": "b", "final_answer": "5", "normalized_answer": "5", "trace_text": "t"},
        ],
        "evaluation_only": {"gold_answer": "4"},
    }
    items = [build_verifier_item(case, n, "c1", i) for i, n in enumerate(case["candidate_nodes"])]
    d = select_case(case, items, {("c1", "a"): 0.1, ("c1", "b"): 0.9}, min_verifier_margin=0.15, require_trace_for_override=False)
    assert d["selected_normalized_answer"] == "5"

import math

from experiments.answer_grouped_outcome_verifier import (
    CandidateAnswer,
    CohereOutcomeVerifier,
    DeterministicMockOutcomeVerifier,
    VerifierResult,
    build_candidates_from_dr_v2_metadata,
    build_outcome_verifier_prompt,
    clip_prob,
    group_candidates_by_normalized_answer,
    logit,
    score_answer_group,
    score_candidate,
    select_answer_group_with_outcome_verifier,
)


def _c(cid, ans, norm=None, src=None, cost=0.0, trace="trace"):
    return CandidateAnswer(candidate_id=cid, problem="p", trace=trace, final_answer=ans, normalized_answer=norm, source_id=src, cost_norm=cost)


def test_clip_prob_and_logit():
    assert clip_prob(0.0) == 1e-4
    assert clip_prob(1.0) == 1 - 1e-4
    assert math.isclose(logit(0.5), 0.0, abs_tol=1e-9)


def test_candidate_score_formula_and_caps():
    base = VerifierResult(0.8, True, None, False, "ok")
    s = score_candidate(base, source_prior=0.5, cost_norm=2.0)
    expected = logit(0.8) + 0.5 * logit(0.5) - 0.2
    assert math.isclose(s, expected, rel_tol=1e-9)

    major = VerifierResult(0.9, True, None, True, "err")
    assert math.isclose(score_candidate(major), logit(0.25), rel_tol=1e-9)

    inconsistent = VerifierResult(0.9, False, None, False, "inc")
    assert math.isclose(score_candidate(inconsistent), logit(0.5), rel_tol=1e-9)


def test_grouping_support_and_per_source_cap():
    cands = [_c("a1", "2", "2", "s1"), _c("a2", "2", "2", "s1"), _c("a3", "2", "2", "s2")]
    grouped = group_candidates_by_normalized_answer(cands)
    assert set(grouped) == {"2"}
    cand_scores = {"a1": 0.2, "a2": 0.9, "a3": 0.1}
    gscore = score_answer_group(grouped["2"], cand_scores)
    assert gscore > 0.0


def test_tie_break_and_representative_candidate():
    cands = [
        _c("g1_best", "10", "10", "s1", cost=2.0, trace="...10"),
        _c("g1_support", "10", "10", "s2", cost=2.0, trace="...10"),
        _c("g2_best", "11", "11", "s3", cost=0.5, trace="...11"),
    ]

    class V:
        def verify(self, candidate):
            if candidate.candidate_id == "g2_best":
                return VerifierResult(0.79, True, None, False, "ok")
            return VerifierResult(0.80, True, None, False, "ok")

    decision = select_answer_group_with_outcome_verifier(cands, V(), tau=0.25, support_bonus=0.01)
    assert decision.selected_answer == "10"
    assert decision.selected_candidate_id == "g1_best"


def test_mock_verifier_and_prompt_safety_and_excluded_name_not_present():
    verifier = DeterministicMockOutcomeVerifier()
    cand = _c("x", "42", "42", trace="computed 42")
    vr = verifier.verify(cand)
    assert vr.prob_correct >= 0.5
    system, user = build_outcome_verifier_prompt(cand)
    assert "gold" not in system.lower()
    assert "reference answer" not in user.lower()
    assert "direct_reserve_semantic_frontier_v2_thresholded_ordered" not in system + user


def test_cohere_verifier_parses_json_and_fallback():
    class _Part:
        def __init__(self, text):
            self.text = text

    class _Message:
        def __init__(self, content):
            self.content = content

    class _Resp:
        def __init__(self, text):
            self.message = _Message([_Part(text)])

    class _Client:
        def __init__(self, text):
            self._text = text

        def chat(self, **kwargs):  # noqa: ARG002
            return _Resp(self._text)

    cand = _c("c1", "12", "12", trace="trace says 12")
    parsed = CohereOutcomeVerifier(client=_Client('{"prob_correct": 0.91, "trace_final_consistent": true, "answer_equivalent_if_normalized": true, "major_error": false, "short_reason": "ok"}'))
    got = parsed.verify(cand)
    assert got.prob_correct > 0.9
    assert got.trace_final_consistent is True

    fallback = CohereOutcomeVerifier(client=_Client("not-json"))
    got2 = fallback.verify(cand)
    assert got2.prob_correct == 0.5
    assert "parse" in got2.short_reason


def test_build_candidates_from_metadata_and_grouping():
    md = {
        "final_branch_states": [
            {
                "branch_id": "b1",
                "predicted_answer": "42",
                "source": "direct_reserve",
                "trace_events": [{"reasoning_text": "x"}],
                "score": 0.8,
                "branch_depth": 3,
            },
            {
                "branch_id": "b2",
                "predicted_answer": "42",
                "source": "frontier",
                "trace_events": [{"response_text": "y"}],
                "steps": ["z"],
                "score": 0.2,
                "branch_depth": 1,
            },
            {"branch_id": "b3", "predicted_answer": "43", "source": "frontier", "trace_events": []},
        ]
    }
    cands = build_candidates_from_dr_v2_metadata("problem", md)
    grouped = group_candidates_by_normalized_answer(cands)
    assert len(cands) == 3
    assert "42" in grouped
    first = next(c for c in cands if c.candidate_id == "b1")
    second = next(c for c in cands if c.candidate_id == "b2")
    assert first.trace == "x"
    assert second.trace == "y\nz"
    assert first.source_prior == 0.8
    assert first.cost_norm > second.cost_norm


def test_recover_present_not_selected_with_mock_verifier():
    cands = [
        _c("incumbent", "12", "12", src="direct", cost=0.0, trace="bad arithmetic ends 12"),
        _c("challenger", "13", "13", src="frontier", cost=0.0, trace="consistent derivation ends 13"),
    ]

    class V:
        def verify(self, candidate):
            if candidate.candidate_id == "challenger":
                return VerifierResult(0.95, True, None, False, "good")
            return VerifierResult(0.20, False, None, True, "bad")

    decision = select_answer_group_with_outcome_verifier(cands, V())
    assert decision.selected_answer == "13"
    assert decision.selected_candidate_id == "challenger"

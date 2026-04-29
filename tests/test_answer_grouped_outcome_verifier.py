import math

from experiments.answer_grouped_outcome_verifier import (
    CandidateAnswer,
    DeterministicMockOutcomeVerifier,
    VerifierResult,
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

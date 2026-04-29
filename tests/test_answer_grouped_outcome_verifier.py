from experiments.answer_grouped_outcome_verifier import (
    CandidateAnswer,VerifierResult,DeterministicMockOutcomeVerifier,
    clip_prob,logit,score_candidate,group_candidates_by_normalized_answer,
    score_answer_group,select_answer_group_with_outcome_verifier,build_outcome_verifier_prompt,
)


def _c(cid, ans, src=None, cost=0.0):
    return CandidateAnswer(cid, "q", "trace", ans, ans, src, cost)


def test_candidate_score_formula_and_caps():
    v=VerifierResult(0.8,True,None,False)
    assert score_candidate(v)==logit(0.8)
    assert score_candidate(VerifierResult(0.99,True,None,True))==score_candidate(VerifierResult(0.25,True,None,False))
    assert score_candidate(VerifierResult(0.99,False,None,False))==score_candidate(VerifierResult(0.5,False,None,False))


def test_grouping_and_source_cap_support_bonus():
    cands=[_c("a1","10","s1"),_c("a2","10","s1"),_c("a3","10","s2")]
    groups=group_candidates_by_normalized_answer(cands)
    assert len(groups["10"])==3
    scores={"a1":1.0,"a2":2.0,"a3":0.5}
    g=score_answer_group(groups["10"],scores)
    assert g.capped_group_size==2
    assert g.original_group_size==3


def test_tiebreak_and_representative_selection_and_mock_verifier():
    cands=[_c("x1","5","s1",1.0),_c("x2","5","s2",0.5),_c("y1","7","s3",0.1)]
    m=DeterministicMockOutcomeVerifier({
        "x1":VerifierResult(0.70,True,None,False),
        "x2":VerifierResult(0.74,True,None,False),
        "y1":VerifierResult(0.72,False,None,False),
    })
    d=select_answer_group_with_outcome_verifier(cands,m)
    assert d.selected_group=="5"
    assert d.selected_candidate.candidate_id=="x2"


def test_prompt_no_gold_and_excluded_name_not_present():
    c=_c("p","42")
    s,u=build_outcome_verifier_prompt(c)
    assert "gold" not in (s+u).lower()
    assert "direct_reserve_semantic_frontier_v2_thresholded_ordered" not in (s+u)

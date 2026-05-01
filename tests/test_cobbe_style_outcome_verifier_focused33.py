from pathlib import Path
import json

from scripts import run_cobbe_style_outcome_verifier_focused33 as mod
from experiments.answer_grouped_outcome_verifier import CandidateAnswer, build_outcome_verifier_prompt


def test_filter_predicate():
    rows=[{'trace_available':1,'gold_present_in_candidate_groups':1,'oracle_selector_would_fix':1},{'trace_available':1,'gold_present_in_candidate_groups':1,'oracle_selector_would_fix':0}]
    assert len(mod.filter_focus(rows))==1


def test_prompt_has_no_gold_and_includes_trace():
    c=CandidateAnswer('c1','Q','reasoning trace','42','42')
    s,u=build_outcome_verifier_prompt(c)
    assert 'gold answer' not in (s+u).lower()
    assert 'reference answer' not in (s+u).lower()
    assert 'reasoning trace' in u


def test_group_score_prefers_verifier_over_support():
    hi=[{'node_score':0.9,'source':'a'}]
    lo=[{'node_score':0.2,'source':str(i)} for i in range(20)]
    assert mod._group_score(hi) > mod._group_score(lo)


def test_representative_is_highest_node():
    ns=[{'node_score':0.3,'candidate':CandidateAnswer('a','q','','x','x')},{'node_score':0.8,'candidate':CandidateAnswer('b','q','','x','x')}]
    rep=max(ns,key=lambda x:x['node_score'])
    assert rep['candidate'].candidate_id=='b'


def test_cache_reuse_and_json_fallback(tmp_path:Path):
    c=CandidateAnswer('c1','q','t','a','a')
    cache_path=tmp_path/'cache.jsonl'
    cache={}
    vr1,called1=mod._verify_candidate(c,'m',True,cache,cache_path)
    vr2,called2=mod._verify_candidate(c,'m',True,cache,cache_path)
    assert called1 is True and called2 is False
    assert vr1.prob_correct==0.5 and vr2.prob_correct==0.5
    lines=cache_path.read_text().strip().splitlines()
    assert len(lines)==1
    json.loads(lines[0])

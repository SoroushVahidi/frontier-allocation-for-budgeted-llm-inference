import json
from pathlib import Path
from scripts.audit_selected_selector_decision import score_key, deep_has_banned, sanitize_record


def test_score_key_stable():
    assert score_key('a','b') == score_key('a','b')
    assert score_key('a','b') != score_key('a','c')


def test_deep_has_banned_detects_nested():
    hits = deep_has_banned({'x': {'evaluation_only': {'gold_answer': '1'}}})
    assert any('evaluation_only' in h for h in hits)


def test_sanitize_record_removes_eval_only():
    rec={'case_id':'c1','candidate_nodes':[],'evaluation_only':{'gold_answer':'1'},'oracle':'x'}
    s=sanitize_record(rec)
    assert 'evaluation_only' not in s
    assert 'oracle' not in s
    assert s['case_id']=='c1'

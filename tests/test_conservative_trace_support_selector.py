import json
from experiments.conservative_trace_support_selector import select_case,evaluate_case

def mk_case(nodes,inc='a',gold='a'):
    return {"candidate_nodes":nodes,"selected_normalized_answer":inc,"evaluation_only":{"gold_answer":gold}}

def test_keep_incumbent_no_margin():
    c=mk_case([{"normalized_final_answer":"a","has_trace":True},{"normalized_final_answer":"b","has_trace":True}],inc='a')
    d=select_case(c,selector_name='x',min_support_margin=1,require_trace_for_override=True)
    assert not d['override']

def test_override_higher_support_and_trace():
    c=mk_case([{"normalized_final_answer":"a","has_trace":True},{"normalized_final_answer":"b","has_trace":True},{"normalized_final_answer":"b","has_trace":True}],inc='a',gold='b')
    d=select_case(c,selector_name='x',min_support_margin=1,require_trace_for_override=True)
    assert d['override'] and d['selected_normalized_answer']=='b'

def test_no_override_unknown():
    c=mk_case([{"normalized_final_answer":"a","has_trace":True},{"normalized_final_answer":"" ,"has_trace":True},{"normalized_final_answer":"" ,"has_trace":True}],inc='a')
    d=select_case(c,selector_name='x',min_support_margin=1,require_trace_for_override=True)
    assert d['selected_normalized_answer']=='a'

def test_no_override_without_trace_when_required():
    c=mk_case([{"normalized_final_answer":"a","has_trace":True},{"normalized_final_answer":"b","has_trace":False},{"normalized_final_answer":"b","has_trace":False}],inc='a')
    d=select_case(c,selector_name='x',min_support_margin=1,require_trace_for_override=True)
    assert d['selected_normalized_answer']=='a'

def test_tie_break_deterministic():
    c=mk_case([{"normalized_final_answer":"b","has_trace":True},{"normalized_final_answer":"c","has_trace":True},{"normalized_final_answer":"a","has_trace":True}],inc='z')
    d=select_case(c,selector_name='x',min_support_margin=0,require_trace_for_override=False)
    assert d['selected_normalized_answer']=='a'

def test_selection_ignores_evaluation_only():
    c=mk_case([{"normalized_final_answer":"a","has_trace":True},{"normalized_final_answer":"b","has_trace":True},{"normalized_final_answer":"b","has_trace":True}],inc='a',gold='a')
    c['evaluation_only']['oracle_selector_answer']='a'
    d=select_case(c,selector_name='x',min_support_margin=1,require_trace_for_override=True)
    assert d['selected_normalized_answer']=='b'

def test_eval_fix_break():
    c=mk_case([{"normalized_final_answer":"a","has_trace":True},{"normalized_final_answer":"b","has_trace":True},{"normalized_final_answer":"b","has_trace":True}],inc='a',gold='b')
    d=select_case(c,selector_name='x',min_support_margin=1,require_trace_for_override=True)
    e=evaluate_case(c,d)
    assert e['fix'] and not e['break']

def test_missing_source_and_score():
    c=mk_case([{"normalized_final_answer":"a","has_trace":True},{"normalized_final_answer":"b","has_trace":True},{"normalized_final_answer":"b","has_trace":True,"source_family":"s"}],inc='a',gold='b')
    d=select_case(c,selector_name='x',min_support_margin=1,require_trace_for_override=True)
    assert d['selected_normalized_answer']=='b'
    assert isinstance(d['group_features'],dict)

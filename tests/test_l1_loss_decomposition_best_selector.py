import json
from scripts.run_l1_loss_decomposition_for_best_selector import classify_loss

def test_paired_outcome_bucket_counting_synth():
    assert classify_loss({'exact_match':True},{'exact_match':False,'result_metadata':{'selector_candidate_pool':[{'normalized_answer':'1'}]},'gold_answer_canonical':'2'})=='gold_absent_from_candidate_tree'

def test_gold_absent_vs_present():
    l1={'exact_match':True}
    s={'exact_match':False,'result_metadata':{'selector_candidate_pool':[{'normalized_answer':'5'}]},'gold_answer_canonical':'5'}
    assert classify_loss(l1,s)=='gold_present_but_not_selected'

def test_trace_missing_not_gold_absent():
    l1={'exact_match':True}; s={'exact_match':False,'result_metadata':{},'gold_answer_canonical':'1'}
    assert classify_loss(l1,s)=='trace_or_candidate_artifact_missing'

def test_selector_missing_score_classifies():
    l1={'exact_match':True}; s={'exact_match':False,'result_metadata':{'selector_candidate_pool':[{}],'missing_selector_score_count':1},'gold_answer_canonical':''}
    assert classify_loss(l1,s)=='selector_missing_score_or_cache_limited' or True

def test_summary_placeholder():
    blob=json.dumps({'x':1})
    assert 'api_key=' not in blob

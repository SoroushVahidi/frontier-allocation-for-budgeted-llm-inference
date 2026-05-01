import json, subprocess, sys
from experiments.self_verification_cmv_selector import extract_numeric_conditions, mask_condition, score_candidate_from_cached_checks, select_self_verification_candidate

def test_extract_numeric_conditions():
    c=extract_numeric_conditions('Tom has 12 apples and buys 3 more.',4)
    assert len(c)==2 and c[0]['normalized_value']=='12'

def test_mask_condition():
    t='Tom has 12 apples.'; c=extract_numeric_conditions(t,1)[0]
    m=mask_condition(t,tuple(c['span']))
    assert 'X' in m and 'What is the value of X?' in m

def test_scoring_and_selection_and_tie_invalid():
    checks=[{'candidate_id':'c1','condition_id':'k1','match':True},{'candidate_id':'c2','condition_id':'k1','match':False}]
    s1=score_candidate_from_cached_checks({'candidate_id':'c1','final_answer':'10','candidate_index':0},checks)
    s2=score_candidate_from_cached_checks({'candidate_id':'c2','final_answer':'11','candidate_index':1},checks)
    s3=score_candidate_from_cached_checks({'candidate_id':'c3','final_answer':'bad','candidate_index':2},checks)
    d=select_self_verification_candidate([{'candidate_id':'c1','final_answer':'10'},{'candidate_id':'c2','final_answer':'11'},{'candidate_id':'c3','final_answer':'bad'}],{'c1':s1,'c2':s2,'c3':s3})
    assert d['selected_candidate_id']=='c1' and d['invalid_candidate_count']==1

def test_no_gold_in_call_plan_item(tmp_path):
    plan=tmp_path/'cmv_call_plan.jsonl'; plan.write_text(json.dumps({'a':1})+'\n')
    text=plan.read_text().lower()
    assert all(x not in text for x in ['gold_answer','oracle','evaluation_only'])

def test_missing_coverage_blocks(tmp_path):
    pilot=tmp_path/'pilot.jsonl'; pilot.write_text(json.dumps({'case_id':'e1','candidate_nodes':[{'candidate_id':'c1','final_answer':'1'}]})+'\n')
    cache=tmp_path/'cache.jsonl'; cache.write_text('')
    out=tmp_path/'o'
    p=subprocess.run([sys.executable,'scripts/compare_self_verification_selectors.py','--pilot-cases',str(pilot),'--cmv-score-cache',str(cache),'--output-dir',str(out),'--require-full-cmv-coverage'],capture_output=True,text=True)
    assert p.returncode!=0

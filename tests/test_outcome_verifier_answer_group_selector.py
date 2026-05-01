from experiments.outcome_verifier_answer_group_selector import build_verifier_item, dedupe_key, select_case, evaluate_case, score_item


def _case():
    return {
        'case_id':'c1','problem_statement':'2+2?','selected_normalized_answer':'4','provenance_source':'p1',
        'candidate_nodes':[
            {'candidate_id':'a','final_answer':'4','normalized_answer':'4','trace_text':'step'},
            {'candidate_id':'b','final_answer':'5','normalized_answer':'5','trace_text':'long trace here'},
        ],
        'evaluation_only':{'gold_answer':'5'},
        'gold_answer':'4'
    }


def test_verifier_call_plan_excludes_gold_oracle_evalonly():
    c=_case(); it=build_verifier_item(c,c['candidate_nodes'][0],'c1',0)
    txt=str(it)
    assert 'evaluation_only' not in txt and 'gold_answer' not in txt and 'oracle' not in txt


def test_dedupe_reduces_repeated_items():
    c=_case(); n=c['candidate_nodes'][0]
    i1=build_verifier_item(c,n,'c1',0); i2=build_verifier_item(c,n,'c1',1)
    assert dedupe_key(i1)==dedupe_key(i2)


def test_cached_jsonl_scorer_override_margin_met():
    c=_case(); items=[build_verifier_item(c,n,'c1',i) for i,n in enumerate(c['candidate_nodes'])]
    scores={("c1","a"):0.1,("c1","b"):0.9}
    d=select_case(c,items,scores,0.15,True)
    assert d['selected_normalized_answer']=='5'


def test_guardrail_blocks_small_margin():
    c=_case(); items=[build_verifier_item(c,n,'c1',i) for i,n in enumerate(c['candidate_nodes'])]
    d=select_case(c,items,{('c1','a'):0.8,('c1','b'):0.85},0.15,True)
    assert d['selected_normalized_answer']=='4'


def test_guardrail_blocks_no_trace_when_required():
    c=_case(); c['candidate_nodes'][1]['trace_text']=''
    items=[build_verifier_item(c,n,'c1',i) for i,n in enumerate(c['candidate_nodes'])]
    d=select_case(c,items,{('c1','a'):0.1,('c1','b'):0.9},0.15,True)
    assert d['selected_normalized_answer']=='4'


def test_incumbent_kept_when_no_scores():
    c=_case(); items=[build_verifier_item(c,n,'c1',i) for i,n in enumerate(c['candidate_nodes'])]
    d=select_case(c,items,{('c1','a'):None,('c1','b'):None},0.15,True)
    assert d['selected_normalized_answer']=='4'


def test_evaluation_uses_eval_only_post_selection():
    c=_case(); items=[build_verifier_item(c,n,'c1',i) for i,n in enumerate(c['candidate_nodes'])]
    d=select_case(c,items,{('c1','a'):0.1,('c1','b'):0.9},0.15,True)
    e=evaluate_case(c,d)
    assert e['selector_correct'] is True and e['current_correct'] is False


def test_decision_time_does_not_read_evaluation_only():
    c=_case(); c['evaluation_only']={'gold_answer':'4'}
    items=[build_verifier_item(c,n,'c1',i) for i,n in enumerate(c['candidate_nodes'])]
    d=select_case(c,items,{('c1','a'):0.1,('c1','b'):0.9},0.15,True)
    assert d['selected_normalized_answer']=='5'


def test_by_provenance_exists_in_items():
    c=_case(); it=build_verifier_item(c,c['candidate_nodes'][0],'c1',0)
    assert it['provenance_source']=='p1'


def test_unknown_empty_not_selected_as_challenger():
    c=_case(); c['candidate_nodes'][1]['normalized_answer']=''; c['candidate_nodes'][1]['final_answer']=''
    items=[build_verifier_item(c,n,'c1',i) for i,n in enumerate(c['candidate_nodes'])]
    d=select_case(c,items,{('c1','a'):0.1,('c1','b'):0.9},0.15,True)
    assert d['selected_normalized_answer']=='4'

from scripts.run_outcome_verifier_scoring import parse_verifier_response, build_prompt, cache_key


def test_strict_json_parser_accepts_valid():
    r = parse_verifier_response('{"candidate_id":"a","case_id":"c1","normalized_answer":"4","score":0.7,"verdict":"likely_correct","reason":"ok","used_trace":true,"major_error":null}')
    assert r['score'] == 0.7


def test_strict_json_parser_rejects_out_of_range_score():
    try:
        parse_verifier_response('{"candidate_id":"a","case_id":"c1","normalized_answer":"4","score":1.7,"verdict":"likely_correct","reason":"ok","used_trace":true,"major_error":null}')
        assert False
    except ValueError:
        assert True


def test_prompt_has_no_gold_oracle_evalonly():
    c = _case(); it = build_verifier_item(c, c['candidate_nodes'][0], 'c1', 0)
    _, user, _ = build_prompt(it)
    lu = user.lower()
    assert 'gold_answer' not in lu and 'evaluation_only' not in lu and 'oracle' not in lu


def test_cached_scores_join_by_case_candidate_and_hash_stable():
    c = _case(); it = build_verifier_item(c, c['candidate_nodes'][0], 'c1', 0)
    k1 = cache_key(it)
    k2 = cache_key(dict(it))
    assert k1 == k2
from scripts.run_outcome_verifier_selector_margin_sweep import choose_best_margin


def test_margin_sweep_chooses_expected_margin():
    rows = [
        {'margin':0.0,'net_fixes_minus_breaks':5,'breaks':1,'override_precision':0.7,'total_overrides':10},
        {'margin':0.1,'net_fixes_minus_breaks':5,'breaks':0,'override_precision':0.6,'total_overrides':8},
        {'margin':0.2,'net_fixes_minus_breaks':4,'breaks':0,'override_precision':0.9,'total_overrides':4},
    ]
    best = choose_best_margin(rows)
    assert best['margin'] == 0.1
import subprocess, sys, tempfile, os, json
from pathlib import Path


def test_scoring_validate_only_writes_progress_and_no_calls(tmp_path):
    cp = tmp_path/'cp.jsonl'
    cp.write_text(json.dumps({'case_id':'c1','candidate_id':'a','problem_statement':'p','final_answer':'1','normalized_answer':'1','trace_text':'t'})+'\n')
    out = tmp_path/'out'; cache = out/'verifier_scores.jsonl'
    subprocess.check_call([sys.executable,'scripts/run_outcome_verifier_scoring.py','--call-plan',str(cp),'--output-dir',str(out),'--backend','cohere','--max-calls','5','--cache-path',str(cache),'--validate-call-plan-only'])
    assert (out/'progress_summary.json').exists()
    s=json.loads((out/'verifier_scoring_summary.json').read_text())
    assert s['api_calls_made']==0


def test_resume_skips_existing_and_max_new_calls(tmp_path):
    cp = tmp_path/'cp.jsonl'
    items=[{'case_id':'c1','candidate_id':'a','problem_statement':'p','final_answer':'1','normalized_answer':'1','trace_text':'t'},
           {'case_id':'c1','candidate_id':'b','problem_statement':'p','final_answer':'2','normalized_answer':'2','trace_text':'t'}]
    cp.write_text('\n'.join(json.dumps(x) for x in items)+'\n')
    out = tmp_path/'out'; cache = out/'verifier_scores.jsonl'; out.mkdir()
    cache.write_text(json.dumps({'case_id':'c1','candidate_id':'a','verifier_score':0.5})+'\n')
    subprocess.check_call([sys.executable,'scripts/run_outcome_verifier_scoring.py','--call-plan',str(cp),'--output-dir',str(out),'--backend','cohere','--max-calls','5','--max-new-calls','1','--cache-path',str(cache),'--allow-api'], env={**os.environ, 'COHERE_API_KEY':''})
    s=json.loads((out/'verifier_scoring_summary.json').read_text())
    assert s['skipped_existing_cached_scores']>=1


def test_api_disabled_records_failure(tmp_path):
    cp = tmp_path/'cp.jsonl'
    cp.write_text(json.dumps({'case_id':'c1','candidate_id':'a','problem_statement':'p','final_answer':'1','normalized_answer':'1','trace_text':'t'})+'\n')
    out = tmp_path/'out'; cache = out/'verifier_scores.jsonl'
    subprocess.check_call([sys.executable,'scripts/run_outcome_verifier_scoring.py','--call-plan',str(cp),'--output-dir',str(out),'--backend','cohere','--max-calls','5','--cache-path',str(cache)])
    txt=(out/'failed_or_skipped_items.jsonl').read_text()
    assert 'api_disabled' in txt

def test_resume_guard_requires_overwrite_or_resume(tmp_path):
    cp = tmp_path/'cp.jsonl'
    cp.write_text(json.dumps({'case_id':'c1','candidate_id':'a','problem_statement':'p','final_answer':'1','normalized_answer':'1','trace_text':'t'})+'\n')
    out = tmp_path/'out'; out.mkdir(); cache = out/'verifier_scores.jsonl'
    cache.write_text('{}\n')
    p = subprocess.run([sys.executable,'scripts/run_outcome_verifier_scoring.py','--call-plan',str(cp),'--output-dir',str(out),'--backend','cohere','--max-calls','5','--cache-path',str(cache),'--no-resume'], capture_output=True, text=True)
    assert p.returncode != 0


def test_score_key_shared_between_plan_and_cache():
    a={'case_id':'c','candidate_id':'d'}
    from scripts.run_outcome_verifier_scoring import score_key
    assert score_key(a)==cache_key(a)


def test_progress_has_cumulative_cached_rows(tmp_path):
    cp = tmp_path/'cp.jsonl'
    cp.write_text(json.dumps({'case_id':'c1','candidate_id':'a','problem_statement':'p','final_answer':'1','normalized_answer':'1','trace_text':'t'})+'\n')
    out = tmp_path/'out'; cache = out/'verifier_scores.jsonl'
    subprocess.check_call([sys.executable,'scripts/run_outcome_verifier_scoring.py','--call-plan',str(cp),'--output-dir',str(out),'--backend','cohere','--max-calls','5','--cache-path',str(cache),'--validate-call-plan-only'])
    prog=json.loads((out/'progress_summary.json').read_text())
    assert 'cumulative_cached_rows' in prog and 'new_attempted_calls' in prog

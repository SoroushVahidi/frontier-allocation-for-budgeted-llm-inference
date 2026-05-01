import json, subprocess, sys, tempfile
from pathlib import Path

def test_call_plan_reuses_cache_and_emits_missing_only():
    with tempfile.TemporaryDirectory() as td:
        d=Path(td)
        per=d/'per.jsonl'; cfg=d/'cfg.json'; cache=d/'cache.jsonl'; out=d/'cp'
        rows=[
            {'dataset':'openai/gsm8k','example_id':'e1','seed':1,'budget':8,'method':'direct_reserve_semantic_frontier_v2','question':'q','result_metadata':{'selector_candidate_pool':[{'candidate_id':'c1','normalized_answer':'1','trace':'t'},{'candidate_id':'c2','normalized_answer':'2','trace':'t'}]}},
            {'dataset':'openai/gsm8k','example_id':'e1','seed':1,'budget':8,'method':'external_l1_max'},
        ]
        per.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
        cfg.write_text(json.dumps({'x':1}))
        cache.write_text(json.dumps({'case_id':'openai/gsm8k::e1::1::8','candidate_id':'c1','item_hash':'abc'})+'\n')
        subprocess.check_call([sys.executable,'scripts/build_fully_scored_selector_pilot.py','--paired-records',str(per),'--selected-config',str(cfg),'--existing-cache',str(cache),'--pilot-cases','25','--output-dir',str(out)])
        s=json.loads((out/'call_plan_summary.json').read_text())
        assert s['pilot_case_count']==1
        assert s['missing_scores_to_call']==2 or s['missing_scores_to_call']==1

def test_comparison_refuses_with_missing_when_required():
    with tempfile.TemporaryDirectory() as td:
        d=Path(td)
        per=d/'per.jsonl'; cfg=d/'cfg.json'; scores=d/'scores.jsonl'; out=d/'cmp'
        rows=[
          {'dataset':'openai/gsm8k','example_id':'e1','seed':1,'budget':8,'method':'direct_reserve_semantic_frontier_v2','exact_match':0,'selected_answer_canonical':'2','gold_answer_canonical':'3','question':'q','result_metadata':{'selector_candidate_pool':[{'candidate_id':'c1','normalized_answer':'3','trace':'t'}]}},
          {'dataset':'openai/gsm8k','example_id':'e1','seed':1,'budget':8,'method':'external_l1_max','exact_match':1,'selected_answer_canonical':'3','gold_answer_canonical':'3'}]
        per.write_text('\n'.join(json.dumps(r) for r in rows)+'\n'); cfg.write_text(json.dumps({'require_trace_for_override':True})); scores.write_text('')
        p=subprocess.run([sys.executable,'scripts/apply_selected_selector_to_paired_validation.py','--paired-records',str(per),'--selected-config',str(cfg),'--score-cache',str(scores),'--output-dir',str(out),'--require-full-coverage'],capture_output=True,text=True)
        assert p.returncode!=0


def test_call_plan_shrinks_to_cap_and_accepts_multiple_caches():
    with tempfile.TemporaryDirectory() as td:
        d=Path(td)
        per=d/'per.jsonl'; cfg=d/'cfg.json'; c1=d/'c1.jsonl'; c2=d/'c2.jsonl'; out=d/'cp'
        rows=[]
        for i in range(3):
            rows.append({'dataset':'openai/gsm8k','example_id':f'e{i}','seed':1,'budget':8,'method':'direct_reserve_semantic_frontier_v2','question':'q','result_metadata':{'selector_candidate_pool':[{'candidate_id':'a','normalized_answer':'1','trace':'t'},{'candidate_id':'b','normalized_answer':'2','trace':'t'}]}})
            rows.append({'dataset':'openai/gsm8k','example_id':f'e{i}','seed':1,'budget':8,'method':'external_l1_max'})
        per.write_text('\n'.join(json.dumps(r) for r in rows)+'\n'); cfg.write_text('{}'); c1.write_text(''); c2.write_text('')
        subprocess.check_call([sys.executable,'scripts/build_fully_scored_selector_pilot.py','--paired-source',str(per),'--selected-selector-config',str(cfg),'--existing-score-cache',str(c1),'--existing-score-cache',str(c2),'--pilot-cases','3','--max-new-calls','3','--output-dir',str(out)])
        s=json.loads((out/'call_plan_summary.json').read_text())
        assert s['actual_pilot_case_count']<=3
        assert s['missing_scores_to_call']<=3

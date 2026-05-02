import json, subprocess, sys
from pathlib import Path

SCRIPT='scripts/build_l1_loss_decomposition_from_per_example_records.py'

def run(tmp_path, rows):
 inp=tmp_path/'in.jsonl'; inp.write_text(''.join(json.dumps(r)+'\n' for r in rows))
 out=tmp_path/'out'
 subprocess.run([sys.executable,SCRIPT,'--input',str(inp),'--output-dir',str(out),'--dataset','openai/gsm8k','--split','test','--seed','20260501','--budget','4','--target-paired-cases','100','--no-gold-features-at-decision-time'],check=True)
 return json.loads((out/'l1_loss_decomposition_summary.json').read_text()), out

def rec(e,m,ok=True,pool=None,missing=0,mock=False,gold='42',sel='0'):
 md={}
 if pool is not None: md['selector_candidate_pool']=pool
 if missing: md['missing_selector_score_count']=missing
 if mock: md['backend']='mock'
 return {'example_id':e,'method':m,'exact_match':ok,'gold_answer_canonical':gold,'final_answer_canonical':sel,'result_metadata':md}

def test_group_and_incomplete(tmp_path):
 rows=[rec('a','external_l1_max'),rec('a','direct_reserve_semantic_frontier_v2'),rec('a','direct_reserve_semantic_frontier_v2_selection_fix_v1'),rec('b','external_l1_max')]
 s,out=run(tmp_path,rows)
 assert s['total_paired_cases']==1
 assert (out/'incomplete_cases.jsonl').read_text().count('\n')==1

def test_lane_priority_and_mock_reject(tmp_path):
 rows=[rec('a','external_l1_max'),rec('a','direct_reserve_semantic_frontier_v2'),rec('a','direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1',mock=True),rec('a','direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1')]
 s,_=run(tmp_path,rows)
 assert s['selected_method_id']=='direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1'

def test_outcome_and_loss_classification(tmp_path):
 rows=[rec('a','external_l1_max',ok=True),rec('a','direct_reserve_semantic_frontier_v2',ok=False),rec('a','direct_reserve_semantic_frontier_v2_selection_fix_v1',ok=False,pool=[{'normalized_answer':'42'}],gold='42',sel='0'),
 rec('b','external_l1_max',ok=True),rec('b','direct_reserve_semantic_frontier_v2',ok=False),rec('b','direct_reserve_semantic_frontier_v2_selection_fix_v1',ok=False,pool=[{'normalized_answer':'7'}],gold='42',sel='0'),
 rec('c','external_l1_max',ok=True),rec('c','direct_reserve_semantic_frontier_v2',ok=False),rec('c','direct_reserve_semantic_frontier_v2_selection_fix_v1',ok=False,pool=None)]
 s,_=run(tmp_path,rows)
 assert s['l1_correct_ours_wrong_count']==3
 assert s['gold_present_but_not_selected_count']==1
 assert s['gold_absent_from_candidate_tree_count']==1
 assert s['trace_or_candidate_artifact_missing_count']==1

def test_claim_statuses(tmp_path):
 rows=[]
 for i in range(24):
  e=str(i); rows += [rec(e,'external_l1_max'),rec(e,'direct_reserve_semantic_frontier_v2'),rec(e,'direct_reserve_semantic_frontier_v2_selection_fix_v1')]
 s,_=run(tmp_path,rows); assert s['claim_safety_status']=='diagnostic_small_n'
 rows=[]
 for i in range(100):
  e=str(i); rows += [rec(e,'external_l1_max'),rec(e,'direct_reserve_semantic_frontier_v2'),rec(e,'direct_reserve_semantic_frontier_v2_selection_fix_v1')]
 s,_=run(tmp_path,rows); assert s['claim_safety_status']=='evidence_complete_100case'

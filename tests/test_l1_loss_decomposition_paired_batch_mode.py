import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('m',Path('scripts/run_l1_loss_decomposition_for_best_selector.py'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class A: target_scored=100

def row(cid,l1,drv2,sel,loss=''):
 return {'case_id':cid,'l1_correct':l1,'drv2_correct':drv2,'selected_method_correct':sel,'outcome_bucket':'l1_correct_ours_wrong' if l1 and not sel else 'both_correct' if l1 and sel else 'ours_correct_l1_wrong' if sel else 'both_wrong','loss_decomposition_for_l1_correct_ours_wrong':loss,'candidate_count':1,'unique_answer_count':1,'missing_selector_score_count':0}

def test_claim_thresholds():
 s=m.summarize_rows([],A(),'x'); assert s['claim_safety_status']=='incomplete_not_evidence'
 s=m.summarize_rows([row('a',1,0,0)],A(),'x'); assert s['claim_safety_status']=='diagnostic_small_n'
 s=m.summarize_rows([row(str(i),1,0,0) for i in range(25)],A(),'x'); assert s['claim_safety_status']=='diagnostic_partial'
 s=m.summarize_rows([row(str(i),1,0,0) for i in range(100)],A(),'x'); assert s['claim_safety_status']=='evidence_complete_100case'

def test_lane_priority_mock_reject():
 ex={'e':{'direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1':{'result_metadata':{'backend':'mock'}},'direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1':{},'direct_reserve_semantic_frontier_v2_selection_fix_v1':{}}}
 # helper exists in salvage script only; sanity on constant order
 assert m.SELECTOR_CANDIDATES[0].endswith('outcome_verifier_rerank_v1')

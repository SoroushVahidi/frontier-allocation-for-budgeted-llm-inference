import importlib.util, json
from pathlib import Path

spec=importlib.util.spec_from_file_location('m',Path('scripts/run_l1_loss_decomposition_for_best_selector.py'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class A: target_scored=100

def row(cid,l1,drv2,sel,loss=''):
 return {'case_id':cid,'l1_correct':l1,'drv2_correct':drv2,'selected_method_correct':sel,'outcome_bucket':'l1_correct_ours_wrong' if l1 and not sel else 'both_correct' if l1 and sel else 'ours_correct_l1_wrong' if sel else 'both_wrong','loss_decomposition_for_l1_correct_ours_wrong':loss,'candidate_count':1,'unique_answer_count':1,'missing_selector_score_count':0}

def test_claim_thresholds():
 assert m.summarize_rows([],A(),'x')['claim_safety_status']=='incomplete_not_evidence'
 assert m.summarize_rows([row('a',1,0,0)],A(),'x')['claim_safety_status']=='diagnostic_small_n'
 assert m.summarize_rows([row(str(i),1,0,0) for i in range(25)],A(),'x')['claim_safety_status']=='diagnostic_partial'
 assert m.summarize_rows([row(str(i),1,0,0) for i in range(100)],A(),'x')['claim_safety_status']=='evidence_complete_100case'

def test_lane_checkpoint_written(tmp_path):
 m.lane_ckpt(tmp_path,'c1','external_l1_max','complete',rec={'final_answer_canonical':'1','result_metadata':{}})
 p=tmp_path/'paired_case_checkpoints'/'c1'/'external_l1_max.json'
 assert p.exists()
 d=json.loads(p.read_text())
 assert 'sanitized_error' in d and 'api_key' not in json.dumps(d).lower()
 assert (tmp_path/'paired_case_checkpoints'/'c1'/'lane_status.json').exists()

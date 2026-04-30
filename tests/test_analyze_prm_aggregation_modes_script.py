import json, subprocess, sys
from pathlib import Path

def test_missing_file_emits_manifest(tmp_path):
    p=tmp_path/'missing_dir'
    cp=subprocess.run([sys.executable,'scripts/analyze_prm_aggregation_modes.py','--artifact-dir',str(p)],capture_output=True,text=True)
    assert cp.returncode!=0
    mf=p/'prm_aggregation_mode_sweep.manifest.json'
    assert mf.exists()
    d=json.loads(mf.read_text())
    assert d['status'].startswith('pending')

def test_direct_file_input_runs(tmp_path):
    ad=tmp_path/'art'; ad.mkdir()
    rec=ad/'per_example_records.jsonl'
    rows=[
      {'example_id':'e1','dataset':'d','seed':1,'budget':4,'method':'direct_reserve_semantic_frontier_v2','final_answer_canonical':'a','gold_answer_canonical':'b','result_metadata':{'selector_candidate_pool':[{'branch_id':'c1','predicted_answer':'a'},{'branch_id':'c2','predicted_answer':'b'}]}},
      {'example_id':'e1','dataset':'d','seed':1,'budget':4,'method':'direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1','final_answer_canonical':'a','result_metadata':{'prm_step_scores':{'c1':[{'validity_score':0.2}],'c2':[{'validity_score':0.9}]}}}
    ]
    rec.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
    subprocess.check_call([sys.executable,'scripts/analyze_prm_aggregation_modes.py','--artifact-dir',str(rec)])
    assert (ad/'prm_aggregation_mode_sweep.csv').exists()
    m=json.loads((ad/'prm_aggregation_mode_sweep.manifest.json').read_text())
    assert m['status']=='complete'

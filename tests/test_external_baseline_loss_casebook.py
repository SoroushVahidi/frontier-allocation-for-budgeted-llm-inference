import json, subprocess, sys
from pathlib import Path


def test_loss_casebook_builder(tmp_path: Path):
    art=tmp_path/'art';art.mkdir()
    rows=[]
    def add(method,eid,correct,md,ans='a',gold='10'):
        rows.append({'example_id':eid,'dataset':'d','seed':11,'budget':4,'method':method,'status':'scored','exact_match':correct,'question':'q 10','gold_answer':gold,'gold_answer_canonical':gold,'final_answer_raw':ans,'final_answer_canonical':ans,'result_metadata':md})
    add('external_l1_max','e1',True,{},ans='10'); add('direct_reserve_semantic_frontier_v2','e1',False,{'selector_candidate_pool':[{'predicted_answer':'10'},{'predicted_answer':'9'}],'candidate_count':2,'answer_group_count':2},ans='9')
    add('external_l1_max','e2',True,{},ans='10'); add('direct_reserve_semantic_frontier_v2','e2',False,{'selector_candidate_pool':[{'predicted_answer':'7'}],'candidate_count':1,'answer_group_count':1},ans='7')
    add('external_l1_max','e3',True,{},ans='100'); add('direct_reserve_semantic_frontier_v2','e3',False,{'selector_candidate_pool':[{'predicted_answer':'98'}],'candidate_count':1,'answer_group_count':1},ans='98',gold='100')
    add('external_l1_max','e4',True,{},ans='10'); add('direct_reserve_semantic_frontier_v2','e4',False,{},ans='x')
    (art/'per_example_records.jsonl').write_text('\n'.join(json.dumps(r) for r in rows),encoding='utf-8')
    subprocess.check_call([sys.executable,'scripts/build_external_baseline_loss_casebook.py','--artifact-dir',str(art),'--timestamp','20260429T_SELECTOR_COMPARISON_30CASE_COHERE'])
    assert (art/'external_l1_loss_casebook.csv').exists()
    assert (art/'external_l1_loss_casebook.jsonl').exists()
    assert Path('docs/EXTERNAL_L1_LOSS_CASEBOOK_20260429T_SELECTOR_COMPARISON_30CASE_COHERE.md').exists()
    j=[json.loads(l) for l in (art/'external_l1_loss_casebook.jsonl').read_text().splitlines() if l.strip()]
    assert any(r['loss_type']=='present_but_not_selected' for r in j)
    assert any(r['loss_type']=='absent_from_tree' for r in j)
    assert any(r['distance_category']=='near_numeric' for r in j)
    assert any(r['loss_type']=='unknown_missing_metadata' for r in j)

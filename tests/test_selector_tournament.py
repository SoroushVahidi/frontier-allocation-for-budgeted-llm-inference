from scripts.run_selector_tournament import run

def _row(eid,method,ans,gold,pool):
    return {'example_id':eid,'dataset':'d','seed':1,'budget':1,'method':method,'final_answer_canonical':ans,'gold_answer_canonical':gold,'result_metadata':{'selector_candidate_pool':pool}}

def test_oracle_not_selected_deployable():
    rows=[]
    pool=[{'predicted_answer':'a','source_family':'direct','is_original_selected':1},{'predicted_answer':'b','source_family':'alt'}]
    rows.append(_row('e1','direct_reserve_semantic_frontier_v2','a','b',pool)); rows.append(_row('e1','external_l1_max','a','b',pool))
    out,cb,best=run(rows)
    assert best['selector']!='oracle_selector'

def test_metrics_small_fixture():
    pool=[{'predicted_answer':'a','source_family':'direct','is_original_selected':1},{'predicted_answer':'b','source_family':'alt'},{'predicted_answer':'b','source_family':'alt2'}]
    rows=[_row('e1','direct_reserve_semantic_frontier_v2','a','b',pool),_row('e1','external_l1_max','a','b',pool)]
    out,_,_=run(rows)
    m={r['selector']:r for r in out}
    assert m['support_only']['accuracy']==1.0
    assert m['current_dr_v2']['accuracy']==0.0

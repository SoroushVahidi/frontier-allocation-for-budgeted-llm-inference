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

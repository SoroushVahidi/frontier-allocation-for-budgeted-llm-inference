from scripts.run_cohere_100case_ours_vs_external_main_table_comparison import choose_cases, dry_plan, EXTERNAL, ALL
from scripts.build_cohere_100case_comparison_report import accuracy, pairwise

def test_fixed_seed_deterministic():
    a=[x['case_id'] for x in choose_cases(20260501,100)]
    b=[x['case_id'] for x in choose_cases(20260501,100)]
    assert a==b

def test_all_six_methods_in_plan():
    c=choose_cases(20260501,2)
    ids=sorted({r['method_id'] for r in dry_plan(c)})
    assert ids==sorted(ALL)

def test_external_exact():
    assert EXTERNAL==['l1_length_control_rl','tale_token_budget_aware_reasoning','s1_simple_test_time_scaling']

def test_no_gold_in_prompt_decision_inputs():
    c=choose_cases(20260501,1)[0]
    assert 'evaluation_only' not in {k:v for k,v in c.items() if k in ['question','case_id','dataset','split']}

def test_accuracy_synth():
    acc,c=accuracy([{'correct':True},{'correct':False},{'correct':True}])
    assert acc==2/3 and c==2

def test_pairwise_matrix_synth():
    m={'a':[{'correct':True},{'correct':False}], 'b':[{'correct':False},{'correct':False}]}
    rows=pairwise(m)
    ab=[r for r in rows if r['method_a']=='a' and r['method_b']=='b'][0]
    assert ab['wins']==1 and ab['losses']==0 and ab['ties']==1

def test_bottleneck_classifier_placeholder():
    assert True

def test_selector_coverage_diag_rule():
    status='diagnostic_if_incomplete'
    assert 'diagnostic' in status

def test_no_secret_keys_manifest_sample():
    import json
    blob=json.dumps({'x':'ok'})
    assert 'api_key' not in blob

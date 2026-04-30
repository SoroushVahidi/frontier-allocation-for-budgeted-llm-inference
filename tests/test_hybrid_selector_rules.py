from scripts.analyze_hybrid_selector_rules import majority_vote, choose_rule, rule_metrics, DR,SF,PRM,OV,L1


def mk(ans,gold='g',meta=None):
    return {'final_answer_canonical':ans,'gold_answer_canonical':gold,'result_metadata':meta or {}}

def bundle_row(d='a',s='b',p='b',o='c',l1='a',gold='b',meta_p=None,meta_s=None):
    return {DR:mk(d,gold),SF:mk(s,gold,meta_s),PRM:mk(p,gold,meta_p),OV:mk(o,gold),L1:mk(l1,gold)}

def test_majority_vote_dr_tie_fallback():
    assert majority_vote(['a','b','a'],'a')=='a'
    assert majority_vote(['a','b','c','d'],'a')=='a'

def test_prm_selection_fix_agreement_override():
    m=bundle_row(d='x',s='y',p='y',gold='y')
    assert choose_rule('prm_and_selection_fix_agree',m)=='y'

def test_override_recovery_regression_counts():
    b={('1',):bundle_row(d='x',s='y',p='y',gold='y'),('2',):bundle_row(d='z',s='q',p='q',gold='z')}
    r=rule_metrics('use_selection_fix_v1',b,set(),set(),set())
    assert r['overrides_vs_dr_v2']==2
    assert r['recoveries_of_dr_v2_wrong']==1
    assert r['regressions_of_dr_v2_correct']==1

def test_oracle_upper_bound():
    b={('1',):bundle_row(d='x',s='y',p='z',o='g',gold='g'),('2',):bundle_row(d='x',s='y',p='z',o='q',gold='w')}
    r=rule_metrics('oracle_upper_bound_existing_internal',b,set(),set(),set())
    assert r['correct_count']==1

def test_deployable_rule_ignores_gold_in_decision():
    m=bundle_row(d='x',s='y',p='z',o='q',gold='x',meta_p={'parse_fallback':True})
    a=choose_rule('prm_unless_parse_fallback',m)
    m[DR]['gold_answer_canonical']='DIFFERENT'
    b=choose_rule('prm_unless_parse_fallback',m)
    assert a==b=='x'

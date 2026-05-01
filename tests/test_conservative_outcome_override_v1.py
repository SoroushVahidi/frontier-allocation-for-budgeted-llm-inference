from scripts.run_conservative_outcome_verifier_override_v1 import conservative_override_choice
from scripts.run_conservative_outcome_verifier_override_v1 import DR_CANDIDATES
from scripts.run_conservative_outcome_verifier_override_v1 import conservative_override_choice_v2
from scripts.run_conservative_outcome_verifier_override_v1 import support_only_with_guard_choice

def _row(selected='a',support=None,fam=None,proc=None,entropy=0.7,gap=1.0):
    return {'result_metadata':{
        'selected_answer_group':selected,
        'raw_support_count_by_answer_group': support or {'a':1,'b':3},
        'num_supporting_strategy_families_by_answer_group': fam or {'a':1,'b':2},
        'mean_process_score_by_answer_group': proc or {'a':0.7,'b':0.75},
        'answer_entropy':entropy,
        'top2_support_gap':gap,
    }}

def test_override_fires_only_with_strong_evidence():
    chosen, reason = conservative_override_choice(_row())
    assert chosen == 'b'
    assert reason['override'] is True
    assert reason['reasons']

def test_no_override_without_margin():
    chosen, reason = conservative_override_choice(_row(support={'a':2,'b':3}, fam={'a':1,'b':1}))
    assert chosen == 'a'
    assert reason['override'] is False

def test_rule_does_not_require_gold_labels():
    row = _row()
    row['gold_answer']='something'
    chosen, reason = conservative_override_choice(row)
    assert chosen in {'a','b'}
    assert 'gold' not in str(reason).lower()

def test_dr_candidates_include_semantic_v2_name():
    assert 'direct_reserve_semantic_frontier_v2' in DR_CANDIDATES

def test_selector_pool_fallback_support_works():
    row={'result_metadata':{'selector_candidate_pool':[
        {'normalized_answer':'10','is_original_selected':1},
        {'normalized_answer':'12','is_original_selected':0},
        {'normalized_answer':'12','is_original_selected':0},
    ],'answer_entropy':0.9,'top2_support_gap':1.0}}
    chosen, reason = conservative_override_choice(row)
    assert chosen in {'10','12'}
    assert isinstance(reason, dict)

def test_v2_overrides_on_strong_support():
    row=_row(support={'a':1,'b':2},fam={'a':1,'b':1})
    chosen, reason = conservative_override_choice_v2(row)
    assert chosen=='b' and reason['override'] is True

def test_v2_blocks_weak_support_and_logs_blockers():
    row=_row(support={'a':2,'b':2},fam={'a':1,'b':1})
    chosen, reason = conservative_override_choice_v2(row)
    assert chosen=='a' and reason['override'] is False
    assert reason['blocked_conditions']

def test_v2_does_not_use_gold():
    row=_row(support={'a':1,'b':2}); row['gold_answer']='b'
    _, reason = conservative_override_choice_v2(row)
    assert 'gold' not in str(reason).lower()

def test_v1_behavior_unchanged_strict():
    chosen,_=conservative_override_choice(_row(support={'a':1,'b':2},fam={'a':1,'b':1}))
    assert chosen=='a'

def test_support_only_with_guard_follows_support_when_clear():
    groups=[{'normalized_answer':'a','support_count':1,'source_family_count':1,'consistency_flags':{}},{'normalized_answer':'b','support_count':2,'source_family_count':2,'consistency_flags':{}}]
    chosen,reason=support_only_with_guard_choice('a',groups)
    assert chosen=='b' and reason['override'] is True

def test_support_only_with_guard_blocks_on_error_flag():
    groups=[{'normalized_answer':'a','support_count':1,'source_family_count':1,'consistency_flags':{}},{'normalized_answer':'b','support_count':2,'source_family_count':2,'consistency_flags':{'bad':1}}]
    chosen,reason=support_only_with_guard_choice('a',groups)
    assert chosen=='a' and reason['blocked_conditions']

def test_support_only_with_guard_no_label_leakage():
    groups=[{'normalized_answer':'a','support_count':1,'source_family_count':1,'consistency_flags':{},'gold':'b','correct':0,'l1':'b','oracle':'b'},
            {'normalized_answer':'b','support_count':2,'source_family_count':2,'consistency_flags':{},'gold':'b','correct':1,'l1':'b','oracle':'b'}]
    chosen,reason=support_only_with_guard_choice('a',groups)
    assert chosen=='b'
    assert 'gold' not in str(reason).lower()

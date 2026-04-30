from scripts.selector_reconstruction import reconstruct_groups, support_only_choice, oracle_choice

def _row(pool):
    return {'result_metadata':{'selector_candidate_pool':pool}}

def test_duplicate_answers_merge():
    gs=reconstruct_groups(_row([{'normalized_answer':'10'},{'normalized_answer':'10'},{'normalized_answer':'11'}]))
    d={g['normalized_answer']:g['support_count'] for g in gs}
    assert d['10']==2 and d['11']==1

def test_oracle_presence_logic():
    gs=reconstruct_groups(_row([{'normalized_answer':'10'}]))
    assert oracle_choice(gs,'10','x')=='10'
    assert oracle_choice(gs,'12','x')=='x'

def test_support_tiebreak_deterministic():
    gs=reconstruct_groups(_row([{'normalized_answer':'a'},{'normalized_answer':'b'}]))
    assert support_only_choice(gs,'')=='b'

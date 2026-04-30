from experiments.selector_error_features import compute_candidate_consistency_flags, compute_unified_confidence_error, build_group_feature_rows

def test_weekday_numeric_flag():
    f=compute_candidate_consistency_flags('What day of the week?','work','7')
    assert f['categorical_numeric_mismatch']

def test_confidence_penalizes_flags():
    a=compute_unified_confidence_error('What day?','', '7', support_count=2)
    b=compute_unified_confidence_error('How many?', '', '10', support_count=2)
    assert a['unified_error_score']>=b['unified_error_score']

def test_group_rows_include_scores():
    rows=build_group_feature_rows('How many?', [{'normalized_answer':'5','support_count':1,'final_answer':'5','trace':'x=5'}])
    assert 'hybrid_selector_score' in rows[0]

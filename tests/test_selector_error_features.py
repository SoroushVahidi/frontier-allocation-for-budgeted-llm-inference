from experiments.selector_error_features import (
    build_group_feature_rows,
    build_structural_target_feature_row,
    compute_candidate_consistency_flags,
    compute_unified_confidence_error,
)

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
    assert 'structural_selector_score' in rows[0]

def test_structural_target_feature_row_has_expected_fields():
    row=build_structural_target_feature_row(
        question='A book costs $12 and a pen costs $3. What is the total cost?',
        candidate_trace='book=12\npen=3\ntotal=15',
        candidate_code='book=12\npen=3\nprint(book + pen)',
        candidate_answer='15',
        execution_metadata={'target_unit':'money','target_entity':'total cost','candidate_role':'current_final'},
        support_count=2,
    )
    assert row['target_tuple']['question_kind'] == 'money'
    assert row['final_answer_role'] == 'target'
    assert row['last_operation_family'] in {'add', 'unknown'}
    assert 0.0 <= row['target_alignment_score'] <= 1.0
    assert 0.0 <= row['structural_selector_score'] <= 1.0

from scripts.analyze_cohere_dr_v2_trace_losses import classify


def row(**kw):
    base={'exact_match':'0','external_l1_exact_match':'1','dr_v2_absent_from_frontier':'0','dr_v2_present_not_selected':'0','dr_v2_extraction_suspected':'0','dr_v2_trace_available':'1'}
    base.update(kw); return base


def test_taxonomy_cases():
    assert classify(row(dr_v2_absent_from_frontier='1'))=='proposal_failure_absent_from_frontier'
    assert classify(row(dr_v2_present_not_selected='1'))=='selection_failure_present_not_selected'
    assert classify(row(dr_v2_extraction_suspected='1'))=='extraction_or_normalization_failure'
    assert classify(row(exact_match='1',external_l1_exact_match='1'))=='both_correct'
    assert classify(row(exact_match='1',external_l1_exact_match='0'))=='dr_v2_only_correct'

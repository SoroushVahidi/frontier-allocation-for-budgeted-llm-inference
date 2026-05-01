from experiments.self_consistency_majority_selector import (
    normalize_gsm8k_numeric_answer, extract_final_numeric_answer,
    select_self_consistency_answer, evaluate_self_consistency_case,
)


def test_numeric_normalization():
    assert normalize_gsm8k_numeric_answer('$18') == '18'
    assert normalize_gsm8k_numeric_answer('18.') == '18'
    assert normalize_gsm8k_numeric_answer('18.0') == '18'
    assert normalize_gsm8k_numeric_answer('0018') == '18'
    assert normalize_gsm8k_numeric_answer('1,800') == '1800'
    assert normalize_gsm8k_numeric_answer('0.500') == '0.5'
    assert normalize_gsm8k_numeric_answer('-03.50') == '-3.5'


def test_extract_patterns():
    assert extract_final_numeric_answer({'trace_text':'... The answer is 42'}) == '42'
    assert extract_final_numeric_answer({'reasoning':'blah #### 17'}) == '17'


def test_selection_and_tie_and_invalid():
    cands=[{'candidate_id':'a','trace_text':'The answer is 2','score':999},{'candidate_id':'b','trace_text':'#### 2','logprob':-9},{'candidate_id':'c','trace_text':'The answer is 3'},{'candidate_id':'d','trace_text':'nonnumeric'}]
    d=select_self_consistency_answer(cands)
    assert d['selected_normalized_answer']=='2'
    assert d['selected_vote_count']==2 and d['invalid_candidate_count']==1

    tie=select_self_consistency_answer([{'candidate_id':'x','trace_text':'The answer is 5'},{'candidate_id':'y','trace_text':'The answer is 6'}])
    assert tie['tie_flag'] is True
    assert tie['selected_candidate_id']=='x'


def test_all_invalid_and_eval_independence():
    d=select_self_consistency_answer([{'candidate_id':'a','trace_text':'none'},{'candidate_id':'b','trace_text':'x'}])
    assert d['all_invalid'] is True and d['selected_normalized_answer'] is None

    cands=[{'candidate_id':'a','trace_text':'The answer is 9'},{'candidate_id':'b','trace_text':'The answer is 8'}]
    d1=select_self_consistency_answer(cands)
    d2=select_self_consistency_answer(cands)
    assert d1['selected_normalized_answer']==d2['selected_normalized_answer']

    rec={'selected_answer_canonical':'8','evaluation_only':{'gold_answer':'9'}}
    e=evaluate_self_consistency_case(rec,d1)
    assert e['fix'] is True and e['break'] is False

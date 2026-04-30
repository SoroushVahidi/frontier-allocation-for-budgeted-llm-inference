from experiments.prm_step_verifier_rerank import StepVerifierResult, aggregate_trace_score

def test_aggregation_modes_basic_ordering():
    steps=[StepVerifierResult(1.0,1.0,False,'a'),StepVerifierResult(0.2,0.2,False,'b')]
    assert aggregate_trace_score(steps,'min_step')==0.2
    assert aggregate_trace_score(steps,'last_step')==0.2
    assert aggregate_trace_score(steps,'mean_step')==0.6

def test_major_error_cap_modes():
    steps=[StepVerifierResult(0.9,0.9,True,'bad')]
    assert aggregate_trace_score(steps,'hybrid_mean_min')<=0.25
    assert aggregate_trace_score(steps,'product')<=0.25
    assert aggregate_trace_score(steps,'mean_step')>0.25

def test_invalid_mode_raises():
    steps=[StepVerifierResult(0.5,None,False,'x')]
    try:
        aggregate_trace_score(steps,'unknown')
        assert False
    except ValueError:
        assert True

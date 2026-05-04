from experiments.selector_candidate_extraction import (
    build_candidates_from_metadata,
    build_candidates_from_metadata_diagnostic,
)


def test_extract_from_final_branch_states():
    md={"final_branch_states":[{"branch_id":"b1","predicted_answer":"42","trace_events":[{"reasoning_text":"r"}],"score":0.9,"branch_depth":2},{"branch_id":"b2","predicted_answer":"43"}]}
    c,s=build_candidates_from_metadata("q",md)
    assert len(c)==2
    assert s==["final_branch_states"]


def test_extract_from_selector_candidate_pool_and_fallback():
    c,s=build_candidates_from_metadata("q",{"selector_candidate_pool":[{"candidate_id":"c1","final_answer":"9","trace":"t"},{"candidate_id":"c2","final_answer":"10","trace":"u"}]})
    assert len(c)==2 and c[0].candidate_id=="c1" and s==["selector_candidate_pool"]
    c2,s2=build_candidates_from_metadata("q",{"final_answer":"7"})
    assert len(c2)==1 and s2==["final_answer_fallback"]


def test_dedup_only_truly_identical():
    md={"selector_candidate_pool":[{"candidate_id":"c1","final_answer":"9","trace":"t","source_id":"s"},{"candidate_id":"c1","final_answer":"9","trace":"t","source_id":"s"},{"candidate_id":"c1","final_answer":"9","trace":"t2","source_id":"s"}]}
    c,_=build_candidates_from_metadata("q",md)
    assert len(c)==2


def test_diagnostic_matches_plain_and_counts_skips():
    md = {
        "final_branch_states": [
            {"branch_id": "b0", "predicted_answer": ""},
            {"branch_id": "b1", "predicted_answer": "42"},
        ]
    }
    plain_c, plain_u = build_candidates_from_metadata("q", md)
    dc, du, diag = build_candidates_from_metadata_diagnostic("q", md)
    assert plain_c == dc and plain_u == du
    assert "empty_answer_field=1" in diag.extraction_skip_counts
    assert "final_branch_states" in diag.metadata_keys_present


def test_diagnostic_rows_not_list_increment_skip():
    md = {"final_branch_states": "not_a_list"}
    c, u, diag = build_candidates_from_metadata_diagnostic("q", md)
    assert not c and not u
    assert "final_branch_states:rows_not_list=1" in diag.extraction_skip_counts


def test_extract_from_direct_reserve_attempts_response_text_boxed():
    md = {
        "direct_reserve_attempts": [
            {
                "branch_id": "dr0",
                "response_text": r"Some reasoning \boxed{106} done.",
            }
        ]
    }
    c, src = build_candidates_from_metadata("q", md)
    assert len(c) == 1
    assert c[0].final_answer == "106"
    assert c[0].source_id == "direct_reserve_attempts_response_text"
    assert "direct_reserve_attempts_response_text" in src


def test_extract_from_final_branch_states_trace_when_predicted_empty():
    md = {
        "final_branch_states": [
            {
                "branch_id": "b0",
                "predicted_answer": "",
                "trace_events": [{"response_text": "The answer is 99"}],
            }
        ]
    }
    c, src = build_candidates_from_metadata("q", md)
    assert len(c) == 1
    assert c[0].final_answer == "99"
    assert "branch_state_trace_response_text:final_branch_states" in c[0].source_id
    assert any("branch_state_trace_response_text" in s for s in src)

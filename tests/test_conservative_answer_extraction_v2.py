from experiments.data import extract_final_answer_conservative_v2


def test_extracts_strict_final_answer_line() -> None:
    out = extract_final_answer_conservative_v2("work\nFINAL_ANSWER: 42\n")
    assert out["answer"] == "42"
    assert out["extraction_rule_used"] == "strict_final_answer_line"
    assert out["extraction_ambiguous"] is False


def test_extracts_alias_final_answer_line() -> None:
    out = extract_final_answer_conservative_v2("steps\nFinal Answer: 42\n")
    assert out["answer"] == "42"
    assert out["extraction_rule_used"] == "alias_final_answer_line"


def test_extracts_the_answer_is_line() -> None:
    out = extract_final_answer_conservative_v2("Let's compute.\nThe answer is 42.\n")
    assert out["answer"] == "42"
    assert out["extraction_rule_used"] == "alias_final_answer_line"


def test_extracts_therefore_answer_is_line() -> None:
    out = extract_final_answer_conservative_v2("Therefore, the answer is 42\n")
    assert out["answer"] == "42"
    assert out["extraction_rule_used"] == "alias_final_answer_line"


def test_extracts_boxed_numeric_answer() -> None:
    out = extract_final_answer_conservative_v2(r"result: \boxed{42}")
    assert out["answer"] == "42"
    assert out["extraction_rule_used"] == "boxed_numeric_answer"


def test_extracts_last_numeric_only_line() -> None:
    out = extract_final_answer_conservative_v2("reasoning line\n17\n")
    assert out["answer"] == "17"
    assert out["extraction_rule_used"] == "last_numeric_only_line"


def test_ambiguous_alias_lines_fail_conservatively() -> None:
    out = extract_final_answer_conservative_v2("Final Answer: 41\nFinal Answer: 42\n")
    assert out["answer"] is None
    assert out["extraction_ambiguous"] is True
    assert out["extraction_rule_used"] == "alias_final_answer_line"


def test_no_gold_or_prediction_inputs_required() -> None:
    out = extract_final_answer_conservative_v2("Answer: 9")
    assert out["answer"] == "9"

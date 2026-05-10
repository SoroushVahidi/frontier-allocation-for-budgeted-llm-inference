"""Static-string tests for APIBranchGenerator JSON / answer extraction (no network)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from experiments.branching import (
    APIBranchGenerator,
    BranchState,
    extract_labeled_numeric_leaf_from_step,
)


@pytest.fixture
def api_gen() -> APIBranchGenerator:
    return APIBranchGenerator(
        api_key="dummy-not-used",
        model="m",
        temperature=0.1,
        max_tokens=128,
        timeout_seconds=5,
        provider="openai",
    )


def test_safe_json_plain() -> None:
    raw = '{"action": "final", "answer": "3", "step": "x", "confidence": 0.9}'
    d = APIBranchGenerator._safe_json(raw)
    assert d.get("answer") == "3"


def test_safe_json_markdown_fence_full_wrap() -> None:
    raw = '```json\n{"action": "continue", "answer": "", "step": "hi", "confidence": 0.5}\n```\n'
    d = APIBranchGenerator._safe_json(raw)
    assert d.get("step") == "hi"


def test_safe_json_prose_before_balanced_object() -> None:
    raw = 'Here you go:\n{"action": "final", "answer": "", "step": "", "confidence": 1, "final_answer": "99"}\nThanks.'
    d = APIBranchGenerator._safe_json(raw)
    assert d.get("final_answer") == "99"


def test_safe_json_string_with_inner_braces() -> None:
    raw = '{"action": "final", "step": "use set {1,2}", "answer": "5", "confidence": 0.8}'
    d = APIBranchGenerator._safe_json(raw)
    assert d.get("answer") == "5"


def test_merge_wrapped_response_dict() -> None:
    inner = {"action": "final", "final_answer": "12", "step": "", "confidence": 0.7}
    merged = APIBranchGenerator._merge_wrapped_json_dicts({"response": inner, "noise": 1})
    assert merged.get("final_answer") == "12"
    assert merged.get("noise") == 1


def test_expand_fallback_phrase_final_answer() -> None:
    gen = APIBranchGenerator(
        api_key="dummy-not-used",
        model="m",
        temperature=0.1,
        max_tokens=128,
        timeout_seconds=5,
        provider="openai",
    )
    raw = "I think the final answer: 4800 is correct."
    with patch.object(APIBranchGenerator, "_call_api", return_value=raw):
        b = gen.init_branch("b0")
        gen.expand(b, "How many?", "")
    assert b.predicted_answer == "4800"
    assert b.is_done


def test_expand_fallback_boxed() -> None:
    gen = APIBranchGenerator(
        api_key="dummy-not-used",
        model="m",
        temperature=0.1,
        max_tokens=128,
        timeout_seconds=5,
        provider="openai",
    )
    raw = r"Some text \boxed{106} trailing"
    with patch.object(APIBranchGenerator, "_call_api", return_value=raw):
        b = gen.init_branch("b0")
        gen.expand(b, "Q", "")
    assert b.predicted_answer == "106"
    assert b.is_done


def test_expand_alternate_numeric_answer_key(api_gen: APIBranchGenerator) -> None:
    raw = '{"action": "final", "numeric_answer": 77, "step": "", "confidence": 1}'
    with patch.object(APIBranchGenerator, "_call_api", return_value=raw):
        b = api_gen.init_branch("b0")
        api_gen.expand(b, "Q", "")
    assert b.predicted_answer == "77"


def test_expand_does_not_commit_continue_with_json_answer(api_gen: APIBranchGenerator) -> None:
    raw = '{"action": "continue", "answer": "120", "step": "Subtotal after the first stage.", "confidence": 0.7}'
    with patch.object(APIBranchGenerator, "_call_api", return_value=raw):
        b = api_gen.init_branch("b0")
        api_gen.expand(b, "Q", "")
    assert b.is_done is False
    assert b.predicted_answer is None
    assert b.trace_events[-1].get("expand_answer_extraction_source") == "api_continue_no_final_answer"


def test_verify_alternate_keys_and_fallback(api_gen: APIBranchGenerator) -> None:
    raw = '{"confidence": 0.8, "solution_answer": "21"}'
    with patch.object(APIBranchGenerator, "_call_api", return_value=raw):
        b = api_gen.init_branch("b0")
        api_gen.verify(b, "Q")
    assert b.predicted_answer == "21"


def test_expand_invalid_json_prefers_phrase_over_random_numbers_in_prose() -> None:
    gen = APIBranchGenerator(
        api_key="dummy-not-used",
        model="m",
        temperature=0.1,
        max_tokens=128,
        timeout_seconds=5,
        provider="openai",
    )
    raw = "Not JSON. The answer is 3 and also 9000 appears."
    with patch.object(APIBranchGenerator, "_call_api", return_value=raw):
        b = gen.init_branch("b0")
        gen.expand(b, "Q", "")
    assert b.predicted_answer == "3"
    assert b.trace_events[-1].get("expand_answer_extraction_source") == "api_plain_text_fallback"


def test_safe_json_top_level_list_first_dict() -> None:
    raw = '[{"action": "final", "answer": "9", "step": "", "confidence": 1}]'
    d = APIBranchGenerator._safe_json(raw)
    assert d.get("answer") == "9"


def test_resolve_expand_answer_from_final_answer_key() -> None:
    raw = '{"action": "final", "answer": "", "step": "", "confidence": 1, "final_answer": "44"}'
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged)
    assert ans == "44"
    assert tag == "api_json_final_answer"


def test_resolve_expand_answer_ignores_json_answer_when_action_continue() -> None:
    raw = '{"action": "continue", "answer": "120", "step": "Subtotal after the first stage.", "confidence": 0.7}'
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged)
    assert ans == ""
    assert tag == "api_continue_no_final_answer"


def test_resolve_expand_answer_ignores_json_final_answer_when_action_continue() -> None:
    raw = '{"action": "continue", "final_answer": "120", "step": "Subtotal after the first stage.", "confidence": 0.7}'
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged)
    assert ans == ""
    assert tag == "api_continue_no_final_answer"


def test_resolve_expand_answer_accepts_json_answer_when_action_final() -> None:
    raw = '{"action": "final", "answer": "480", "step": "", "confidence": 0.9}'
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged)
    assert ans == "480"
    assert tag == "api_json_answer"


def test_resolve_expand_answer_accepts_json_answer_when_action_missing() -> None:
    raw = '{"answer": "480", "step": "", "confidence": 0.9}'
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged)
    assert ans == "480"
    assert tag == "api_json_answer"




def test_resolve_expand_answer_missing_action_boxed_fallback_still_works() -> None:
    raw = r'{"answer": "", "step": "Thus \\boxed{88}.", "confidence": 0.5}'
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged)
    assert ans == "88"
    assert tag == "api_json_reasoning_fallback"


def test_resolve_expand_answer_reasoning_step_boxed_continue() -> None:
    raw = r'{"action": "continue", "answer": "", "step": "Thus \\boxed{88}.", "confidence": 0.5}'
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged)
    assert ans == ""
    assert tag == "api_continue_no_final_answer"


def test_resolve_expand_answer_reasoning_step_hashes_continue() -> None:
    raw = '{"action": "continue", "answer": "", "step": "Intermediate computation. #### 88", "confidence": 0.5}'
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged)
    assert ans == ""
    assert tag == "api_continue_no_final_answer"


def test_resolve_expand_answer_reasoning_numeric_without_boxed() -> None:
    raw = '{"action": "continue", "answer": "", "step": "The total is 62.", "confidence": 0.5}'
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged)
    assert ans == ""
    assert tag == "api_continue_no_final_answer"


def test_resolve_expand_skips_ambiguous_continue_step_without_finality_hint() -> None:
    raw = (
        '{"action": "continue", "answer": "", "step": "4 quarters * 12 minutes per quarter = 48 minutes.", '
        '"confidence": 0.5}'
    )
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged)
    assert ans == ""
    assert tag == "api_continue_no_final_answer"


def test_resolve_expand_answer_parse_failed_records_tag() -> None:
    raw = '{"broken json'
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged)
    assert ans == ""
    assert tag == "api_parse_failed_no_answer"


def test_expand_skips_json_null_string_answer() -> None:
    raw = '{"action": "final", "answer": "null", "step": "", "confidence": 0.9}'
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged)
    assert ans == ""
    assert tag == "api_parse_failed_no_answer"


def test_verify_trace_has_extraction_source(api_gen: APIBranchGenerator) -> None:
    raw = '{"confidence": 0.8, "rationale_short": "Hence \\\\boxed{15}"}'
    with patch.object(APIBranchGenerator, "_call_api", return_value=raw):
        b = api_gen.init_branch("b0")
        api_gen.verify(b, "Q")
    assert b.predicted_answer == "15"
    assert b.trace_events[-1].get("verify_answer_extraction_source") == "api_json_reasoning_fallback"


def test_resolve_expand_numeric_leaf_prefers_explicit_answer_over_numeric_leaf_value() -> None:
    raw = (
        '{"action":"final","answer":"42","numeric_leaf_value":"99","numeric_leaf_status":"final",'
        '"step":"","confidence":1}'
    )
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged, expand_prompt_variant="numeric_leaf")
    assert ans == "42"
    assert tag == "api_json_answer"


def test_resolve_expand_numeric_leaf_final_uses_leaf_when_answer_missing() -> None:
    raw = (
        '{"action":"final","answer":"","numeric_leaf_value":"77","numeric_leaf_status":"final",'
        '"step":"","confidence":1}'
    )
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged, expand_prompt_variant="numeric_leaf")
    assert ans == "77"
    assert tag == "api_json_numeric_leaf_final"


def test_resolve_expand_numeric_leaf_continue_does_not_commit_leaf_as_answer() -> None:
    raw = (
        '{"action":"continue","answer":"","numeric_leaf_value":"10","numeric_leaf_status":"equation_progress",'
        '"step":"next step","confidence":0.6}'
    )
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged, expand_prompt_variant="numeric_leaf")
    assert ans == ""
    assert tag == "api_continue_no_final_answer"


def test_resolve_expand_numeric_leaf_continue_does_not_commit_boxed_or_hash_answer() -> None:
    raw_boxed = r'{"action":"continue","answer":"","step":"provisional \\boxed{10}","confidence":0.6}'
    merged_boxed = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw_boxed))
    ans_boxed, tag_boxed = APIBranchGenerator._resolve_expand_answer(
        raw_boxed, merged_boxed, expand_prompt_variant="numeric_leaf"
    )
    assert ans_boxed == ""
    assert tag_boxed == "api_continue_no_final_answer"

    raw_hash = '{"action":"continue","answer":"","step":"provisional #### 10","confidence":0.6}'
    merged_hash = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw_hash))
    ans_hash, tag_hash = APIBranchGenerator._resolve_expand_answer(
        raw_hash, merged_hash, expand_prompt_variant="numeric_leaf"
    )
    assert ans_hash == ""
    assert tag_hash == "api_continue_no_final_answer"


def test_resolve_numeric_leaf_skips_loose_last_number_in_step_prose() -> None:
    raw = '{"action":"continue","answer":"","step":"Values 5, 9, and 12 mentioned.","confidence":0.5}'
    merged = APIBranchGenerator._merge_wrapped_json_dicts(APIBranchGenerator._safe_json(raw))
    ans, tag = APIBranchGenerator._resolve_expand_answer(raw, merged, expand_prompt_variant="numeric_leaf")
    assert ans == ""
    assert tag == "api_continue_no_final_answer"


def test_extract_labeled_numeric_leaf_from_step() -> None:
    v, tag = extract_labeled_numeric_leaf_from_step("Provisional answer: 88 units.")
    assert v == "88"
    assert "provisional_answer" in tag


def test_extract_labeled_numeric_leaf_rejects_unlabeled_prose() -> None:
    v, tag = extract_labeled_numeric_leaf_from_step("The numbers are 3 and 4.")
    assert v == ""
    assert tag == ""


def test_expand_numeric_leaf_trace_records_leaf_metadata() -> None:
    gen = APIBranchGenerator(
        api_key="dummy-not-used",
        model="m",
        temperature=0.1,
        max_tokens=128,
        timeout_seconds=5,
        provider="openai",
        expand_prompt_variant="numeric_leaf",
    )
    raw = (
        '{"action":"continue","answer":"","step":"provisional answer: 15","numeric_leaf_value":"15",'
        '"numeric_leaf_status":"provisional","confidence":0.7}'
    )
    with patch.object(APIBranchGenerator, "_call_api", return_value=raw):
        b = gen.init_branch("b0")
        gen.expand(b, "Q", "")
    ev = b.trace_events[-1]
    assert ev.get("numeric_leaf_status") == "provisional"
    assert ev.get("numeric_leaf_value") == "15"


def test_expand_trace_records_unit_track_json_fields() -> None:
    gen = APIBranchGenerator(
        api_key="dummy-not-used",
        model="m",
        temperature=0.1,
        max_tokens=128,
        timeout_seconds=5,
        provider="openai",
    )
    raw = (
        '{"action":"final","answer":"24","confidence":0.8,"step":"done",'
        '"entity_ledger":[{"entity":"box","quantity_raw":"3","unit":"boxes"}],'
        '"target_entity":"items","target_unit":"items",'
        '"unit_consistency_status":"consistent","unit_consistency_notes":"ok",'
        '"unit_tracked_answer":"24"}'
    )
    with patch.object(APIBranchGenerator, "_call_api", return_value=raw):
        b = gen.init_branch("b0")
        gen.expand(b, "Q", "")
    ev = b.trace_events[-1]
    assert isinstance(ev.get("entity_ledger"), list)
    assert ev.get("target_entity") == "items"
    assert ev.get("target_unit") == "items"
    assert ev.get("unit_consistency_status") == "consistent"
    assert ev.get("unit_tracked_answer") == "24"


def test_simulated_branch_generator_unchanged() -> None:
    import random

    from experiments.branching import SimulatedBranchGenerator

    rng = random.Random(0)
    sim = SimulatedBranchGenerator(rng, max_depth=4, finish_prob_base=0.99, answer_noise=0.0)
    b = sim.init_branch("s0")
    for _ in range(20):
        sim.expand(b, "2+2?", "")
        if b.is_done:
            break
    assert b.predicted_answer is not None

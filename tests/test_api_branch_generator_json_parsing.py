"""Static-string tests for APIBranchGenerator JSON / answer extraction (no network)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from experiments.branching import APIBranchGenerator, BranchState


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

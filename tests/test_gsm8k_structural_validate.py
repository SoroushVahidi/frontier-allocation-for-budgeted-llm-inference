"""Tests for experiments/gsm8k_structural_validate.py (offline, no gold in validator)."""

from __future__ import annotations

import inspect
import json
import random
import string
from pathlib import Path
from typing import Any

import pytest

from experiments.gsm8k_structural_validate import validate_gsm8k_candidate

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "present_not_selected_replay"


def test_signature_has_no_gold_parameter() -> None:
    sig = inspect.signature(validate_gsm8k_candidate)
    assert "gold" not in sig.parameters


def test_never_raises_on_random_noise() -> None:
    rng = random.Random(42)
    for _ in range(300):
        noise = "".join(rng.choice(string.printable) for _ in range(rng.randint(0, 500)))
        out = validate_gsm8k_candidate(
            problem_text=noise,
            candidate_answer=noise[:30] if noise else None,
            candidate_trace=noise[30:120] if len(noise) > 120 else noise,
            candidate_code=noise if rng.random() < 0.25 else None,
            source_family="fuzz",
        )
        assert isinstance(out, dict)
        assert "errors" in out and "structural_score" in out


def test_rate_question_detects_type_and_cues() -> None:
    prob = "A car travels 180 miles in 3 hours. What is its average speed in miles per hour?"
    trace = "distance = 180\ntime = 3\nspeed = distance / time\nprint(speed)"
    out = validate_gsm8k_candidate(
        problem_text=prob,
        candidate_answer="60",
        candidate_trace=trace,
        candidate_code="distance = 180\ntime = 3\nprint(distance / time)",
        source_family="test",
    )
    assert out["target_question_type"] == "rate"
    assert "rate" in out["operation_cues_required"]
    assert out["code_syntax_ok"] is True
    assert isinstance(out["structural_score"], float)


def test_difference_question_warning_when_trace_weak() -> None:
    prob = (
        "Alice has 12 apples. Bob has 5 apples less than Alice. "
        "Express Bob's apple count as a single number."
    )
    out = validate_gsm8k_candidate(
        problem_text=prob,
        candidate_answer="7",
        candidate_trace="The answer is 7.",
        source_family="test",
    )
    assert out["target_question_type"] == "difference"
    assert "difference" in out["operation_cues_required"]
    assert any("comparison_question_weak_contrast" in w for w in out["warnings"])


def test_invalid_python_code_sets_syntax_error() -> None:
    out = validate_gsm8k_candidate(
        problem_text="What is 2+2?",
        candidate_answer="4",
        candidate_code="def broken(\n    pass",
        source_family="test",
    )
    assert out["code_syntax_ok"] is False
    assert any("code_syntax_error" in e for e in out["errors"])


def test_money_answer_numeric_acceptable() -> None:
    prob = "A book costs $12 and a pen costs $3. What is the total cost?"
    out = validate_gsm8k_candidate(
        problem_text=prob,
        candidate_answer="15",
        candidate_trace="12 + 3 = 15",
        source_family="test",
    )
    assert out["target_question_type"] == "money"
    assert out["target_type_match"] is True


def test_written_numbers_extracted() -> None:
    prob = "Mary has twelve apples and buys five more."
    out = validate_gsm8k_candidate(
        problem_text=prob,
        candidate_answer="17",
        candidate_trace="12 + 5 = 17",
        source_family="test",
    )
    norms = [m["normalized"] for m in out["quantity_mentions"]]
    assert "12" in norms and "5" in norms
    assert out["quantity_coverage"] is not None and out["quantity_coverage"] >= 0.5


def test_fixture_smoke_no_gold_passed_to_validator() -> None:
    p = FIXTURE_DIR / "openai_gsm8k_1087.json"
    if not p.is_file():
        pytest.skip("fixture missing")
    row = json.loads(p.read_text(encoding="utf-8"))
    question = str(row["question"])
    pal = str(row.get("current_pal_answer") or "")
    out = validate_gsm8k_candidate(
        problem_text=question,
        candidate_answer=pal,
        candidate_trace="stdout only — synthetic",
        source_family="fixture_smoke",
    )
    assert isinstance(out["structural_score"], float)
    assert isinstance(out["warnings"], list)


def test_execution_metadata_exec_ok() -> None:
    out = validate_gsm8k_candidate(
        problem_text="Compute 1+1.",
        candidate_answer="2",
        execution_metadata={"pal_exec_ok": 1},
    )
    assert out["exec_ok"] is True
    assert "target_tuple" in out and "structural_selector_score" in out
    assert out["target_tuple"]["question_kind"] == "unknown"
    assert "entity_unit_ledger_proxy" in out
    assert "duplicate_wrong_signature" in out
    out2 = validate_gsm8k_candidate(
        problem_text="Compute 1+1.",
        candidate_answer="2",
        execution_metadata={"pal_exec_ok": 0},
    )
    assert out2["exec_ok"] is False


def test_total_cue_family() -> None:
    prob = "There are 4 teams with 5 players each. How many players in total altogether?"
    trace = "total = 4 * 5\nprint(total)"
    out = validate_gsm8k_candidate(problem_text=prob, candidate_answer="20", candidate_trace=trace)
    assert "total" in out["operation_cues_required"]


def test_internal_exception_path_returns_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    import experiments.gsm8k_structural_validate as gsv

    def boom(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("forced")

    monkeypatch.setattr(gsv, "_validate_gsm8k_candidate_impl", boom)
    out = validate_gsm8k_candidate(problem_text="x", candidate_answer="1")
    assert any("validator_swallowed_exception" in e for e in out["errors"])
    assert "internal_exception" in out["abstain_reasons"]

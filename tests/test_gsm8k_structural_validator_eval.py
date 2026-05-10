"""Unit tests for offline GSM8K structural validator batch evaluation helpers."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from scripts.evaluate_gsm8k_structural_validator import (
    evidence_class_for_spec,
    matches_gold_offline_column,
    row_is_pal_internal_pool,
    row_matches_gold_row,
    score_family_for_evidence,
)


@pytest.mark.parametrize(
    ("trace", "code", "expected"),
    [
        ("some reasoning", "x=1\nprint(x)", "pal_trace_code"),
        ("some reasoning", "", "text_trace"),
        ("", "", "answer_only"),
        ("", "print(1)", "unknown"),
    ],
)
def test_evidence_class_for_spec(trace: str, code: str, expected: str) -> None:
    spec = {"trace": trace, "code": code}
    assert evidence_class_for_spec(spec) == expected


@pytest.mark.parametrize(
    ("ec", "sf"),
    [
        ("pal_trace_code", "structural_trace_score"),
        ("text_trace", "structural_trace_score"),
        ("answer_only", "answer_only_diagnostic"),
        ("unknown", "unknown"),
    ],
)
def test_score_family_for_evidence(ec: str, sf: str) -> None:
    assert score_family_for_evidence(ec) == sf


def test_row_is_pal_internal_pool_roles() -> None:
    assert row_is_pal_internal_pool({"candidate_role": "current_final", "source_family": "x"})
    assert row_is_pal_internal_pool(
        {"candidate_role": "other", "source_family": "overlay_previous"}
    )
    assert not row_is_pal_internal_pool(
        {"candidate_role": "external_answer", "source_family": "external_l1_max"}
    )


def test_matches_gold_offline_column_parsing() -> None:
    assert matches_gold_offline_column(True)
    assert not matches_gold_offline_column(False)
    assert matches_gold_offline_column("True")
    assert matches_gold_offline_column("1")
    assert not matches_gold_offline_column("False")


def test_row_matches_gold_row() -> None:
    assert row_matches_gold_row({"matches_gold_offline": True})
    assert not row_matches_gold_row({"matches_gold_offline": False})


def test_validate_call_never_receives_gold_kwarg() -> None:
    """Gold must only label rows after validation."""
    import scripts.evaluate_gsm8k_structural_validator as ev

    captured: dict[str, Any] = {}

    def fake_validate(**kwargs: Any) -> dict[str, Any]:
        captured.clear()
        captured.update(kwargs)
        return {"structural_score": 0.5, "warnings": [], "errors": []}

    spec = {
        "problem_text": "q",
        "candidate_answer": "1",
        "trace": "t",
        "code": "print(1)",
        "source_family": "test",
        "execution_metadata": {},
        "case_id": "c",
        "cohort": "other",
        "candidate_role": "current_final",
    }
    with patch.object(ev, "validate_gsm8k_candidate", side_effect=fake_validate):
        ev.validate_gsm8k_candidate(
            problem_text=spec["problem_text"],
            candidate_answer=spec["candidate_answer"],
            candidate_trace=spec.get("trace") or None,
            candidate_code=spec.get("code") or None,
            source_family=spec.get("source_family"),
            execution_metadata=spec.get("execution_metadata"),
        )
    assert "gold" not in captured
    assert set(captured.keys()) <= {
        "problem_text",
        "candidate_answer",
        "candidate_trace",
        "candidate_code",
        "source_family",
        "execution_metadata",
    }

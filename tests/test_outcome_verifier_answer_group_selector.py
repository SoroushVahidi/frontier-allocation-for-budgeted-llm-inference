"""Compatibility shim so CI can run `pytest tests/test_outcome_verifier_answer_group_selector.py`."""

from experiments.answer_grouped_outcome_verifier import select_answer_group_with_outcome_verifier


def test_outcome_verifier_answer_group_selector_importable() -> None:
    assert callable(select_answer_group_with_outcome_verifier)

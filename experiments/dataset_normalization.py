"""Normalize Hugging Face dataset rows into a small common shape for pilots and papers.

This is intentionally lightweight: no raw dataset storage, only field selection and
optional multiple-choice formatting for evaluation code that expects `question` + `answer`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from experiments.hf_datasets import HFDatasetSpec, _pick_first_present


@dataclass
class NormalizedExample:
    """Repo-friendly example for reasoning experiments."""

    dataset_key: str
    example_id: str
    question: str
    answer: str
    task_format: str  # e.g. free_form_math, multiple_choice, planning
    extra: dict[str, Any] = field(default_factory=dict)


def normalize_row(spec: HFDatasetSpec, row: dict[str, Any], index: int) -> NormalizedExample:
    question = _pick_first_present(row, spec.question_fields)
    answer = _pick_first_present(row, spec.answer_fields)

    task_format = "free_form_math"
    extra: dict[str, Any] = {}

    if spec.key == "Idavidrein/gpqa":
        task_format = "multiple_choice"
        for k in ("choices", "Choices", "options", "distractors"):
            if k in row and row[k] is not None:
                extra["choices"] = row[k]
                break
        if question and "choices" in extra:
            question = f"{question}\n\nChoices: {extra.get('choices')}"

    if spec.key == "HuggingFaceH4/aime_2024":
        task_format = "aime_integer"

    ex_id = f"{spec.key.replace('/', '_')}_{index}"
    return NormalizedExample(
        dataset_key=spec.key,
        example_id=ex_id,
        question=question,
        answer=answer,
        task_format=task_format,
        extra=extra,
    )


def normalized_to_pilot_dict(ex: NormalizedExample) -> dict[str, str]:
    return {"example_id": ex.example_id, "question": ex.question, "answer": ex.answer}

"""Normalize Hugging Face dataset rows into a small common shape for pilots and papers.

This is intentionally lightweight: no raw dataset storage, only field selection and
optional multiple-choice formatting for evaluation code that expects `question` + `answer`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from experiments.data import normalize_answer_text
from experiments.hf_datasets import HFDatasetSpec, _pick_first_present


@dataclass
class NormalizedExample:
    """Repo-friendly example for reasoning experiments."""

    dataset_name: str
    example_id: str
    split: str
    question: str
    raw_answer: str
    normalized_answer: str | None
    answer_type: str
    numeric_answer_flag: bool
    multiple_choice_flag: bool
    long_form_flag: bool
    task_format: str  # e.g. free_form_math, multiple_choice, planning
    recoverable_answer_flag: bool
    recoverability_reason: str | None
    extra: dict[str, Any] = field(default_factory=dict)


def normalize_row(
    spec: HFDatasetSpec,
    row: dict[str, Any],
    index: int,
    *,
    split: str = "",
) -> NormalizedExample:
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

    if spec.key in {"HuggingFaceH4/aime_2024", "MathArena/aime_2025", "MathArena/hmmt_feb_2025", "MathArena/brumo_2025"}:
        task_format = "aime_integer"

    if spec.key == "TIGER-Lab/MMLU-Pro":
        task_format = "multiple_choice"
        if row.get("options") is not None:
            extra["options"] = row.get("options")
        if row.get("answer_index") is not None:
            extra["answer_index"] = row.get("answer_index")
        if row.get("category") is not None:
            extra["category"] = row.get("category")

    if spec.key in {"livecodebench/code_generation", "livecodebench/execution-v2"}:
        task_format = "code_generation"
        for key in ("public_test_cases", "private_test_cases", "difficulty", "code", "input", "output"):
            if row.get(key) is not None:
                extra[key] = row.get(key)

    if spec.key == "lmms-lab/HLE-Verified":
        task_format = "mixed_reasoning"
        for key in ("answer_type", "subset", "category", "has_image"):
            if row.get(key) is not None:
                extra[key] = row.get(key)

    answer_norm = normalize_answer_text(answer)
    ex_id = f"{spec.key.replace('/', '_')}_{index}"
    return NormalizedExample(
        dataset_name=spec.key,
        example_id=ex_id,
        split=split,
        question=question,
        raw_answer=answer,
        normalized_answer=answer_norm["normalized_answer"],
        answer_type=str(answer_norm["answer_type"]),
        numeric_answer_flag=bool(answer_norm["numeric_answer_flag"]),
        multiple_choice_flag=bool(answer_norm["multiple_choice_flag"]),
        long_form_flag=bool(answer_norm["long_form_flag"]),
        task_format=task_format,
        recoverable_answer_flag=bool(answer_norm["recoverable"]),
        recoverability_reason=answer_norm["recoverability_reason"],
        extra=extra,
    )


def normalized_to_pilot_dict(ex: NormalizedExample) -> dict[str, str]:
    answer = ex.normalized_answer if ex.normalized_answer is not None else ex.raw_answer
    return {"example_id": ex.example_id, "question": ex.question, "answer": answer}

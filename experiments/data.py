"""Data loading helpers for pilot experiments (JSONL/HF/mock)."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import random
import re
from typing import Any

from experiments.hf_datasets import sample_hf_examples


@dataclass
class PilotExample:
    """Single benchmark example used by the pilot."""

    example_id: str
    question: str
    answer: str


ANSWER_PATTERN = re.compile(r"####\s*([-+]?\d[\d,]*(?:\.\d+)?)")
BOXED_PATTERN = re.compile(r"\\boxed\{([^}]*)\}")
NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
MCQ_LABEL_PATTERN = re.compile(r"\b([A-E])\b")
FRACTION_PATTERN = re.compile(r"^\s*([-+]?\d+)\s*/\s*(\d+)\s*$")


def _normalize_numeric_token(token: str) -> str | None:
    cleaned = token.replace(",", "").strip()
    if not cleaned:
        return None
    frac = FRACTION_PATTERN.match(cleaned)
    if frac:
        num = int(frac.group(1))
        den = int(frac.group(2))
        if den == 0:
            return None
        cleaned = str(num / den)
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if value.is_integer():
        return str(int(value))
    return f"{value:.10g}"


def _normalize_text_answer(text: str) -> str:
    return " ".join(text.strip().lower().split())


def normalize_answer_text(answer_text: str | None) -> dict[str, Any]:
    """Canonical answer normalization with recoverability metadata.

    Returns a compact dict suitable for branch-observability and dataset-normalization
    layers. This function is intentionally conservative and deterministic.
    """
    if answer_text is None or not str(answer_text).strip():
        return {
            "normalized_answer": None,
            "recoverable": False,
            "recoverability_reason": "missing_or_empty_answer_text",
            "answer_type": "missing",
            "numeric_answer_flag": False,
            "multiple_choice_flag": False,
            "long_form_flag": False,
            "normalization_method": "none",
        }

    text = str(answer_text).strip()
    long_form_flag = len(text) > 160 or "\n" in text

    mcq_match = MCQ_LABEL_PATTERN.search(text.upper())
    if mcq_match:
        return {
            "normalized_answer": mcq_match.group(1),
            "recoverable": True,
            "recoverability_reason": None,
            "answer_type": "multiple_choice",
            "numeric_answer_flag": False,
            "multiple_choice_flag": True,
            "long_form_flag": long_form_flag,
            "normalization_method": "mcq_label_extract",
        }

    extracted = extract_final_answer(text)
    numeric = _normalize_numeric_token(extracted)
    if numeric is not None:
        return {
            "normalized_answer": numeric,
            "recoverable": True,
            "recoverability_reason": None,
            "answer_type": "numeric",
            "numeric_answer_flag": True,
            "multiple_choice_flag": False,
            "long_form_flag": long_form_flag,
            "normalization_method": "numeric_extract",
        }

    normalized_text = _normalize_text_answer(extracted)
    return {
        "normalized_answer": normalized_text if normalized_text else None,
        "recoverable": bool(normalized_text),
        "recoverability_reason": None if normalized_text else "text_normalization_empty",
        "answer_type": "short_text" if normalized_text else "missing",
        "numeric_answer_flag": False,
        "multiple_choice_flag": False,
        "long_form_flag": long_form_flag,
        "normalization_method": "text_canonicalization",
    }


def extract_final_answer(answer_text: str) -> str:
    """Extract a compact final answer for GSM8K/MATH-style response fields."""
    match = ANSWER_PATTERN.search(answer_text)
    if not match:
        boxed = BOXED_PATTERN.findall(answer_text)
        if boxed:
            candidate = boxed[-1].strip()
            number_match = NUMBER_PATTERN.findall(candidate)
            return number_match[-1].replace(",", "") if number_match else candidate
        nums = NUMBER_PATTERN.findall(answer_text)
        if nums:
            return nums[-1].replace(",", "")
        return answer_text.strip()
    return match.group(1).replace(",", "")


def load_pilot_examples(config: dict[str, Any]) -> tuple[list[PilotExample], dict[str, Any]]:
    """Load a configurable subset of pilot examples with safe local fallback.

    Priority order:
    1) JSONL file path from config
    2) HuggingFace datasets (configured by hf_dataset_* keys)
    3) local mock arithmetic examples (if enabled)
    """
    num_examples = int(config["pilot_size"])
    seed = int(config["seed"])

    jsonl_path = config.get("gsm8k_jsonl_path")
    if jsonl_path:
        examples = _load_from_jsonl(Path(jsonl_path), num_examples)
        return examples, {"data_source": "jsonl", "path": str(jsonl_path)}

    hf_dataset_name = str(config.get("hf_dataset_name", "openai/gsm8k"))
    hf_dataset_split = str(config.get("hf_dataset_split", config.get("gsm8k_split", "test")))
    hf_dataset_config = config.get("hf_dataset_config")

    try:
        rows = sample_hf_examples(
            dataset_name=hf_dataset_name,
            pilot_size=num_examples,
            seed=seed,
            split=hf_dataset_split,
            config_name=str(hf_dataset_config) if hf_dataset_config is not None else None,
        )
        examples = [
            PilotExample(
                example_id=row["example_id"],
                question=row["question"],
                answer=extract_final_answer(row["answer"]),
            )
            for row in rows
        ]
        return examples, {"data_source": f"huggingface:{hf_dataset_name}", "split": hf_dataset_split}
    except Exception as exc:  # noqa: BLE001 - explicit fallback for lightweight pilot
        if not config.get("allow_mock_data", True):
            raise RuntimeError(
                f"Could not load HuggingFace dataset {hf_dataset_name} and mock mode is disabled. "
                f"Original error: {exc}"
            ) from exc

        examples = _build_mock_arithmetic_examples(num_examples=num_examples, seed=seed)
        return examples, {
            "data_source": "mock_arithmetic",
            "note": f"Fallback used because HuggingFace dataset {hf_dataset_name} loading failed.",
            "load_error": f"{type(exc).__name__}: {exc}",
        }


def _load_from_jsonl(path: Path, num_examples: int) -> list[PilotExample]:
    examples: list[PilotExample] = []
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if idx >= num_examples:
                break
            row = json.loads(line)
            examples.append(
                PilotExample(
                    example_id=f"jsonl_{idx}",
                    question=row["question"],
                    answer=extract_final_answer(row["answer"]),
                )
            )
    return examples


def _build_mock_arithmetic_examples(num_examples: int, seed: int) -> list[PilotExample]:
    rng = random.Random(seed)
    examples: list[PilotExample] = []
    for i in range(num_examples):
        a = rng.randint(5, 99)
        b = rng.randint(2, 40)
        c = rng.randint(1, 15)
        question = f"If a store sells {a} apples and then sells {b} more, then throws out {c}, how many are left?"
        answer = str(a + b - c)
        examples.append(PilotExample(example_id=f"mock_{i}", question=question, answer=answer))
    return examples

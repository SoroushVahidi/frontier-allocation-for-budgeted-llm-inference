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

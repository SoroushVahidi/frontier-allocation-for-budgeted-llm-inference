from __future__ import annotations

import json
from pathlib import Path

from experiments.dataset_normalization import normalize_row
from experiments.hf_datasets import resolve_dataset_spec


def test_readiness_bundle_config_contains_expected_datasets() -> None:
    payload = json.loads(Path("configs/dataset_experiment_readiness_bundles.json").read_text(encoding="utf-8"))
    bundles = payload["bundles"]

    exact = bundles["exact_answer_math_expansion"]["datasets"]
    assert "MathArena/aime_2025" in exact
    assert "MathArena/hmmt_feb_2025" in exact
    assert "MathArena/brumo_2025" in exact

    breadth = bundles["breadth_control_mcq"]["datasets"]
    assert breadth == ["TIGER-Lab/MMLU-Pro"]

    codegen = bundles["code_generation_partial"]["datasets"]
    assert "livecodebench/code_generation" in codegen
    assert "livecodebench/execution-v2" in codegen


def test_mmlu_pro_and_livecodebench_normalization_preserves_task_metadata() -> None:
    mmlu_spec = resolve_dataset_spec("mmlu-pro")
    mmlu_row = {
        "question": "Which option is correct?",
        "answer": "B",
        "answer_index": 1,
        "options": ["A", "B", "C", "D"],
        "category": "biology",
    }
    mmlu = normalize_row(mmlu_spec, mmlu_row, 0, split="test")
    assert mmlu.task_format == "multiple_choice"
    assert mmlu.extra["answer_index"] == 1
    assert mmlu.extra["category"] == "biology"

    lcb_spec = resolve_dataset_spec("livecodebench")
    lcb_row = {
        "question_content": "Write a function add(a,b)",
        "starter_code": "def add(a,b):\n    pass",
        "public_test_cases": [{"input": "1 2", "output": "3"}],
        "private_test_cases": [{"input": "2 2", "output": "4"}],
        "difficulty": "easy",
    }
    lcb = normalize_row(lcb_spec, lcb_row, 0, split="test")
    assert lcb.task_format == "code_generation"
    assert "public_test_cases" in lcb.extra
    assert "private_test_cases" in lcb.extra

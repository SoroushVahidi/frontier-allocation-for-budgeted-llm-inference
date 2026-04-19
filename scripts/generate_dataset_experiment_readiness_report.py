#!/usr/bin/env python3
"""Generate experiment-readiness report for newly integrated reasoning datasets."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.dataset_normalization import normalize_row
from experiments.hf_datasets import check_hf_dataset_access, resolve_dataset_spec, sample_hf_examples


SCOPED_DATASETS = [
    "aime_2025",
    "hmmt",
    "brumo",
    "mmlu-pro",
    "livecodebench",
    "livecodebench_execution",
    "hle",
]


def _task_type_for(key: str) -> str:
    if key in {"MathArena/aime_2025", "MathArena/hmmt_feb_2025", "MathArena/brumo_2025"}:
        return "exact_answer_math"
    if key == "TIGER-Lab/MMLU-Pro":
        return "multiple_choice"
    if key.startswith("livecodebench/"):
        return "code_generation"
    if key == "lmms-lab/HLE-Verified":
        return "mixed_text_reasoning"
    return "unknown"


def _classify(dataset_key: str, loader_ok: bool, schema_normalized: bool) -> tuple[str, str, str]:
    if dataset_key in {"MathArena/aime_2025", "MathArena/hmmt_feb_2025", "MathArena/brumo_2025"}:
        if loader_ok and schema_normalized:
            return (
                "experiment_ready",
                "",
                "None required for pilot math path; include in exact_answer_math_expansion bundle.",
            )
        return ("partially_ready", "Loader/schema issue blocks immediate pilot usage.", "Fix loader or schema mapping.")

    if dataset_key == "TIGER-Lab/MMLU-Pro":
        return (
            "partially_ready",
            (
                "Dataset loads and normalizes, but current runners are optimized for direct-answer matching rather "
                "than option-constrained MCQ inference with calibrated distractor handling."
            ),
            "Add MCQ-native runner path that consumes options and answer_index during generation and scoring.",
        )

    if dataset_key.startswith("livecodebench/"):
        return (
            "partially_ready",
            (
                "Dataset loads and metadata is preserved, but repository lacks a production-safe code execution "
                "grading harness for generated solutions."
            ),
            "Wire a sandboxed code-evaluation runner and deterministic testcase grading interface.",
        )

    if dataset_key == "lmms-lab/HLE-Verified":
        return (
            "partially_ready",
            "Text rows are usable, but image-aware evaluation path is not wired in current pilot runners.",
            "Add multimodal-aware loader/runner or restrict to validated text-only subset with explicit policy.",
        )

    return ("not_ready", "Unsupported by current readiness script.", "Define schema and runner compatibility.")


def _row_for_alias(name: str) -> dict[str, Any]:
    spec = resolve_dataset_spec(name)
    access = check_hf_dataset_access(spec.key)
    loader_ok = bool(access.get("ok"))

    sample_error = ""
    sample_rows: list[dict[str, str]] = []
    if loader_ok:
        try:
            sample_rows = sample_hf_examples(spec.key, pilot_size=2, seed=13)
        except Exception as exc:  # noqa: BLE001
            sample_error = f"{type(exc).__name__}: {exc}"

    schema_normalized = False
    normalized_preview: dict[str, Any] | None = None
    if sample_rows:
        question_value = sample_rows[0].get("question", "")
        answer_value = sample_rows[0].get("answer", "")
        synthetic_row = {
            "question": question_value,
            "problem": question_value,
            "question_content": question_value,
            "code": question_value,
            "input": sample_rows[0].get("input", question_value),
            "answer": answer_value,
            "output": sample_rows[0].get("output", answer_value),
            "starter_code": answer_value,
            "answer_index": sample_rows[0].get("answer_index", ""),
            "options": sample_rows[0].get("choices", ""),
            "category": sample_rows[0].get("category", ""),
            "public_test_cases": sample_rows[0].get("public_test_cases", ""),
            "private_test_cases": sample_rows[0].get("private_test_cases", ""),
            "difficulty": sample_rows[0].get("difficulty", ""),
            "answer_type": sample_rows[0].get("answer_type", ""),
            "subset": sample_rows[0].get("subset", ""),
            "has_image": sample_rows[0].get("has_image", ""),
        }
        ex = normalize_row(spec, synthetic_row, 0, split=spec.default_split)
        normalized_preview = {
            "task_format": ex.task_format,
            "normalized_answer": ex.normalized_answer,
            "multiple_choice_flag": ex.multiple_choice_flag,
            "extra_keys": sorted(ex.extra.keys()),
        }
        schema_normalized = bool(ex.question.strip()) and bool(ex.raw_answer.strip())

    status, reason, next_step = _classify(spec.key, loader_ok=loader_ok and not sample_error, schema_normalized=schema_normalized)
    task_type = _task_type_for(spec.key)

    runner_compatible = spec.key in {"MathArena/aime_2025", "MathArena/hmmt_feb_2025", "MathArena/brumo_2025"}
    automatic_grading = task_type in {"exact_answer_math", "multiple_choice"} and not spec.key.startswith("livecodebench/")

    return {
        "dataset_name": spec.key,
        "dataset_status": status,
        "task_type": task_type,
        "loader_working": bool(loader_ok and not sample_error),
        "schema_normalized": schema_normalized,
        "current_runner_compatible": runner_compatible,
        "automatic_grading_supported": automatic_grading,
        "exact_answer_math_ready": task_type == "exact_answer_math" and status == "experiment_ready",
        "mcq_ready": spec.key == "TIGER-Lab/MMLU-Pro" and status == "experiment_ready",
        "code_execution_ready": False,
        "config_added": spec.key in {
            "MathArena/aime_2025",
            "MathArena/hmmt_feb_2025",
            "MathArena/brumo_2025",
            "TIGER-Lab/MMLU-Pro",
            "livecodebench/code_generation",
            "livecodebench/execution-v2",
        },
        "smoke_test_passed": bool(loader_ok and not sample_error and schema_normalized),
        "reason_if_not_fully_ready": reason,
        "next_step_needed": next_step,
        "sample_error": sample_error,
        "normalization_preview": normalized_preview,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate dataset experiment-readiness report")
    parser.add_argument("--output-dir", default="docs/reports")
    args = parser.parse_args()

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = [_row_for_alias(name) for name in SCOPED_DATASETS]

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/generate_dataset_experiment_readiness_report.py",
        "scoped_datasets": SCOPED_DATASETS,
        "rows": rows,
    }

    json_path = out_dir / "dataset_experiment_readiness_report.json"
    csv_path = out_dir / "dataset_experiment_readiness_report.csv"

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "dataset_name",
                "dataset_status",
                "task_type",
                "loader_working",
                "schema_normalized",
                "current_runner_compatible",
                "automatic_grading_supported",
                "exact_answer_math_ready",
                "mcq_ready",
                "code_execution_ready",
                "config_added",
                "smoke_test_passed",
                "reason_if_not_fully_ready",
                "next_step_needed",
                "sample_error",
            ],
        )
        writer.writeheader()
        for row in rows:
            out_row = dict(row)
            out_row.pop("normalization_preview", None)
            writer.writerow(out_row)

    print(str(json_path))
    print(str(csv_path))


if __name__ == "__main__":
    main()

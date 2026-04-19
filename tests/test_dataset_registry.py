from __future__ import annotations

import json
from pathlib import Path

from experiments.hf_datasets import (
    check_git_dataset_access,
    resolve_dataset_spec,
    resolve_git_dataset_spec,
    sample_git_dataset_examples,
)


def _write_minimal_naturalplan_clone(root: Path) -> None:
    (root / "data").mkdir(parents=True, exist_ok=True)
    for name in [
        "trip_planning",
        "meeting_planning",
        "calendar_scheduling",
    ]:
        payload = {
            f"{name}_example_0": {
                "prompt_0shot": f"question for {name}",
                "prompt_5shot": f"few-shot question for {name}",
                "golden_plan": f"gold plan for {name}",
            }
        }
        (root / "data" / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")

    for script_name in [
        "evaluate_trip_planning.py",
        "evaluate_meeting_planning.py",
        "evaluate_calendar_scheduling.py",
    ]:
        (root / script_name).write_text("# stub\n", encoding="utf-8")


def test_alias_resolution_for_math500_and_amo_bench() -> None:
    math500 = resolve_dataset_spec("math-500")
    assert math500.key == "HuggingFaceH4/MATH-500"
    assert "problem" in math500.question_fields
    assert "answer" in math500.answer_fields

    amo = resolve_dataset_spec("amo-bench")
    assert amo.key == "meituan-longcat/AMO-Bench"
    assert "prompt" in amo.question_fields
    assert "answer" in amo.answer_fields


def test_alias_resolution_for_new_requested_datasets() -> None:
    aime_2025 = resolve_dataset_spec("aime_2025")
    assert aime_2025.key == "MathArena/aime_2025"
    assert "problem" in aime_2025.question_fields
    assert "answer" in aime_2025.answer_fields

    hmmt = resolve_dataset_spec("hmmt")
    assert hmmt.key == "MathArena/hmmt_feb_2025"

    brumo = resolve_dataset_spec("BRUMO")
    assert brumo.key == "MathArena/brumo_2025"

    mmlu_pro = resolve_dataset_spec("mmlu-pro")
    assert mmlu_pro.key == "TIGER-Lab/MMLU-Pro"
    assert "question" in mmlu_pro.question_fields
    assert "answer_index" in mmlu_pro.answer_fields

    lcb = resolve_dataset_spec("livecodebench")
    assert lcb.key == "livecodebench/code_generation"

    lcb_exec = resolve_dataset_spec("livecodebench_execution")
    assert lcb_exec.key == "livecodebench/execution-v2"
    assert "output" in lcb_exec.answer_fields

    hle = resolve_dataset_spec("hle")
    assert hle.key == "cais/hle"
    assert "question" in hle.question_fields

    hle_text = resolve_dataset_spec("hle_text_only")
    assert hle_text.key == "cais/hle_text_only"

    hle_auto = resolve_dataset_spec("hle_auto_gradable")
    assert hle_auto.key == "cais/hle_auto_gradable"


def test_naturalplan_git_spec_resolution() -> None:
    spec = resolve_git_dataset_spec("NaturalPlan")
    assert spec.key == "google-deepmind/natural-plan"
    assert spec.repo_url == "https://github.com/google-deepmind/natural-plan"
    assert "data/trip_planning.json" in spec.required_files


def test_check_git_dataset_access_reports_missing_files(tmp_path: Path, monkeypatch) -> None:
    clone_root = tmp_path / "natural-plan"
    clone_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("NATURAL_PLAN_DIR", str(clone_root))

    report = check_git_dataset_access("google-deepmind/natural-plan")
    assert report["ok"] is False
    assert report["missing_files"]


def test_sample_git_dataset_examples_from_local_clone(tmp_path: Path, monkeypatch) -> None:
    clone_root = tmp_path / "natural-plan"
    _write_minimal_naturalplan_clone(clone_root)
    monkeypatch.setenv("NATURAL_PLAN_DIR", str(clone_root))

    report = check_git_dataset_access("naturalplan")
    assert report["ok"] is True

    rows = sample_git_dataset_examples("natural_plan", pilot_size=2, seed=0)
    assert rows
    assert all(row["question"] for row in rows)
    assert all(row["answer"] for row in rows)
    assert all("task_name" in row for row in rows)

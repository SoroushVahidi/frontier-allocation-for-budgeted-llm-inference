from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path


def _write_loss_artifact(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "example_id",
                "dataset",
                "question",
                "ground_truth",
                "absent_from_tree",
                "present_not_selected",
                "is_correct",
                "failure_type",
            ],
        )
        w.writeheader()
        for i in range(4):
            w.writerow({"example_id": f"a{i}", "dataset": "openai/gsm8k", "question": f"Q a{i}", "ground_truth": "4", "absent_from_tree": 1, "present_not_selected": 0, "is_correct": 0, "failure_type": "absent_from_tree"})
        for i in range(4):
            w.writerow({"example_id": f"p{i}", "dataset": "openai/gsm8k", "question": f"Q p{i}", "ground_truth": "5", "absent_from_tree": 0, "present_not_selected": 1, "is_correct": 0, "failure_type": "present_not_selected"})
        for i in range(4):
            w.writerow({"example_id": f"c{i}", "dataset": "openai/gsm8k", "question": f"Q c{i}", "ground_truth": "6", "absent_from_tree": 0, "present_not_selected": 0, "is_correct": 1, "failure_type": "correct"})


def test_dry_run_planning_and_outputs(tmp_path: Path) -> None:
    loss = tmp_path / "loss.csv"
    _write_loss_artifact(loss)
    ts = "TEST_DIRECT_RESERVE_DRY"
    out = Path("outputs") / f"cohere_direct_reserve_validation_{ts}"

    cmd = [
        sys.executable,
        "scripts/run_cohere_direct_reserve_validation.py",
        "--timestamp",
        ts,
        "--loss-artifact",
        str(loss),
        "--loss-artifact-glob",
        "outputs/NO_MATCH/per_case_results.csv",
        "--max-cases",
        "6",
        "--dry-run",
    ]
    subprocess.run(cmd, check=True)

    required = [
        "manifest.json",
        "planned_cases.csv",
        "per_case_method_results.csv",
        "per_method_summary.csv",
        "per_stratum_summary.csv",
        "coverage_summary.csv",
        "answer_group_summary.csv",
        "candidate_branch_table.csv",
        "action_trace.jsonl",
        "final_branch_states.jsonl",
        "tree_decision_traces.jsonl",
        "loss_cases.jsonl",
        "loss_cases.csv",
        "loss_cases_for_manual_inspection.md",
        "difference_cases.jsonl",
        "difference_cases_for_manual_inspection.md",
        "missing_fields_report.csv",
        "README.md",
    ]
    for name in required:
        assert (out / name).exists(), name

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["real_api_enabled"] is False


def test_exclusion_reduces_overlap(tmp_path: Path) -> None:
    loss = tmp_path / "loss.csv"
    _write_loss_artifact(loss)
    prev = tmp_path / "prev"
    prev.mkdir(parents=True, exist_ok=True)
    with (prev / "planned_cases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["example_id"])
        w.writeheader()
        w.writerow({"example_id": "a0"})
        w.writerow({"example_id": "p0"})

    ts = "TEST_DIRECT_RESERVE_EXCL"
    out = Path("outputs") / f"cohere_direct_reserve_validation_{ts}"
    cmd = [
        sys.executable,
        "scripts/run_cohere_direct_reserve_validation.py",
        "--timestamp",
        ts,
        "--loss-artifact",
        str(loss),
        "--loss-artifact-glob",
        "outputs/NO_MATCH/per_case_results.csv",
        "--max-cases",
        "4",
        "--exclude-previous-output",
        str(prev),
        "--dry-run",
    ]
    subprocess.run(cmd, check=True)
    planned = list(csv.DictReader((out / "planned_cases.csv").open("r", encoding="utf-8")))
    assert all(r["example_id"] not in {"a0", "p0"} for r in planned)


def test_real_api_refused_without_key(tmp_path: Path) -> None:
    loss = tmp_path / "loss.csv"
    _write_loss_artifact(loss)
    cmd = [
        sys.executable,
        "scripts/run_cohere_direct_reserve_validation.py",
        "--timestamp",
        "TEST_DIRECT_RESERVE_NO_KEY",
        "--loss-artifact",
        str(loss),
        "--loss-artifact-glob",
        "outputs/NO_MATCH/per_case_results.csv",
        "--max-cases",
        "1",
        "--run-real-api",
    ]
    env = dict(os.environ)
    env.pop("COHERE_API_KEY", None)
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "COHERE_API_KEY missing" in (proc.stdout + proc.stderr)

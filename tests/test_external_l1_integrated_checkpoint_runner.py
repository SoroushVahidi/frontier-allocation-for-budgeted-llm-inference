from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/run_external_l1_integrated_checkpoint.py"
READINESS_DIR = REPO / "outputs/external_l1_checkpoint_readiness_20260508T021402Z"
CASE_FILE = READINESS_DIR / "recommended_checkpoint_cases.csv"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=True,
    )


def _latest_dir(prefix: str) -> Path:
    dirs = sorted((REPO / "outputs").glob(f"{prefix}_*"))
    assert dirs
    return dirs[-1]


def test_dry_run_creates_required_files_and_no_api_manifest() -> None:
    _run(
        "--readiness-dir",
        str(READINESS_DIR),
        "--case-file",
        str(CASE_FILE),
        "--stage-name",
        "stage2_test",
        "--max-new-cohere-calls",
        "50",
        "--reuse-external-l1",
        "--dry-run-only",
    )
    out = _latest_dir("external_l1_stage2_test_integrated_checkpoint_dry_run")
    required = [
        "stage_checkpoint_manifest.json",
        "selected_stage_cases.csv",
        "preflight_status.json",
        "stage_checkpoint_results.csv",
        "stage_checkpoint_summary.json",
        "stage_checkpoint_report.md",
    ]
    for name in required:
        p = out / name
        assert p.exists()
        assert p.stat().st_size > 0
    manifest = json.loads((out / "stage_checkpoint_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "stage_checkpoint_summary.json").read_text(encoding="utf-8"))
    assert manifest["no_api_calls"] is True
    assert summary["no_api_calls"] is True
    assert manifest["method_name"].endswith("targeted_retry_v1")


def test_planned_calls_respect_max_cap() -> None:
    _run(
        "--readiness-dir",
        str(READINESS_DIR),
        "--case-file",
        str(CASE_FILE),
        "--stage-name",
        "capfail_test",
        "--max-new-cohere-calls",
        "1",
        "--reuse-external-l1",
        "--dry-run-only",
    )
    out = _latest_dir("external_l1_capfail_test_integrated_checkpoint_dry_run")
    preflight = json.loads((out / "preflight_status.json").read_text(encoding="utf-8"))
    assert preflight["planned_new_cohere_calls"] >= 2
    assert preflight["planned_calls_ok"] is False


def test_external_reuse_paths_required_when_flag_set() -> None:
    _run(
        "--readiness-dir",
        str(READINESS_DIR),
        "--case-file",
        str(CASE_FILE),
        "--stage-name",
        "reusepath_test",
        "--max-new-cohere-calls",
        "50",
        "--reuse-external-l1",
        "--dry-run-only",
    )
    out = _latest_dir("external_l1_reusepath_test_integrated_checkpoint_dry_run")
    preflight = json.loads((out / "preflight_status.json").read_text(encoding="utf-8"))
    assert preflight["external_l1_paths_exist"] is True
    assert preflight["missing_external_l1_paths"] == []


def test_results_and_summary_schema_stable() -> None:
    _run(
        "--readiness-dir",
        str(READINESS_DIR),
        "--case-file",
        str(CASE_FILE),
        "--stage-name",
        "schema_test",
        "--max-new-cohere-calls",
        "50",
        "--reuse-external-l1",
        "--dry-run-only",
    )
    out = _latest_dir("external_l1_schema_test_integrated_checkpoint_dry_run")
    rows = list(csv.DictReader((out / "stage_checkpoint_results.csv").open(encoding="utf-8")))
    assert rows
    assert {
        "case_id",
        "external_l1_prediction",
        "baseline_pal_prediction",
        "integrated_prediction",
        "integrated_action",
        "cohere_call_made",
    }.issubset(rows[0].keys())
    summary = json.loads((out / "stage_checkpoint_summary.json").read_text(encoding="utf-8"))
    assert {
        "case_count",
        "actual_new_cohere_calls",
        "external_l1_correct_count",
        "integrated_correct_count",
        "paired_external_l1_only",
        "paired_integrated_only",
    }.issubset(summary.keys())

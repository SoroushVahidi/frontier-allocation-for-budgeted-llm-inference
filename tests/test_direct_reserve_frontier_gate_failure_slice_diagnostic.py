from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "run_direct_reserve_frontier_gate_failure_slice_diagnostic.py"


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _source_fixture(root: Path) -> tuple[Path, Path]:
    source = root / "source"
    diag = root / "diag"
    _write_csv(diag / "paired_summary.csv", ["scope", "matched_examples"], [["overall", 2]])
    (diag / "manifest.json").write_text("{}", encoding="utf-8")
    base = {
        "provider": "cohere",
        "model": "command-r-plus-08-2024",
        "dataset": "openai/gsm8k",
        "seed": 11,
        "budget": 4,
        "status": "scored",
        "scored": 1,
    }
    _write_jsonl(
        source / "per_example_records.jsonl",
        [
            {**base, "method": "external_l1_max", "example_id": "ex1", "exact_match": 1, "gold_answer": "10", "final_answer_raw": "10"},
            {**base, "method": "strict_f3", "example_id": "ex1", "exact_match": 0, "gold_answer": "10", "final_answer_raw": "9"},
            {**base, "method": "external_l1_max", "example_id": "ex2", "exact_match": 0, "gold_answer": "20", "final_answer_raw": "7"},
            {**base, "method": "strict_f3", "example_id": "ex2", "exact_match": 1, "gold_answer": "20", "final_answer_raw": "20"},
        ],
    )
    return source, diag


def test_fails_clearly_if_required_source_artifacts_missing(tmp_path: Path) -> None:
    out_root = tmp_path / "out"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-dir",
            str(tmp_path / "missing_source"),
            "--diagnostic-dir",
            str(tmp_path / "missing_diag"),
            "--output-root",
            str(out_root),
            "--timestamp",
            "MISSING",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "Missing required source artifacts" in proc.stderr
    manifest = json.loads((out_root / "direct_reserve_frontier_gate_failure_slice_MISSING" / "manifest.json").read_text())
    assert manifest["status"] == "missing_required_source_artifacts"
    assert manifest["missing_files"]


def test_summary_metrics_are_consistent_with_per_case_rows(tmp_path: Path) -> None:
    source, diag = _source_fixture(tmp_path)
    out_root = tmp_path / "out"
    subprocess.check_call(
        [
            sys.executable,
            str(SCRIPT),
            "--source-dir",
            str(source),
            "--diagnostic-dir",
            str(diag),
            "--output-root",
            str(out_root),
            "--timestamp",
            "CONSISTENT",
            "--skip-status-doc",
        ],
        cwd=REPO,
    )
    out = out_root / "direct_reserve_frontier_gate_failure_slice_CONSISTENT"
    rows = list(csv.DictReader((out / "per_case_results.csv").open("r", encoding="utf-8")))
    summary = list(csv.DictReader((out / "summary.csv").open("r", encoding="utf-8")))[0]
    assert int(summary["matched_examples"]) == len(rows)
    assert float(summary["external_l1_max_accuracy"]) == sum(int(r["external_l1_max_correct"]) for r in rows) / len(rows)
    assert float(summary["direct_reserve_frontier_gate_v1_accuracy"]) == sum(
        int(r["direct_reserve_frontier_gate_correct"]) for r in rows
    ) / len(rows)
    assert int(summary["total_overrides"]) == sum(int(r["frontier_override_triggered"]) for r in rows)
    assert summary["diagnostic_type"] == "diagnostic_limited_prediction_level"


def test_no_real_api_calls_are_made_unless_flag_is_passed(tmp_path: Path) -> None:
    source, diag = _source_fixture(tmp_path)
    out_root = tmp_path / "out"
    env = dict(os.environ)
    env["COHERE_API_KEY"] = "should-not-be-needed"
    subprocess.check_call(
        [
            sys.executable,
            str(SCRIPT),
            "--source-dir",
            str(source),
            "--diagnostic-dir",
            str(diag),
            "--output-root",
            str(out_root),
            "--timestamp",
            "OFFLINE",
            "--skip-status-doc",
        ],
        cwd=REPO,
        env=env,
    )
    manifest = json.loads((out_root / "direct_reserve_frontier_gate_failure_slice_OFFLINE" / "manifest.json").read_text())
    assert manifest["real_api_allowed"] is False
    assert manifest["real_api_used"] is False

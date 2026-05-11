from __future__ import annotations

import ast
import csv
import json
import subprocess
import sys
from pathlib import Path

from scripts import audit_latest_failure_recovery_coverage as auditor


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "audit_latest_failure_recovery_coverage.py"


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row.keys()}))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _failure_rows() -> list[dict[str, object]]:
    return [
        {
            "case_id": "openai_gsm8k_1",
            "method_id": "method_a",
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "family_a",
            "gold_answer": "10",
            "selected_answer": "9",
        },
        {
            "case_id": "openai_gsm8k_1",
            "method_id": "method_b",
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "family_a",
            "gold_answer": "10",
            "selected_answer": "9",
        },
        {
            "case_id": "openai_gsm8k_2",
            "method_id": "method_a",
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "family_b",
            "gold_answer": "20",
            "selected_answer": "19",
        },
        {
            "case_id": "openai_gsm8k_3",
            "method_id": "method_a",
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "family_b",
            "gold_answer": "30",
            "selected_answer": "29",
        },
    ]


def _gold_absent_rows() -> list[dict[str, object]]:
    return [
        {"case_id": "openai_gsm8k_1", "gold": "10"},
        {"case_id": "openai_gsm8k_3", "gold": "30"},
    ]


def _artifact_rows() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    early = [
        {
            "case_id": "openai_gsm8k_1",
            "method": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
            "exact_match": 1,
            "prediction": "10",
            "gold_answer": "10",
            "status": "scored",
        },
        {
            "case_id": "openai_gsm8k_2",
            "method": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
            "exact_match": 0,
            "prediction": "18",
            "gold_answer": "20",
            "status": "scored",
        },
        {
            "case_id": "openai_gsm8k_3",
            "method": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
            "prediction": "",
            "gold_answer": "",
            "status": "scored",
        },
    ]
    later = [
        {
            "case_id": "openai_gsm8k_1",
            "method": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
            "exact_match": 0,
            "prediction": "9",
            "gold_answer": "10",
            "status": "scored",
        },
        {
            "case_id": "openai_gsm8k_2",
            "method": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
            "exact_match": 1,
            "prediction": "20",
            "gold_answer": "20",
            "status": "scored",
        },
        {
            "case_id": "openai_gsm8k_3",
            "method": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
            "status": "scored",
        },
        {
            "case_id": "openai_gsm8k_1",
            "method": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_uncertainty_retry_v1",
            "exact_match": 1,
            "prediction": "10",
            "gold_answer": "10",
            "status": "scored",
        },
    ]
    return early, later


def _run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_audit_counts_and_deduplication(tmp_path: Path) -> None:
    failure_csv = tmp_path / "failure.csv"
    gold_csv = tmp_path / "gold.csv"
    outputs_root = tmp_path / "outputs"
    _write_csv(failure_csv, _failure_rows())
    _write_csv(gold_csv, _gold_absent_rows())
    early, later = _artifact_rows()
    _write_csv(outputs_root / "20260510T000000Z" / "per_case_results.csv", early)
    _write_csv(outputs_root / "20260511T000000Z" / "per_case_results.csv", later)

    output_dir = tmp_path / "audit"
    result = _run_script(
        [
            "--failure-csv",
            str(failure_csv),
            "--gold-absent-csv",
            str(gold_csv),
            "--outputs-root",
            str(outputs_root),
            "--output-dir",
            str(output_dir),
            "--method",
            "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
            "--method",
            "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_uncertainty_retry_v1",
        ]
    )
    assert result.returncode == 0, result.stderr

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    pal = next(row for row in summary["coverage_by_method"] if row["method"].endswith("_pal"))
    ur = next(row for row in summary["coverage_by_method"] if row["method"].endswith("uncertainty_retry_v1"))

    assert summary["unique_failure_ids"] == 3
    assert summary["gold_absent_ids"] == 2
    assert pal["covered_cases"] == 3
    assert pal["resolved_cases"] == 1
    assert pal["still_fails_cases"] == 1
    assert pal["unknown_cases"] == 1
    assert pal["not_covered_cases"] == 0
    assert pal["gold_absent_covered"] == 2
    assert ur["covered_cases"] == 1
    assert ur["resolved_cases"] == 1
    assert ur["not_covered_cases"] == 2


def test_unknown_correctness_and_report_written(tmp_path: Path) -> None:
    failure_csv = tmp_path / "failure.csv"
    gold_csv = tmp_path / "gold.csv"
    outputs_root = tmp_path / "outputs"
    _write_csv(failure_csv, _failure_rows())
    _write_csv(gold_csv, _gold_absent_rows())
    _write_jsonl(
        outputs_root / "20260510T000000Z" / "per_example_records.jsonl",
        [
            {
                "case_id": "openai_gsm8k_3",
                "method": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
                "status": "scored",
                "prediction": "",
                "gold_answer": "",
            }
        ],
    )

    output_dir = tmp_path / "audit"
    result = _run_script(
        [
            "--failure-csv",
            str(failure_csv),
            "--gold-absent-csv",
            str(gold_csv),
            "--outputs-root",
            str(outputs_root),
            "--output-dir",
            str(output_dir),
            "--method",
            "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
        ]
    )
    assert result.returncode == 0, result.stderr

    details = [row for row in csv.DictReader((output_dir / "case_coverage_details.csv").open(encoding="utf-8"))]
    row = next(r for r in details if r["case_id"] == "openai_gsm8k_3")
    report = (output_dir / "recovery_coverage_report.md").read_text(encoding="utf-8").lower()

    assert row["coverage_status"] == "unknown"
    assert (output_dir / "recovery_coverage_report.md").is_file()
    assert "superiority" not in report
    assert "outperform" not in report


def test_invalidated_diverse_anchor_is_not_counted(tmp_path: Path) -> None:
    failure_csv = tmp_path / "failure.csv"
    gold_csv = tmp_path / "gold.csv"
    outputs_root = tmp_path / "outputs"
    _write_csv(failure_csv, _failure_rows())
    _write_csv(gold_csv, _gold_absent_rows())
    _write_csv(
        outputs_root / "20260511T000000Z" / "per_case_results.csv",
        [
            {
                "case_id": "openai_gsm8k_1",
                "method": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor",
                "exact_match": 1,
                "prediction": "10",
                "gold_answer": "10",
                "valid_for_selected_failure_case": 0,
                "status": "invalidated_after_execution",
            }
        ],
    )

    output_dir = tmp_path / "audit"
    result = _run_script(
        [
            "--failure-csv",
            str(failure_csv),
            "--gold-absent-csv",
            str(gold_csv),
            "--outputs-root",
            str(outputs_root),
            "--output-dir",
            str(output_dir),
            "--method",
            "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor",
        ]
    )
    assert result.returncode == 0, result.stderr

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    report = (output_dir / "recovery_coverage_report.md").read_text(encoding="utf-8").lower()

    assert summary["coverage_by_method"][0]["covered_cases"] == 0
    assert summary["coverage_by_method"][0]["not_covered_cases"] == 3
    assert "invalidated recovery artifacts" in report
    assert "diverse_anchor" in report


def test_dry_run_does_not_write_outputs(tmp_path: Path) -> None:
    failure_csv = tmp_path / "failure.csv"
    gold_csv = tmp_path / "gold.csv"
    outputs_root = tmp_path / "outputs"
    _write_csv(failure_csv, _failure_rows())
    _write_csv(gold_csv, _gold_absent_rows())
    _write_csv(
        outputs_root / "20260510T000000Z" / "per_case_results.csv",
        [
            {
                "case_id": "openai_gsm8k_1",
                "method": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
                "exact_match": 1,
            }
        ],
    )

    output_dir = tmp_path / "audit"
    result = _run_script(
        [
            "--failure-csv",
            str(failure_csv),
            "--gold-absent-csv",
            str(gold_csv),
            "--outputs-root",
            str(outputs_root),
            "--output-dir",
            str(output_dir),
            "--dry-run",
        ]
    )
    assert result.returncode == 0, result.stderr
    assert not output_dir.exists()
    assert "unique_failure_ids" in result.stdout


def test_missing_failure_csv_fails_clearly(tmp_path: Path) -> None:
    result = _run_script(["--failure-csv", str(tmp_path / "missing.csv"), "--outputs-root", str(tmp_path / "outputs")])
    assert result.returncode != 0
    assert "Missing failure corpus CSV" in result.stderr


def test_script_has_no_api_client_imports() -> None:
    source_path = Path(auditor.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])

    forbidden = {"openai", "cohere", "anthropic", "requests", "google"}
    assert imported_modules.isdisjoint(forbidden)

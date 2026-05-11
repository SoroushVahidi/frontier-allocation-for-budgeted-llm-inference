from __future__ import annotations

import ast
import csv
import json
import subprocess
import sys
from pathlib import Path

from scripts import build_pal_unresolved_pattern_taxonomy as builder


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_pal_unresolved_pattern_taxonomy.py"


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _failure_rows() -> list[dict[str, object]]:
    return [
        {
            "case_id": "a",
            "method_id": builder.DEFAULT_METHOD,
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "money_family",
            "problem_text": "Money question A",
            "gold_answer": "10",
            "selected_answer": "9",
            "artifact_source": "outputs/a.jsonl",
            "selected_source": "outputs/a.jsonl",
            "notes": "pal row",
        },
        {
            "case_id": "b",
            "method_id": builder.DEFAULT_METHOD,
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "ratio_family",
            "problem_text": "Ratio question B",
            "gold_answer": "20",
            "selected_answer": "19",
            "artifact_source": "outputs/b.jsonl",
            "selected_source": "outputs/b.jsonl",
            "notes": "pal row",
        },
        {
            "case_id": "c",
            "method_id": builder.DEFAULT_METHOD,
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "multi_step_family",
            "problem_text": "Multi-step question C",
            "gold_answer": "30",
            "selected_answer": "29",
            "artifact_source": "outputs/c.jsonl",
            "selected_source": "outputs/c.jsonl",
            "notes": "pal row",
        },
        {
            "case_id": "d",
            "method_id": builder.DEFAULT_METHOD,
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "unit_family",
            "problem_text": "Unit question D",
            "gold_answer": "40",
            "selected_answer": "",
            "artifact_source": "outputs/d.jsonl",
            "selected_source": "outputs/d.jsonl",
            "notes": "pal row",
        },
    ]


def _gold_absent_rows() -> list[dict[str, object]]:
    return [
        {
            "case_id": "a",
            "question_type": "money/cost/revenue",
            "error_type": "premature intermediate answer",
            "gold": "10",
            "predicted": "9",
            "abs_error": "1",
            "rel_error": "0.1",
            "distance_bucket": "near (<10%)",
            "num_candidate_groups": 0,
            "diversity_bucket": "low (1 group)",
            "external_contrast": "Both wrong",
            "notes": "premature stop",
        },
        {
            "case_id": "b",
            "question_type": "ratio/proportion/percentage",
            "error_type": "unknown",
            "gold": "20",
            "predicted": "19",
            "abs_error": "1",
            "rel_error": "0.05",
            "distance_bucket": "near (<10%)",
            "num_candidate_groups": 2,
            "diversity_bucket": "medium (2-3 groups)",
            "external_contrast": "unknown",
            "notes": "metadata only",
        },
        {
            "case_id": "c",
            "question_type": "multi-step arithmetic",
            "error_type": "counting/grouping off-by-factor (factor)",
            "gold": "30",
            "predicted": "15",
            "abs_error": "15",
            "rel_error": "0.5",
            "distance_bucket": "far (>50%)",
            "num_candidate_groups": 1,
            "diversity_bucket": "low (1 group)",
            "external_contrast": "Both wrong",
            "notes": "factor error",
        },
        {
            "case_id": "d",
            "question_type": "unit conversion",
            "error_type": "structured extraction failure",
            "gold": "40",
            "predicted": "",
            "abs_error": "",
            "rel_error": "",
            "distance_bucket": "unknown",
            "num_candidate_groups": 0,
            "diversity_bucket": "low (1 group)",
            "external_contrast": "unknown",
            "notes": "extraction failure",
        },
    ]


def _anchor_rows() -> list[dict[str, object]]:
    return [
        {
            "case_id": "a",
            "anchor_matches_l1_max": 1,
            "external_l1_exact": 1,
            "gold_recovered": 1,
            "diversity_increased": 1,
        },
        {
            "case_id": "b",
            "anchor_matches_l1_max": 0,
            "external_l1_exact": 0,
            "gold_recovered": 0,
            "diversity_increased": 0,
        },
        {
            "case_id": "c",
            "anchor_matches_l1_max": 0,
            "external_l1_exact": 0,
            "gold_recovered": 0,
            "diversity_increased": 0,
        },
        {
            "case_id": "d",
            "anchor_matches_l1_max": 0,
            "external_l1_exact": 0,
            "gold_recovered": 0,
            "diversity_increased": 0,
        },
    ]


def _coverage_rows() -> list[dict[str, object]]:
    return [
        {
            "case_id": "a",
            "method": builder.DEFAULT_METHOD,
            "coverage_status": "still_fails",
            "selected_source_path": "outputs/a.jsonl",
            "selected_correctness_status": "still_fails",
            "selected_correctness_field": "exact_match",
        },
        {
            "case_id": "a",
            "method": builder.DEFAULT_METHOD,
            "coverage_status": "still_fails",
            "selected_source_path": "outputs/a_duplicate.jsonl",
            "selected_correctness_status": "still_fails",
            "selected_correctness_field": "exact_match",
        },
        {
            "case_id": "b",
            "method": builder.DEFAULT_METHOD,
            "coverage_status": "still_fails",
            "selected_source_path": "outputs/b.jsonl",
            "selected_correctness_status": "still_fails",
            "selected_correctness_field": "exact_match",
        },
        {
            "case_id": "c",
            "method": builder.DEFAULT_METHOD,
            "coverage_status": "still_fails",
            "selected_source_path": "outputs/c.jsonl",
            "selected_correctness_status": "still_fails",
            "selected_correctness_field": "exact_match",
        },
        {
            "case_id": "d",
            "method": builder.DEFAULT_METHOD,
            "coverage_status": "still_fails",
            "selected_source_path": "outputs/d.jsonl",
            "selected_correctness_status": "still_fails",
            "selected_correctness_field": "exact_match",
        },
    ]


def _run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_taxonomy_counts_and_deduplication(tmp_path: Path) -> None:
    failure_csv = tmp_path / "failure.csv"
    gold_csv = tmp_path / "gold.csv"
    anchor_csv = tmp_path / "anchor.csv"
    coverage_csv = tmp_path / "coverage.csv"
    output_dir = tmp_path / "taxonomy"

    _write_csv(failure_csv, _failure_rows())
    _write_csv(gold_csv, _gold_absent_rows())
    _write_csv(anchor_csv, _anchor_rows())
    _write_csv(coverage_csv, _coverage_rows())

    summary = builder.run(
        [
            "--failure-csv",
            str(failure_csv),
            "--gold-absent-csv",
            str(gold_csv),
            "--coverage-details-csv",
            str(coverage_csv),
            "--anchor-effect-csv",
            str(anchor_csv),
            "--output-dir",
            str(output_dir),
            "--method",
            builder.DEFAULT_METHOD,
        ]
    )

    assert summary["unresolved_cases_count"] == 4
    assert summary["unresolved_unique_case_ids"] == 4
    assert summary["pattern_counts"]["gold_absent_from_candidate_pool"] == 4
    assert summary["pattern_counts"]["frontier_collapse_low_diversity"] == 3
    assert summary["pattern_counts"]["wrong_supported_consensus"] == 2
    assert summary["pattern_counts"]["direct_l1_anchor_potential"] == 1
    assert summary["pattern_counts"]["premature_intermediate_answer"] == 1
    assert summary["pattern_counts"]["counting_grouping_off_by_factor"] == 1
    assert summary["pattern_counts"]["structured_extraction_failure"] == 1
    assert summary["pattern_counts"]["unknown_or_insufficient_metadata"] == 1
    assert summary["domain_counts"]["domain_money_cost_revenue"] == 1
    assert summary["domain_counts"]["domain_ratio_proportion_percentage"] == 1
    assert summary["domain_counts"]["domain_multi_step_arithmetic"] == 1
    assert summary["domain_counts"]["domain_unit_conversion"] == 1

    case_rows = list(csv.DictReader((output_dir / "pal_unresolved_cases.csv").open(encoding="utf-8")))
    assert {row["case_id"] for row in case_rows} == {"a", "b", "c", "d"}
    examples = list(csv.DictReader((output_dir / "pattern_case_examples.csv").open(encoding="utf-8")))
    assert examples[0]["case_id"] == "a"
    report = (output_dir / "pal_unresolved_pattern_taxonomy_report.md").read_text(encoding="utf-8").lower()
    assert "## facts" in report
    assert "## heuristic labels" in report
    assert "## proposed fixes" in report


def test_dry_run_does_not_write_outputs(tmp_path: Path) -> None:
    failure_csv = tmp_path / "failure.csv"
    gold_csv = tmp_path / "gold.csv"
    anchor_csv = tmp_path / "anchor.csv"
    coverage_csv = tmp_path / "coverage.csv"
    output_dir = tmp_path / "dryrun"

    _write_csv(failure_csv, _failure_rows())
    _write_csv(gold_csv, _gold_absent_rows())
    _write_csv(anchor_csv, _anchor_rows())
    _write_csv(coverage_csv, _coverage_rows())

    result = _run_script(
        [
            "--failure-csv",
            str(failure_csv),
            "--gold-absent-csv",
            str(gold_csv),
            "--coverage-details-csv",
            str(coverage_csv),
            "--anchor-effect-csv",
            str(anchor_csv),
            "--output-dir",
            str(output_dir),
            "--dry-run",
        ]
    )
    assert result.returncode == 0, result.stderr
    assert not output_dir.exists()
    assert '"unresolved_cases_count": 4' in result.stdout


def test_missing_input_fails_clearly(tmp_path: Path) -> None:
    result = _run_script(
        [
            "--failure-csv",
            str(tmp_path / "missing_failure.csv"),
            "--gold-absent-csv",
            str(tmp_path / "gold.csv"),
            "--coverage-details-csv",
            str(tmp_path / "coverage.csv"),
        ]
    )
    assert result.returncode != 0
    assert "Missing failure corpus CSV" in result.stderr


def test_report_separates_facts_heuristics_and_proposed_fixes(tmp_path: Path) -> None:
    failure_csv = tmp_path / "failure.csv"
    gold_csv = tmp_path / "gold.csv"
    anchor_csv = tmp_path / "anchor.csv"
    coverage_csv = tmp_path / "coverage.csv"
    output_dir = tmp_path / "taxonomy"

    _write_csv(failure_csv, _failure_rows())
    _write_csv(gold_csv, _gold_absent_rows())
    _write_csv(anchor_csv, _anchor_rows())
    _write_csv(coverage_csv, _coverage_rows())

    summary = builder.run(
        [
            "--failure-csv",
            str(failure_csv),
            "--gold-absent-csv",
            str(gold_csv),
            "--coverage-details-csv",
            str(coverage_csv),
            "--anchor-effect-csv",
            str(anchor_csv),
            "--output-dir",
            str(output_dir),
        ]
    )

    report = (output_dir / "pal_unresolved_pattern_taxonomy_report.md").read_text(encoding="utf-8").lower()
    assert "facts" in report
    assert "heuristic labels" in report
    assert "proposed fixes" in report
    assert "direct l1 anchor" in report
    assert summary["recommended_next_fix"].lower().startswith("test a stronger direct l1 anchor")


def test_script_has_no_api_client_imports() -> None:
    source = Path(builder.__file__).read_text(encoding="utf-8")
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

from __future__ import annotations

import ast
import csv
import json
import subprocess
import sys
from pathlib import Path

from scripts import prepare_direct_l1_seed_strengthening_preflight as preflight


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "prepare_direct_l1_seed_strengthening_preflight.py"


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _full_failure_rows() -> list[dict[str, object]]:
    return [
        {
            "case_id": "openai_gsm8k_168",
            "method_id": preflight.DEFAULT_METHOD,
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "money_family",
            "problem_text": "Money question 168",
            "gold_answer": "35",
            "selected_answer": "40",
            "artifact_source": "outputs/a.jsonl",
            "selected_source": "outputs/a.jsonl",
        },
        {
            "case_id": "openai_gsm8k_190",
            "method_id": preflight.DEFAULT_METHOD,
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "ratio_family",
            "problem_text": "Ratio question 190",
            "gold_answer": "420",
            "selected_answer": "720",
            "artifact_source": "outputs/b.jsonl",
            "selected_source": "outputs/b.jsonl",
        },
        {
            "case_id": "openai_gsm8k_999",
            "method_id": preflight.DEFAULT_METHOD,
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "multi_step_family",
            "problem_text": "Arithmetic question 999",
            "gold_answer": "18",
            "selected_answer": "12",
            "artifact_source": "outputs/c.jsonl",
            "selected_source": "outputs/c.jsonl",
        },
        {
            "case_id": "openai_gsm8k_777",
            "method_id": preflight.DEFAULT_METHOD,
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "unit_family",
            "problem_text": "Unit question 777",
            "gold_answer": "12",
            "selected_answer": "8",
            "artifact_source": "outputs/d.jsonl",
            "selected_source": "outputs/d.jsonl",
        },
        {
            "case_id": "openai_gsm8k_888",
            "method_id": preflight.DEFAULT_METHOD,
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "temporal_family",
            "problem_text": "Temporal question 888",
            "gold_answer": "9",
            "selected_answer": "5",
            "artifact_source": "outputs/e.jsonl",
            "selected_source": "outputs/e.jsonl",
        },
    ]


def _gold_absent_rows() -> list[dict[str, object]]:
    return [
        {
            "case_id": "openai_gsm8k_168",
            "question_type": "money/cost/revenue",
            "error_type": "premature intermediate answer",
            "gold": "35",
            "predicted": "40",
            "abs_error": "5",
            "rel_error": "0.142857",
            "distance_bucket": "near (<10%)",
            "num_candidate_groups": 1,
            "diversity_bucket": "low (1 group)",
            "external_contrast": "Both wrong",
            "notes": "anchor case 168",
        },
        {
            "case_id": "openai_gsm8k_190",
            "question_type": "ratio/proportion/percentage",
            "error_type": "unknown",
            "gold": "420",
            "predicted": "720",
            "abs_error": "300",
            "rel_error": "0.714286",
            "distance_bucket": "far (>50%)",
            "num_candidate_groups": 2,
            "diversity_bucket": "medium (2-3 groups)",
            "external_contrast": "Both wrong",
            "notes": "anchor case 190",
        },
        {
            "case_id": "openai_gsm8k_999",
            "question_type": "multi-step arithmetic",
            "error_type": "counting/grouping off-by-factor (factor)",
            "gold": "18",
            "predicted": "12",
            "abs_error": "6",
            "rel_error": "0.333333",
            "distance_bucket": "near (<10%)",
            "num_candidate_groups": 1,
            "diversity_bucket": "low (1 group)",
            "external_contrast": "Both wrong",
            "notes": "anchor case 999",
        },
        {
            "case_id": "openai_gsm8k_777",
            "question_type": "unit conversion",
            "error_type": "structured extraction failure",
            "gold": "12",
            "predicted": "8",
            "abs_error": "4",
            "rel_error": "0.333333",
            "distance_bucket": "near (<10%)",
            "num_candidate_groups": 0,
            "diversity_bucket": "low (1 group)",
            "external_contrast": "Both wrong",
            "notes": "anchor case 777",
        },
        {
            "case_id": "openai_gsm8k_888",
            "question_type": "temporal/calendar",
            "error_type": "unknown",
            "gold": "9",
            "predicted": "5",
            "abs_error": "4",
            "rel_error": "0.444444",
            "distance_bucket": "near (<10%)",
            "num_candidate_groups": 0,
            "diversity_bucket": "low (1 group)",
            "external_contrast": "Both wrong",
            "notes": "non-anchor case",
        },
    ]


def _anchor_effect_rows() -> list[dict[str, object]]:
    return [
        {
            "case_id": "openai_gsm8k_168",
            "anchor_matches_l1_max": 1,
            "external_l1_exact": 1,
            "gold_recovered": 1,
            "diversity_increased": 1,
        },
        {
            "case_id": "openai_gsm8k_190",
            "anchor_matches_l1_max": 1,
            "external_l1_exact": 1,
            "gold_recovered": 0,
            "diversity_increased": 1,
        },
        {
            "case_id": "openai_gsm8k_999",
            "anchor_matches_l1_max": 0,
            "external_l1_exact": 1,
            "gold_recovered": 0,
            "diversity_increased": 1,
        },
        {
            "case_id": "openai_gsm8k_777",
            "anchor_matches_l1_max": 0,
            "external_l1_exact": 1,
            "gold_recovered": 0,
            "diversity_increased": 1,
        },
    ]


def _coverage_rows() -> list[dict[str, object]]:
    return [
        {
            "case_id": "openai_gsm8k_168",
            "method": preflight.DEFAULT_METHOD,
            "coverage_status": "still_fails",
            "selected_source_path": "outputs/a.jsonl",
            "selected_correctness_status": "still_fails",
            "selected_correctness_field": "exact_match",
        },
        {
            "case_id": "openai_gsm8k_190",
            "method": preflight.DEFAULT_METHOD,
            "coverage_status": "still_fails",
            "selected_source_path": "outputs/b.jsonl",
            "selected_correctness_status": "still_fails",
            "selected_correctness_field": "exact_match",
        },
        {
            "case_id": "openai_gsm8k_999",
            "method": preflight.DEFAULT_METHOD,
            "coverage_status": "still_fails",
            "selected_source_path": "outputs/c.jsonl",
            "selected_correctness_status": "still_fails",
            "selected_correctness_field": "exact_match",
        },
        {
            "case_id": "openai_gsm8k_777",
            "method": preflight.DEFAULT_METHOD,
            "coverage_status": "still_fails",
            "selected_source_path": "outputs/d.jsonl",
            "selected_correctness_status": "still_fails",
            "selected_correctness_field": "exact_match",
        },
        {
            "case_id": "openai_gsm8k_888",
            "method": preflight.DEFAULT_METHOD,
            "coverage_status": "still_fails",
            "selected_source_path": "outputs/e.jsonl",
            "selected_correctness_status": "still_fails",
            "selected_correctness_field": "exact_match",
        },
    ]


def _exact_replay_jsonl(ids: list[str]) -> str:
    return "\n".join(json.dumps({"example_id": cid}) for cid in ids) + "\n"


def test_preflight_counts_selection_and_overlap(tmp_path: Path) -> None:
    failure_csv = tmp_path / "failure.csv"
    gold_csv = tmp_path / "gold.csv"
    anchor_csv = tmp_path / "anchor.csv"
    coverage_csv = tmp_path / "coverage.csv"
    exact30 = tmp_path / "exact30.jsonl"
    exact50 = tmp_path / "exact50.jsonl"
    output_dir = tmp_path / "preflight"

    _write_csv(failure_csv, _full_failure_rows())
    _write_csv(gold_csv, _gold_absent_rows())
    _write_csv(anchor_csv, _anchor_effect_rows())
    _write_csv(coverage_csv, _coverage_rows())
    exact30.write_text(_exact_replay_jsonl(["openai_gsm8k_168", "openai_gsm8k_190", "openai_gsm8k_999"]), encoding="utf-8")
    exact50.write_text(_exact_replay_jsonl(["openai_gsm8k_168", "openai_gsm8k_777", "openai_gsm8k_999"]), encoding="utf-8")

    summary = preflight.run(
        [
            "--full-failure-csv",
            str(failure_csv),
            "--gold-absent-csv",
            str(gold_csv),
            "--anchor-effect-csv",
            str(anchor_csv),
            "--coverage-details-csv",
            str(coverage_csv),
            "--exact-replay-30-jsonl",
            str(exact30),
            "--exact-replay-50-jsonl",
            str(exact50),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert summary["anchor_potential_count"] == 4
    assert summary["strong_patch_effect_count"] == 2
    assert summary["domain_counts"] == {
        "domain_money_cost_revenue": 1,
        "domain_multi_step_arithmetic": 1,
        "domain_ratio_proportion_percentage": 1,
        "domain_unit_conversion": 1,
    }
    assert summary["selected_diagnostic_case_ids"] == [
        "openai_gsm8k_168",
        "openai_gsm8k_190",
        "openai_gsm8k_999",
        "openai_gsm8k_777",
    ]
    assert len(summary["missing_suggested_case_ids"]) == 13
    assert summary["exact_replay_overlap"]["exact_replay_30_count"] == 3
    assert summary["exact_replay_overlap"]["exact_replay_50_count"] == 3
    assert summary["exact_replay_overlap"]["selected_15_overlap_30_count"] == 3
    assert summary["exact_replay_overlap"]["selected_15_overlap_50_count"] == 3

    assert (output_dir / "summary.json").is_file()
    assert (output_dir / "direct_l1_anchor_potential_cases.csv").is_file()
    assert (output_dir / "direct_l1_seed_diagnostic_15case.csv").is_file()
    assert (output_dir / "direct_l1_seed_strengthening_preflight_report.md").is_file()

    anchor_rows = list(csv.DictReader((output_dir / "direct_l1_anchor_potential_cases.csv").open(encoding="utf-8")))
    diag_rows = list(csv.DictReader((output_dir / "direct_l1_seed_diagnostic_15case.csv").open(encoding="utf-8")))
    assert [row["case_id"] for row in anchor_rows] == [
        "openai_gsm8k_168",
        "openai_gsm8k_999",
        "openai_gsm8k_777",
        "openai_gsm8k_190",
    ]
    assert [row["case_id"] for row in diag_rows] == [
        "openai_gsm8k_168",
        "openai_gsm8k_190",
        "openai_gsm8k_999",
        "openai_gsm8k_777",
    ]
    report = (output_dir / "direct_l1_seed_strengthening_preflight_report.md").read_text(encoding="utf-8").lower()
    assert "observed facts" in report
    assert "current direct l1 anchor behavior" in report
    assert "recommended design" in report
    assert "direct answer plus independent arithmetic/unit self-check" in report
    assert preflight.PROPOSED_METHOD_ID in report


def test_dry_run_does_not_write_outputs(tmp_path: Path) -> None:
    failure_csv = tmp_path / "failure.csv"
    gold_csv = tmp_path / "gold.csv"
    anchor_csv = tmp_path / "anchor.csv"
    coverage_csv = tmp_path / "coverage.csv"
    exact30 = tmp_path / "exact30.jsonl"
    exact50 = tmp_path / "exact50.jsonl"
    output_dir = tmp_path / "dryrun"

    _write_csv(failure_csv, _full_failure_rows())
    _write_csv(gold_csv, _gold_absent_rows())
    _write_csv(anchor_csv, _anchor_effect_rows())
    _write_csv(coverage_csv, _coverage_rows())
    exact30.write_text(_exact_replay_jsonl(["openai_gsm8k_168"]), encoding="utf-8")
    exact50.write_text(_exact_replay_jsonl(["openai_gsm8k_777"]), encoding="utf-8")

    result = _run_script(
        [
            "--full-failure-csv",
            str(failure_csv),
            "--gold-absent-csv",
            str(gold_csv),
            "--anchor-effect-csv",
            str(anchor_csv),
            "--coverage-details-csv",
            str(coverage_csv),
            "--exact-replay-30-jsonl",
            str(exact30),
            "--exact-replay-50-jsonl",
            str(exact50),
            "--output-dir",
            str(output_dir),
            "--dry-run",
        ]
    )
    assert result.returncode == 0, result.stderr
    assert not output_dir.exists()
    assert '"anchor_potential_count": 4' in result.stdout


def test_missing_input_fails_clearly(tmp_path: Path) -> None:
    result = _run_script(
        [
            "--full-failure-csv",
            str(tmp_path / "missing_failure.csv"),
            "--gold-absent-csv",
            str(tmp_path / "gold.csv"),
            "--anchor-effect-csv",
            str(tmp_path / "anchor.csv"),
            "--coverage-details-csv",
            str(tmp_path / "coverage.csv"),
        ]
    )
    assert result.returncode != 0
    assert "Missing failure corpus CSV" in result.stderr


def test_script_has_no_api_client_imports() -> None:
    source = Path(preflight.__file__).read_text(encoding="utf-8")
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


def test_proposed_method_id_is_not_registered_in_controller_defaults() -> None:
    controller_source = (REPO_ROOT / "experiments" / "controllers.py").read_text(encoding="utf-8")
    assert preflight.PROPOSED_METHOD_ID not in controller_source

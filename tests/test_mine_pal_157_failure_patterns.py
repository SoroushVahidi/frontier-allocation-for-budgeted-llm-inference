from __future__ import annotations

import ast
import csv
import json
import subprocess
import sys
from pathlib import Path

from scripts import mine_pal_157_failure_patterns as miner


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "mine_pal_157_failure_patterns.py"


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_jsonl_ids(path: Path, ids: list[str]) -> None:
    path.write_text("\n".join(json.dumps({"example_id": case_id}) for case_id in ids) + "\n", encoding="utf-8")


def _run_script(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _failure_rows() -> list[dict[str, object]]:
    return [
        {
            "case_id": "a",
            "method_id": miner.DEFAULT_METHOD,
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "money_family",
            "problem_text": "A dinner check is $50 and a 20 percent tip is added before splitting the total.",
            "gold_answer": "35",
            "selected_answer": "40",
            "artifact_source": "outputs/a.jsonl",
            "selected_source": "outputs/a.jsonl",
        },
        {
            "case_id": "b",
            "method_id": miner.DEFAULT_METHOD,
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "ratio_family",
            "problem_text": "The ratio is 2:3 and the total is 100. Find the smaller share.",
            "gold_answer": "40",
            "selected_answer": "60",
            "artifact_source": "outputs/b.jsonl",
            "selected_source": "outputs/b.jsonl",
        },
        {
            "case_id": "c",
            "method_id": miner.DEFAULT_METHOD,
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "parse_format",
            "problem_text": "A car travels 60 miles per hour for 2 hours. How many miles does it travel?",
            "gold_answer": "120",
            "selected_answer": "",
            "artifact_source": "outputs/c.jsonl",
            "selected_source": "outputs/c.jsonl",
        },
        {
            "case_id": "d",
            "method_id": miner.DEFAULT_METHOD,
            "method_version": "v1",
            "evidence_completeness": "FULL",
            "failure_family": "temporal_family",
            "problem_text": "A person works 5 days every week for 4 weeks, then takes 3 days off.",
            "gold_answer": "17",
            "selected_answer": "20",
            "artifact_source": "outputs/d.jsonl",
            "selected_source": "outputs/d.jsonl",
        },
    ]


def _gold_rows() -> list[dict[str, object]]:
    return [
        {
            "case_id": "a",
            "question_type": "money/cost/revenue",
            "error_type": "premature intermediate answer",
            "gold": "35",
            "predicted": "40",
            "num_candidate_groups": 1,
            "diversity_bucket": "low (1 group)",
            "external_contrast": "Both wrong",
            "notes": "stopped at subtotal",
        },
        {
            "case_id": "b",
            "question_type": "ratio/proportion/percentage",
            "error_type": "unknown",
            "gold": "40",
            "predicted": "60",
            "num_candidate_groups": 2,
            "diversity_bucket": "medium (2-3 groups)",
            "external_contrast": "Both wrong",
            "notes": "ratio base confusion",
        },
        {
            "case_id": "c",
            "question_type": "rate/speed/work",
            "error_type": "structured extraction failure",
            "gold": "120",
            "predicted": "",
            "num_candidate_groups": 0,
            "diversity_bucket": "low (1 group)",
            "external_contrast": "unknown",
            "notes": "parse issue",
        },
        {
            "case_id": "d",
            "question_type": "temporal/calendar",
            "error_type": "unknown",
            "gold": "17",
            "predicted": "20",
            "num_candidate_groups": 1,
            "diversity_bucket": "low (1 group)",
            "external_contrast": "Both wrong",
            "notes": "missed remaining days",
        },
    ]


def _anchor_rows() -> list[dict[str, object]]:
    return [
        {"case_id": "a", "anchor_matches_l1_max": 1, "external_l1_exact": 1, "gold_recovered": 0, "diversity_increased": 1},
        {"case_id": "b", "anchor_matches_l1_max": 0, "external_l1_exact": 1, "gold_recovered": 0, "diversity_increased": 1},
        {"case_id": "c", "anchor_matches_l1_max": 0, "external_l1_exact": 0, "gold_recovered": 0, "diversity_increased": 0},
        {"case_id": "d", "anchor_matches_l1_max": 0, "external_l1_exact": 0, "gold_recovered": 0, "diversity_increased": 0},
    ]


def _coverage_rows() -> list[dict[str, object]]:
    rows = []
    for case_id in ("a", "a", "b", "c", "d"):
        rows.append(
            {
                "case_id": case_id,
                "method": miner.DEFAULT_METHOD,
                "coverage_status": "still_fails",
                "selected_source_path": f"outputs/{case_id}.jsonl",
                "selected_correctness_status": "still_fails",
                "selected_correctness_field": "exact_match",
            }
        )
    return rows


def _common_args(tmp_path: Path) -> tuple[list[str], Path]:
    failure_csv = tmp_path / "failure.csv"
    gold_csv = tmp_path / "gold.csv"
    anchor_csv = tmp_path / "anchor.csv"
    coverage_csv = tmp_path / "coverage.csv"
    exact30 = tmp_path / "exact30.jsonl"
    exact50 = tmp_path / "exact50.jsonl"
    output_dir = tmp_path / "out"
    _write_csv(failure_csv, _failure_rows())
    _write_csv(gold_csv, _gold_rows())
    _write_csv(anchor_csv, _anchor_rows())
    _write_csv(coverage_csv, _coverage_rows())
    _write_jsonl_ids(exact30, ["a", "b"])
    _write_jsonl_ids(exact50, ["a", "b", "c"])
    return (
        [
            "--failure-csv",
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
        ],
        output_dir,
    )


def test_mines_pal_unresolved_cases_and_outputs(tmp_path: Path) -> None:
    args, output_dir = _common_args(tmp_path)
    summary = miner.run(args)

    assert summary["unresolved_cases_count"] == 4
    assert summary["unique_case_ids"] == 4
    assert summary["direct_l1_anchor_potential_count"] == 2
    assert summary["direct_l1_patch_effect_match_count"] == 1
    assert summary["wrong_supported_consensus_count"] == 3
    assert summary["best_scored_candidate_fix"] == "stronger_direct_l1_seed_with_independent_arithmetic_unit_self_check"
    assert summary["stronger_direct_l1_seed_still_recommended"] is True

    cases = list(csv.DictReader((output_dir / "pal_157_unresolved_cases.csv").open(encoding="utf-8")))
    by_id = {row["case_id"]: row for row in cases}
    assert "domain_money_cost_revenue" in by_id["a"]["pattern_tags"]
    assert "direct_l1_anchor_potential" in by_id["a"]["pattern_tags"]
    assert "direct_l1_patch_effect_match" in by_id["a"]["pattern_tags"]
    assert "premature_intermediate_answer" in by_id["a"]["mechanism_tags"]
    assert "ratio_base_confusion" in by_id["b"]["mechanism_tags"]
    assert "answer_extraction_or_parse_issue" in by_id["c"]["mechanism_tags"]
    assert "temporal_counting_confusion" in by_id["d"]["mechanism_tags"]

    assert (output_dir / "summary.json").is_file()
    assert (output_dir / "pattern_counts.csv").is_file()
    assert (output_dir / "pattern_by_domain_counts.csv").is_file()
    assert (output_dir / "mechanism_counts.csv").is_file()
    assert (output_dir / "actionable_slices.csv").is_file()
    assert (output_dir / "recommended_diagnostic_slices.csv").is_file()
    assert (output_dir / "case_examples_by_pattern.csv").is_file()
    assert (output_dir / "pal_157_failure_pattern_report.md").is_file()


def test_diagnostic_slices_are_deterministic(tmp_path: Path) -> None:
    args, output_dir = _common_args(tmp_path)
    miner.run(args)
    slices = list(csv.DictReader((output_dir / "recommended_diagnostic_slices.csv").open(encoding="utf-8")))
    direct_15 = [row["case_id"] for row in slices if row["slice_id"] == "direct_l1_strong_seed_15case"]
    wrong_15 = [row["case_id"] for row in slices if row["slice_id"] == "wrong_supported_consensus_15case"]
    assert direct_15 == ["a", "b"]
    assert wrong_15 == ["a", "b", "d"]
    assert all(row["reason"] for row in slices)


def test_report_separates_facts_heuristics_mechanisms_and_fixes(tmp_path: Path) -> None:
    args, output_dir = _common_args(tmp_path)
    miner.run(args)
    report = (output_dir / "pal_157_failure_pattern_report.md").read_text(encoding="utf-8").lower()
    assert "observed facts from artifacts" in report
    assert "heuristic pattern labels" in report
    assert "inferred likely failure mechanisms" in report
    assert "proposed targeted fixes" in report
    assert "no external-baseline claim" in report


def test_dry_run_does_not_write_outputs(tmp_path: Path) -> None:
    args, output_dir = _common_args(tmp_path)
    result = _run_script([*args, "--dry-run"])
    assert result.returncode == 0, result.stderr
    assert '"unresolved_cases_count": 4' in result.stdout
    assert not output_dir.exists()


def test_missing_input_fails_clearly(tmp_path: Path) -> None:
    result = _run_script(
        [
            "--failure-csv",
            str(tmp_path / "missing.csv"),
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
    source = Path(miner.__file__).read_text(encoding="utf-8")
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

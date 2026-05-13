from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import analyze_bftc_candidate_rebinding_selector_v1 as mod


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _write_casebook(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _make_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    bftc_dir = tmp_path / "bftc"
    exec_dir = tmp_path / "exec"
    casebook = tmp_path / "casebook.csv"
    doc_path = tmp_path / "analysis.md"

    _write_jsonl(
        bftc_dir / "candidate_rows.jsonl",
        [
            {
                "case_id": "case_1",
                "fa_numeric": 8.0,
                "gold_recovered": False,
                "candidate_pool": ["8", "12"],
                "baseline_answer": "8",
                "is_new_candidate": False,
                "matches_baseline": True,
            },
            {
                "case_id": "case_2",
                "fa_numeric": 5.0,
                "gold_recovered": False,
                "candidate_pool": ["5"],
                "baseline_answer": "5",
                "is_new_candidate": False,
                "matches_baseline": True,
            },
        ],
    )
    _write_jsonl(
        bftc_dir / "parsed_responses.jsonl",
        [
            {
                "case_id": "case_1",
                "target_identified": "target amount apples",
                "target_unit": "apples",
                "all_steps_consistent": True,
            },
            {
                "case_id": "case_2",
                "target_identified": "prank percentage",
                "target_unit": "percent",
                "all_steps_consistent": True,
            },
        ],
    )

    exec_raw_rows = [
        {
            "case_id": "case_1",
            "prompt_text": "QUESTION:\nHow many apples are needed?\n\nEXISTING CANDIDATES",
            "raw_response": json.dumps(
                {
                    "requested_target": "target amount apples",
                    "formula_variables": {
                        "target_amount_apples": {
                            "value": 10,
                            "description": "target amount apples",
                            "unit": "apples",
                        },
                        "other_count": {
                            "value": 12,
                            "description": "other count",
                            "unit": "apples",
                        },
                    },
                    "final_answer": 8,
                }
            ),
        },
        {
            "case_id": "case_2",
            "prompt_text": "QUESTION:\nWhat percentage is left?\n\nEXISTING CANDIDATES",
            "raw_response": json.dumps(
                {
                    "requested_target": "prank percentage",
                    "formula_variables": {
                        "total_sodas": {
                            "value": 12,
                            "description": "total sodas",
                            "unit": "sodas",
                        }
                    },
                    "final_answer": 6,
                }
            ),
        },
    ]
    _write_jsonl(exec_dir / "raw_responses.jsonl", exec_raw_rows)
    _write_jsonl(
        exec_dir / "parsed_responses.jsonl",
        [
            {
                "case_id": "case_1",
                "requested_target": "target amount apples",
                "fa_numeric": 8.0,
                "eval_ok": True,
                "eval_error_type": None,
                "solution_formula": "other_count - 2",
                "formula_matches_model_fa": False,
            },
            {
                "case_id": "case_2",
                "requested_target": "prank percentage",
                "fa_numeric": 6.0,
                "eval_ok": True,
                "eval_error_type": None,
                "solution_formula": "total_sodas / 2",
                "formula_matches_model_fa": True,
            },
        ],
    )
    _write_jsonl(
        exec_dir / "executable_candidate_rows.jsonl",
        [
            {
                "case_id": "case_1",
                "executable_final_answer": 12.0,
                "baseline_answer": "8",
                "candidate_pool": ["8", "12"],
                "gold_recovered_model_fa": False,
                "gold_recovered_executable_fa": False,
                "is_new_executable_candidate": False,
                "matches_baseline": False,
            },
            {
                "case_id": "case_2",
                "executable_final_answer": 6.0,
                "baseline_answer": "5",
                "candidate_pool": ["5", "6"],
                "gold_recovered_model_fa": False,
                "gold_recovered_executable_fa": False,
                "is_new_executable_candidate": True,
                "matches_baseline": False,
            },
        ],
    )
    _write_jsonl(
        exec_dir / "bftc_executable_case_error_analysis.jsonl",
        [
            {
                "case_id": "case_1",
                "primary_category": "wrong_variable_binding_in_formula",
                "failure_axis": "relation_construction",
                "prompt_gold_consistency": "consistent",
            },
            {
                "case_id": "case_2",
                "primary_category": "other",
                "failure_axis": "artifact_mismatch",
                "prompt_gold_consistency": "definite_mismatch",
            },
        ],
    )

    _write_casebook(
        casebook,
        [
            {
                "case_id": "case_1",
                "question_type": "counting",
                "gold": "10",
                "predicted": "",
                "error_type": "unknown",
                "abs_error": "",
                "rel_error": "",
                "distance_bucket": "unknown",
                "num_candidate_groups": "0",
                "diversity_bucket": "low",
                "external_contrast": "Both wrong",
                "notes": "",
            },
            {
                "case_id": "case_2",
                "question_type": "percentage",
                "gold": "99",
                "predicted": "",
                "error_type": "unknown",
                "abs_error": "",
                "rel_error": "",
                "distance_bucket": "unknown",
                "num_candidate_groups": "0",
                "diversity_bucket": "low",
                "external_contrast": "Both wrong",
                "notes": "",
            },
        ],
    )

    return bftc_dir, exec_dir, casebook, doc_path


def test_candidate_set_construction_and_numeric_deduplication(tmp_path: Path):
    bftc_dir, exec_dir, _, _ = _make_fixture(tmp_path)
    rows = mod.build_candidate_rows(
        bftc_only_dir=bftc_dir,
        exec_dir=exec_dir,
        exec_postmortem=mod.load_exec_postmortem(exec_dir),
    )
    case_1_rows = [row for row in rows if row["case_id"] == "case_1"]
    values = sorted(row["candidate_value"] for row in case_1_rows)
    assert values == [8.0, 10.0, 12.0]
    eight_row = next(row for row in case_1_rows if row["candidate_value"] == 8.0)
    assert "bftc_only_final" in eight_row["provenance_types"]
    assert "exec_model_final" in eight_row["provenance_types"]


def test_formula_variable_extraction_and_target_overlap(tmp_path: Path):
    bftc_dir, exec_dir, _, _ = _make_fixture(tmp_path)
    rows = mod.build_candidate_rows(
        bftc_only_dir=bftc_dir,
        exec_dir=exec_dir,
        exec_postmortem=mod.load_exec_postmortem(exec_dir),
    )
    case_1_gold_candidate = next(
        row for row in rows if row["case_id"] == "case_1" and row["candidate_value"] == 10.0
    )
    assert case_1_gold_candidate["came_from_formula_variable"] is True
    assert case_1_gold_candidate["candidate_equals_any_formula_variable"] is True
    assert case_1_gold_candidate["max_variable_name_target_overlap"] > 0
    assert case_1_gold_candidate["max_variable_description_target_overlap"] > 0
    assert case_1_gold_candidate["unit_match_any"] is True


def test_posthoc_gold_labeling_is_separate_from_candidate_construction(tmp_path: Path):
    bftc_dir, exec_dir, casebook, _ = _make_fixture(tmp_path)
    rows = mod.build_candidate_rows(
        bftc_only_dir=bftc_dir,
        exec_dir=exec_dir,
        exec_postmortem=mod.load_exec_postmortem(exec_dir),
    )
    assert all(row["candidate_matches_gold"] is False for row in rows)
    gold_map = {
        case_id: float(row["gold"])
        for case_id, row in mod.load_casebook(casebook).items()
    }
    labeled_rows = mod.attach_posthoc_gold_labels(rows, gold_map)
    gold_row = next(
        row for row in labeled_rows if row["case_id"] == "case_1" and row["candidate_value"] == 10.0
    )
    assert gold_row["candidate_matches_gold"] is True
    assert all("prompt_text" not in row for row in labeled_rows)


def test_prompt_gold_inconsistent_flag_handling(tmp_path: Path):
    bftc_dir, exec_dir, casebook, _ = _make_fixture(tmp_path)
    summary = mod.run_analysis(
        bftc_only_dir=bftc_dir,
        exec_dir=exec_dir,
        casebook_path=casebook,
        out_dir=tmp_path / "out",
        doc_path=tmp_path / "doc.md",
    )
    assert summary["prompt_gold_inconsistent_case_ids"] == ["case_2"]
    assert "case_2" in summary["prompt_gold_inconsistent_unrecoverable_case_ids"]


def test_selector_summary_counters(tmp_path: Path):
    bftc_dir, exec_dir, casebook, _ = _make_fixture(tmp_path)
    summary = mod.run_analysis(
        bftc_only_dir=bftc_dir,
        exec_dir=exec_dir,
        casebook_path=casebook,
        out_dir=tmp_path / "out",
        doc_path=tmp_path / "doc.md",
    )
    assert summary["candidate_pool_union_recovery_count"] == 1
    assert summary["oracle_upper_bound_count"] == 1
    assert summary["variable_rebinding_recoverable_count"] == 1
    selector_map = {row["selector"]: row for row in summary["selectors"]}
    assert selector_map["prefer_bftc_only_final"]["correct_count"] == 0
    assert selector_map["prefer_variable_with_target_overlap"]["correct_count"] == 1


def test_cli_smoke_test_on_tiny_fixtures(tmp_path: Path):
    bftc_dir, exec_dir, casebook, doc_path = _make_fixture(tmp_path)
    out_dir = tmp_path / "cli_out"
    subprocess.check_call(
        [
            sys.executable,
            "scripts/analyze_bftc_candidate_rebinding_selector_v1.py",
            "--bftc-only-dir",
            str(bftc_dir),
            "--exec-dir",
            str(exec_dir),
            "--casebook",
            str(casebook),
            "--out-dir",
            str(out_dir),
            "--doc-path",
            str(doc_path),
        ],
        cwd=REPO_ROOT,
    )
    assert (out_dir / "selector_summary.json").exists()
    assert (out_dir / "candidate_set_rows.jsonl").exists()
    assert (out_dir / "candidate_set_rows.csv").exists()
    assert (out_dir / "case_selector_report.md").exists()
    assert doc_path.exists()
    summary = json.loads((out_dir / "selector_summary.json").read_text(encoding="utf-8"))
    assert summary["case_count"] == 2

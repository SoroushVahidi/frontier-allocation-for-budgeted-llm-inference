from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import export_relation_verifier_manual_audit_sheet as export_script  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_creates_csv_from_small_jsonl_fixture(tmp_path: Path):
    input_path = tmp_path / "seed_rows.jsonl"
    output_path = tmp_path / "manual_audit.csv"
    _write_jsonl(
        input_path,
        [
            {
                "row_id": "rrseed_1",
                "problem_id": "p1",
                "case_id": "c1",
                "split_group_id": "train",
                "candidate_source": "direct_formula_family",
                "question": "How many apples are left?",
                "target_phrase": "apples are left",
                "target_semantic_type": "unknown",
                "candidate_answer": "5",
                "candidate_trace": "trace text",
                "gold_answer": "5",
                "provenance": {"source_path": "source.jsonl"},
            }
        ],
    )

    count = export_script.export_audit_sheet(input_path, output_path)

    assert count == 1
    rows = _read_csv(output_path)
    assert len(rows) == 1
    assert rows[0]["row_id"] == "rrseed_1"
    assert rows[0]["relation_ready_label_manual"] == ""
    assert rows[0]["first_error_axis_manual"] == ""
    assert rows[0]["notes_manual"] == "source_path=source.jsonl"


def test_truncates_long_traces(tmp_path: Path):
    input_path = tmp_path / "seed_rows.jsonl"
    output_path = tmp_path / "manual_audit.csv"
    long_trace = "x" * 2000
    _write_jsonl(
        input_path,
        [
            {
                "row_id": "rrseed_2",
                "problem_id": "p2",
                "case_id": "c2",
                "split_group_id": "val",
                "candidate_source": "direct_formula_family",
                "question": "Q",
                "target_phrase": "TP",
                "target_semantic_type": "unknown",
                "candidate_answer": "9",
                "candidate_trace": long_trace,
            }
        ],
    )

    export_script.export_audit_sheet(input_path, output_path)

    rows = _read_csv(output_path)
    assert len(rows[0]["candidate_trace_short"]) <= 800
    assert rows[0]["candidate_trace_short"].endswith("…")


def test_preserves_split_group_id_and_row_id(tmp_path: Path):
    input_path = tmp_path / "seed_rows.jsonl"
    output_path = tmp_path / "manual_audit.csv"
    _write_jsonl(
        input_path,
        [
            {
                "row_id": "rrseed_3",
                "problem_id": "p3",
                "case_id": "c3",
                "split_group_id": "test",
                "candidate_source": "explicit_case_split_family",
                "question": "Q",
                "target_phrase": "TP",
                "target_semantic_type": "unknown",
                "candidate_answer": "11",
                "candidate_trace": "trace",
            }
        ],
    )

    export_script.export_audit_sheet(input_path, output_path)

    rows = _read_csv(output_path)
    assert rows[0]["row_id"] == "rrseed_3"
    assert rows[0]["split_group_id"] == "test"


def test_does_not_require_gold_answer(tmp_path: Path):
    input_path = tmp_path / "seed_rows.jsonl"
    output_path = tmp_path / "manual_audit.csv"
    _write_jsonl(
        input_path,
        [
            {
                "row_id": "rrseed_4",
                "problem_id": "p4",
                "case_id": "c4",
                "split_group_id": "train",
                "candidate_source": "direct_formula_family",
                "question": "Q",
                "target_phrase": "TP",
                "target_semantic_type": "unknown",
                "candidate_answer": "12",
                "candidate_trace": "trace",
            }
        ],
    )

    export_script.export_audit_sheet(input_path, output_path)

    rows = _read_csv(output_path)
    assert rows[0]["gold_answer_metadata_only"] == ""


def test_writes_gold_answer_only_as_metadata_column_if_present(tmp_path: Path):
    input_path = tmp_path / "seed_rows.jsonl"
    output_path = tmp_path / "manual_audit.csv"
    _write_jsonl(
        input_path,
        [
            {
                "row_id": "rrseed_5",
                "problem_id": "p5",
                "case_id": "c5",
                "split_group_id": "train",
                "candidate_source": "direct_formula_family",
                "question": "Q",
                "target_phrase": "TP",
                "target_semantic_type": "unknown",
                "candidate_answer": "13",
                "candidate_trace": "trace",
                "gold_answer": "13",
            }
        ],
    )

    export_script.export_audit_sheet(input_path, output_path)

    rows = _read_csv(output_path)
    assert rows[0]["gold_answer_metadata_only"] == "13"
    assert rows[0]["relation_ready_label_manual"] == ""
    assert rows[0]["first_error_axis_manual"] == ""


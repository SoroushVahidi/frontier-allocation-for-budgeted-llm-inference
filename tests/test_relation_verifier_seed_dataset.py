from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import build_relation_verifier_seed_dataset as builder  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_jsonl_input_emits_normalized_row(tmp_path: Path):
    input_path = tmp_path / "rows.jsonl"
    output_path = tmp_path / "seed.jsonl"
    _write_jsonl(
        input_path,
        [
            {
                "case_id": "openai_gsm8k_1",
                "dataset_name": "gsm8k",
                "question": "Alice has 9 apples and gives away 4. How many apples are left?",
                "candidate_source": "declarative_v2",
                "candidate_trace": "9 - 4 = 5",
                "candidate_equation": "9 - 4",
                "candidate_answer": "5",
                "target_phrase": "apples left",
                "source_facts": ["Alice has 9 apples", "gives away 4"],
                "quantities": ["9", "4"],
                "candidate_relations": ["subtract away"],
                "formula_executable_ok": True,
                "gold_answer": "5",
            }
        ],
    )

    summary = builder.main(["--input-jsonl", str(input_path), "--output-jsonl", str(output_path)])

    assert summary["emitted_row_count"] == 1
    row = json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["case_id"] == "openai_gsm8k_1"
    assert row["problem_id"] == "gsm8k_1"
    assert row["split_group_id"] in {"train", "val", "test"}
    assert row["relation_ready_label"] == "unknown"
    assert row["first_error_axis"] == "unknown"
    assert row["gold_answer"] == "5"
    assert row["candidate_answer"] == "5"
    assert row["candidate_equation"] == "9 - 4"


def test_csv_input_emits_normalized_row(tmp_path: Path):
    input_path = tmp_path / "rows.csv"
    output_path = tmp_path / "seed.jsonl"
    _write_csv(
        input_path,
        [
            {
                "case_id": "openai_gsm8k_2",
                "dataset_name": "gsm8k",
                "question": "What is 12 divided by 3?",
                "candidate_source": "bftc_only",
                "trace": "12 / 3 = 4",
                "solution_formula": "12 / 3",
                "fa": "4",
                "source_facts": json.dumps(["12 items", "3 groups"]),
            }
        ],
    )

    summary = builder.main(["--input-csv", str(input_path), "--output-jsonl", str(output_path)])

    assert summary["emitted_row_count"] == 1
    row = json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["candidate_trace"] == "12 / 3 = 4"
    assert row["candidate_equation"] == "12 / 3"
    assert row["candidate_answer"] == "4"
    assert row["source_facts"] == ["12 items", "3 groups"]


def test_missing_question_is_excluded(tmp_path: Path):
    input_path = tmp_path / "rows.jsonl"
    output_path = tmp_path / "seed.jsonl"
    _write_jsonl(
        input_path,
        [
            {
                "case_id": "openai_gsm8k_3",
                "candidate_source": "declarative_v2",
                "candidate_trace": "x + y = 5",
                "candidate_equation": "x + y",
                "candidate_answer": "5",
            }
        ],
    )

    summary = builder.main(["--input-jsonl", str(input_path), "--output-jsonl", str(output_path)])

    assert summary["excluded_row_count"] == 1
    assert summary["exclusion_reason_counts"]["missing_question"] == 1
    assert output_path.read_text(encoding="utf-8") == ""


def test_missing_trace_and_equation_is_excluded(tmp_path: Path):
    input_path = tmp_path / "rows.jsonl"
    output_path = tmp_path / "seed.jsonl"
    _write_jsonl(
        input_path,
        [
            {
                "case_id": "openai_gsm8k_4",
                "question": "How many are left?",
                "candidate_source": "declarative_v2",
                "candidate_answer": "5",
            }
        ],
    )

    summary = builder.main(["--input-jsonl", str(input_path), "--output-jsonl", str(output_path)])

    assert summary["excluded_row_count"] == 1
    assert summary["exclusion_reason_counts"]["missing_candidate_trace_and_equation"] == 1


def test_include_excluded_preserves_excluded_rows_with_reason(tmp_path: Path):
    input_path = tmp_path / "rows.jsonl"
    output_path = tmp_path / "seed.jsonl"
    _write_jsonl(
        input_path,
        [
            {
                "case_id": "openai_gsm8k_5",
                "question": "How many apples are left?",
                "candidate_source": "declarative_v2",
                "candidate_trace": "9 - 4 = 5",
                "candidate_answer": "5",
                "prompt_gold_inconsistent_flag": True,
            }
        ],
    )

    summary = builder.main(
        ["--input-jsonl", str(input_path), "--output-jsonl", str(output_path), "--include-excluded"]
    )

    assert summary["excluded_row_count"] == 1
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["exclusion_reason"] == "gold_inconsistent_source"
    assert rows[0]["relation_ready_label"] == "unknown"


def test_split_group_id_is_stable_and_problem_level(tmp_path: Path):
    input_path = tmp_path / "rows.jsonl"
    output_path = tmp_path / "seed.jsonl"
    _write_jsonl(
        input_path,
        [
            {
                "case_id": "openai_gsm8k_6",
                "question": "What is 10 minus 3?",
                "candidate_source": "declarative_v1",
                "candidate_trace": "10 - 3 = 7",
                "candidate_equation": "10 - 3",
                "candidate_answer": "7",
            },
            {
                "case_id": "openai_gsm8k_6",
                "question": "What is 10 minus 3?",
                "candidate_source": "bftc_only",
                "candidate_trace": "10 - 3 = 7",
                "candidate_equation": "10 - 3",
                "candidate_answer": "7",
            },
        ],
    )

    builder.main(["--input-jsonl", str(input_path), "--output-jsonl", str(output_path)])
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["split_group_id"] == rows[1]["split_group_id"]
    assert rows[0]["problem_id"] == rows[1]["problem_id"] == "gsm8k_6"


def test_report_file_created_with_counts(tmp_path: Path):
    input_path = tmp_path / "rows.jsonl"
    output_path = tmp_path / "seed.jsonl"
    _write_jsonl(
        input_path,
        [
            {
                "case_id": "openai_gsm8k_7",
                "question": "How many are left?",
                "candidate_source": "declarative_v2",
                "candidate_trace": "9 - 4 = 5",
                "candidate_answer": "5",
            }
        ],
    )

    summary = builder.main(["--input-jsonl", str(input_path), "--output-jsonl", str(output_path)])
    report_path = output_path.with_name(output_path.stem + ".report.md")
    report = report_path.read_text(encoding="utf-8")

    assert summary["emitted_row_count"] == 1
    assert report_path.exists()
    assert "input rows" in report
    assert "emitted rows" in report
    assert "candidate source counts" in report


def test_source_with_holdout_marker_is_excluded(tmp_path: Path):
    input_path = tmp_path / "rows.jsonl"
    output_path = tmp_path / "seed.jsonl"
    _write_jsonl(
        input_path,
        [
            {
                "case_id": "openai_gsm8k_8",
                "question": "How many are left?",
                "candidate_source": "declarative_v2",
                "candidate_trace": "9 - 4 = 5",
                "candidate_answer": "5",
                "split_group_id": "eval_holdout",
            }
        ],
    )

    summary = builder.main(["--input-jsonl", str(input_path), "--output-jsonl", str(output_path)])

    assert summary["excluded_row_count"] == 1
    assert summary["exclusion_reason_counts"]["gold_inconsistent_source"] == 1


def test_no_api_or_eval_usage_in_builder_source():
    source = Path(builder.__file__).read_text(encoding="utf-8").lower()
    assert "eval(" not in source
    assert "import openai" not in source
    assert "import cohere" not in source


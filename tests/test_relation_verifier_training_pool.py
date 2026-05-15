"""Tests for build_relation_verifier_training_pool.py"""
from __future__ import annotations

import csv
import importlib.util as ilu
import json
import pathlib
import sys
import tempfile

import pytest

FORBIDDEN_IMPORTS = {"openai", "anthropic", "cohere", "requests", "httpx", "boto3"}


def _import_pool_builder():
    sys.path.insert(0, str(pathlib.Path("scripts").resolve().parent))
    spec = ilu.spec_from_file_location(
        "build_relation_verifier_training_pool",
        "scripts/build_relation_verifier_training_pool.py",
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SEED_ROWS = [
    {
        "row_id": "rrseed_aaa",
        "problem_id": "pid1",
        "case_id": "cid1",
        "split_group_id": "train",
        "candidate_source": "direct_formula_family",
        "question": "How many apples are there?",
        "candidate_trace": "Apples are counted as follows: 3 + 2 = 5.",
        "candidate_equation": "",
        "candidate_answer": "5",
        "target_phrase": "total apples",
        "target_semantic_type": "count",
        "candidate_relations": [],
        "formula_executable_ok": True,
        "relation_ready_label": "",
        "first_error_axis": "",
        "exclusion_reason": "",
    },
    {
        "row_id": "rrseed_bbb",
        "problem_id": "pid2",
        "case_id": "cid2",
        "split_group_id": "train",
        "candidate_source": "explicit_case_split_family",
        "question": "How many oranges are there?",
        "candidate_trace": "Oranges: 4 * 2 = 8.",
        "candidate_equation": "",
        "candidate_answer": "8",
        "target_phrase": "total oranges",
        "target_semantic_type": "count",
        "candidate_relations": [],
        "formula_executable_ok": True,
        "relation_ready_label": "",
        "first_error_axis": "",
        "exclusion_reason": "",
    },
]

FAILURE_RECORDS = [
    {
        "case_id": "case_001",
        "question": "How many cats does Mary have?",
        "gold_answer_metadata_only": "7",
        "method_name": "best",
        "selected_answer": "5",
        "selected_answer_canonical": "5",
        "selected_answer_support_count": 2,
        "unique_answer_count": 2,
        "all_candidate_answers": ["5", "3"],
        "all_candidate_traces": [
            '{"action":"final","step":"5 cats","answer":"5","confidence":1.0}',
            '{"action":"final","code":"answer = 3","answer":3,"confidence":1}',
        ],
        "gold_appeared_in_candidate_pool": False,
        "failure_type": "absent_from_tree",
        "failure_hints": {"trace_is_opaque": False, "arithmetic_only_suspicion": True},
        "notes": "",
    },
    {
        "case_id": "case_002",
        "question": "How many dogs does John have?",
        "gold_answer_metadata_only": "4",
        "method_name": "best",
        "selected_answer": "6",
        "selected_answer_canonical": "6",
        "selected_answer_support_count": 1,
        "unique_answer_count": 2,
        "all_candidate_answers": ["6", "4"],
        "all_candidate_traces": [
            "John has 6 dogs according to the trace.",
            "John has 4 dogs, computed as 2*2.",
        ],
        "gold_appeared_in_candidate_pool": True,
        "failure_type": "present_not_selected",
        "failure_hints": {"trace_is_opaque": False, "arithmetic_only_suspicion": False},
        "notes": "",
    },
]

PER_EXAMPLE_RECORDS = [
    {
        "example_id": "ex_001",
        "question": "Sally has 10 pens and gives 3 away. How many remain?",
        "gold_answer": "7",
        "gold_answer_canonical": "7",
        "final_answer_raw": "8",
        "failure_tag": "absent_from_tree",
        "gold_in_tree": False,
        "final_nodes": [
            {
                "branch_id": "l1_max_0",
                "reasoning_text": "Sally starts with 10 pens. She gives 3 away. 10 - 3 = 7.",
                "predicted_answer": "8",
                "numeric_leaf_value": "8",
            },
            {
                "branch_id": "pal_0",
                "reasoning_text": "answer = 10 - 3\nprint(answer)",
                "predicted_answer": "7",
                "numeric_leaf_value": "7",
            },
        ],
    }
]


def write_jsonl(rows: list[dict], path: pathlib.Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def write_csv(rows: list[dict], path: pathlib.Path) -> None:
    if not rows:
        path.write_text("")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


EXISTING_LABELS = [
    {
        "row_id": "rrseed_aaa",
        "problem_id": "pid1",
        "case_id": "cid1",
        "split_group_id": "train",
        "candidate_source": "direct_formula_family",
        "question": "How many apples are there?",
        "target_phrase": "total apples",
        "target_semantic_type": "count",
        "candidate_answer": "5",
        "candidate_trace_short": "Apples are counted as follows: 3 + 2 = 5.",
        "gold_answer_metadata_only": "",
        "relation_ready_label_manual": "ready",
        "first_error_axis_manual": "",
        "notes_manual": "",
    }
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_api_imports():
    src = pathlib.Path("scripts/build_relation_verifier_training_pool.py").read_text()
    import_lines = [l for l in src.splitlines() if l.strip().startswith(("import ", "from "))]
    for lib in FORBIDDEN_IMPORTS:
        for line in import_lines:
            assert lib not in line, f"Forbidden import '{lib}' in pool builder: {line}"


def test_multiple_jsonl_inputs_loaded():
    mod = _import_pool_builder()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        seed_path = d / "seed_rows.jsonl"
        fail_path = d / "failures.jsonl"
        out_dir = d / "out"
        write_jsonl(SEED_ROWS, seed_path)
        write_jsonl(FAILURE_RECORDS, fail_path)
        ret = mod.main(
            ["--input-jsonl", str(seed_path), "--input-jsonl", str(fail_path), "--output-dir", str(out_dir)]
        )
        assert ret == 0
        rows = [json.loads(l) for l in (out_dir / "pool_rows.jsonl").read_text().splitlines() if l]
        # seed: 2 rows, failures: 2 cases × 2 candidates = 4 → total 6
        assert len(rows) >= 4


def test_duplicate_rows_removed():
    mod = _import_pool_builder()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        p = d / "seed.jsonl"
        out_dir = d / "out"
        # Write same rows twice
        write_jsonl(SEED_ROWS + SEED_ROWS, p)
        mod.main(["--input-jsonl", str(p), "--output-dir", str(out_dir)])
        rows = [json.loads(l) for l in (out_dir / "pool_rows.jsonl").read_text().splitlines() if l]
        row_ids = [r["row_id"] for r in rows]
        assert len(row_ids) == len(set(row_ids)), "Duplicate row_ids found after deduplication"


def test_existing_labels_excluded():
    mod = _import_pool_builder()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        seed_path = d / "seed.jsonl"
        labels_path = d / "labels.csv"
        out_dir = d / "out"
        write_jsonl(SEED_ROWS, seed_path)
        write_csv(EXISTING_LABELS, labels_path)
        mod.main(
            [
                "--input-jsonl", str(seed_path),
                "--existing-labels-csv", str(labels_path),
                "--output-dir", str(out_dir),
            ]
        )
        rows = [json.loads(l) for l in (out_dir / "pool_rows.jsonl").read_text().splitlines() if l]
        row_ids = [r["row_id"] for r in rows]
        assert "rrseed_aaa" not in row_ids, "Already-labeled row must be excluded"


def test_manual_label_columns_blank():
    mod = _import_pool_builder()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        p = d / "fail.jsonl"
        out_dir = d / "out"
        write_jsonl(FAILURE_RECORDS, p)
        mod.main(["--input-jsonl", str(p), "--output-dir", str(out_dir)])
        rows = [json.loads(l) for l in (out_dir / "pool_rows.jsonl").read_text().splitlines() if l]
        for row in rows:
            assert row.get("relation_ready_label_manual", "") == "", "label must be blank"
            assert row.get("first_error_axis_manual", "") == "", "axis must be blank"
            assert row.get("notes_manual", "") == "", "notes must be blank"


def test_gold_not_in_feature_columns():
    mod = _import_pool_builder()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        p = d / "fail.jsonl"
        out_dir = d / "out"
        write_jsonl(FAILURE_RECORDS, p)
        mod.main(["--input-jsonl", str(p), "--output-dir", str(out_dir)])
        rows = [json.loads(l) for l in (out_dir / "pool_rows.jsonl").read_text().splitlines() if l]
        for row in rows:
            trace = row.get("candidate_trace_short", "")
            assert "gold_answer_metadata_only" not in trace
            # The gold VALUE (e.g. "7", "4") may coincidentally appear in the trace text,
            # but the column name itself must never be there
            assert "gold_answer_metadata_only" not in row.get("question", "")


def test_trace_quality_flags_computed():
    mod = _import_pool_builder()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        p = d / "fail.jsonl"
        out_dir = d / "out"
        write_jsonl(FAILURE_RECORDS, p)
        mod.main(["--input-jsonl", str(p), "--output-dir", str(out_dir)])
        rows = [json.loads(l) for l in (out_dir / "pool_rows.jsonl").read_text().splitlines() if l]
        for row in rows:
            assert "trace_quality_flags" in row
            assert row["trace_quality_flags"]  # must be non-empty string


def test_pool_report_written():
    mod = _import_pool_builder()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        p = d / "seed.jsonl"
        out_dir = d / "out"
        write_jsonl(SEED_ROWS, p)
        mod.main(["--input-jsonl", str(p), "--output-dir", str(out_dir)])
        assert (out_dir / "pool_report.md").exists()
        assert (out_dir / "manual_audit_batch.csv").exists()
        assert (out_dir / "pool_rows.jsonl").exists()


def test_manual_audit_csv_columns():
    mod = _import_pool_builder()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        p = d / "seed.jsonl"
        out_dir = d / "out"
        write_jsonl(SEED_ROWS, p)
        mod.main(["--input-jsonl", str(p), "--output-dir", str(out_dir)])
        with open(out_dir / "manual_audit_batch.csv") as f:
            cols = next(csv.reader(f))
        for expected_col in mod.AUDIT_CSV_COLUMNS:
            assert expected_col in cols, f"Expected column '{expected_col}' missing from audit CSV"


def test_per_example_records_schema():
    mod = _import_pool_builder()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        p = d / "per_example.jsonl"
        out_dir = d / "out"
        write_jsonl(PER_EXAMPLE_RECORDS, p)
        mod.main(["--input-jsonl", str(p), "--output-dir", str(out_dir)])
        rows = [json.loads(l) for l in (out_dir / "pool_rows.jsonl").read_text().splitlines() if l]
        # 1 case × 2 nodes = 2 rows
        assert len(rows) == 2
        for row in rows:
            assert row["question"] == "Sally has 10 pens and gives 3 away. How many remain?"
            # gold must be metadata only, not in trace
            assert "gold_answer_metadata_only" not in row["candidate_trace_short"]


def test_gold_answer_metadata_only_never_as_feature():
    mod = _import_pool_builder()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        p = d / "fail.jsonl"
        out_dir = d / "out"
        write_jsonl(FAILURE_RECORDS, p)
        mod.main(["--input-jsonl", str(p), "--output-dir", str(out_dir)])
        rows = [json.loads(l) for l in (out_dir / "pool_rows.jsonl").read_text().splitlines() if l]
        forbidden_feature_keys = {"candidate_trace_short", "question", "target_phrase", "target_semantic_type"}
        for row in rows:
            for key in forbidden_feature_keys:
                assert "gold_answer_metadata_only" not in row.get(key, "")

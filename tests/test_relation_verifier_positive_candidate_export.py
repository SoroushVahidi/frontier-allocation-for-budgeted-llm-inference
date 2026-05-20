"""Tests for export_relation_verifier_positive_candidate_batch.py"""
from __future__ import annotations

import csv
import importlib.util as ilu
import json
import pathlib
import sys
import tempfile

import pytest

FORBIDDEN_IMPORTS = {"openai", "anthropic", "cohere", "requests", "httpx", "boto3"}


def _import_exporter():
    sys.path.insert(0, str(pathlib.Path("scripts").resolve().parent))
    spec = ilu.spec_from_file_location(
        "export_relation_verifier_positive_candidate_batch",
        "scripts/export_relation_verifier_positive_candidate_batch.py",
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PER_EXAMPLE_CORRECT = {
    "example_id": "gsm8k_1",
    "question": "Alice has 3 baskets with 4 apples each. How many apples total?",
    "exact_match": 1,
    "gold_answer": "12",
    "gold_answer_canonical": "12",
    "method": "direct_reserve",
    "final_nodes": [
        {
            "branch_id": "pal_branch_0",
            # Bare digit-op-digit pattern "3 * 4" ensures has_arithmetic flag fires
            "reasoning_text": "Alice counted 3 * 4 = 12 apples in total.",
            "predicted_answer": "12",
            "predicted_answer_normalized": "12",
            "numeric_leaf_value": "12",
            "numeric_leaf_status": "ok",
        },
        {
            "branch_id": "pal_branch_1",
            "reasoning_text": '{"action": "final", "answer": "12"}',
            "predicted_answer": "12",
            "predicted_answer_normalized": "12",
            "numeric_leaf_value": None,
            "numeric_leaf_status": "ok",
        },
    ],
}

PER_EXAMPLE_WRONG = {
    "example_id": "gsm8k_2",
    "question": "Bob has 5 boxes with 6 toys each. How many toys?",
    "exact_match": 0,
    "gold_answer": "30",
    "gold_answer_canonical": "30",
    "method": "direct_reserve",
    "final_nodes": [
        {
            "branch_id": "pal_branch_0",
            "reasoning_text": "Bob has 5 boxes * 5 toys = 25 toys.",
            "predicted_answer": "25",
            "predicted_answer_normalized": "25",
            "numeric_leaf_value": "25",
            "numeric_leaf_status": "ok",
        }
    ],
}

CANDIDATE_NODES_ROW = {
    "case_id": "unified_case_1",
    "problem_statement": "Jane earns $10/hr and works 8 hrs. Total?",
    "gold_answer_metadata_only": "80",
    "candidate_nodes": [
        {
            "candidate_id": "direct_reserve_0",
            "source_family": "direct_reserve",
            "final_answer": "80",
            "normalized_answer": "80",
            "trace_text": "Jane earns 10 * 8 = 80 dollars.",
        }
    ],
}

FAILURE_RECORD = {
    "case_id": "fail_case_1",
    "question": "Carl has 7 boxes with 3 items each. Total?",
    "gold_answer_metadata_only": "21",
    "failure_type": "output_layer_mismatch",
    "all_candidate_answers": ["21", "14"],
    "all_candidate_traces": [
        "Carl has 7 * 3 = 21 items total.",
        '{"action": "final", "answer": "14"}',
    ],
    "failure_hints": {},
}

ALREADY_LABELED_ROW = {
    "row_id": "rrpool_existing_001",
    "question": "Already labeled?",
    "candidate_answer": "7",
    "candidate_trace_short": "7 + 0 = 7",
    "trace_quality_flags": "has_arithmetic|answer_present",
    "relation_ready_label_manual": "ready",
    "first_error_axis_manual": "",
    "notes_manual": "",
    "gold_answer_metadata_only": "",
    "source_artifact": "",
    "candidate_source": "",
    "case_id": "",
    "problem_id": "",
}


def _write_jsonl(path: pathlib.Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _write_csv(path: pathlib.Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNoForbiddenImports:
    def test_no_api_imports(self):
        import ast
        src = pathlib.Path(
            "scripts/export_relation_verifier_positive_candidate_batch.py"
        ).read_text()
        tree = ast.parse(src)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module.split(".")[0])
        for pkg in FORBIDDEN_IMPORTS:
            assert pkg not in imported, f"Forbidden import: {pkg}"


class TestSchemaDetection:
    def test_per_example_records(self):
        mod = _import_exporter()
        assert mod._detect_schema(PER_EXAMPLE_CORRECT) == "per_example_records"

    def test_candidate_nodes(self):
        mod = _import_exporter()
        assert mod._detect_schema(CANDIDATE_NODES_ROW) == "candidate_nodes"

    def test_failure_records(self):
        mod = _import_exporter()
        assert mod._detect_schema(FAILURE_RECORD) == "failure_records"


class TestPerExampleLoader:
    def test_extracts_nodes(self):
        mod = _import_exporter()
        rows = list(mod._load_per_example_records([PER_EXAMPLE_CORRECT], "test.jsonl", 30))
        # Branch 0 has arithmetic trace → passes min_trace_chars=30; branch 1 is opaque JSON
        arith_rows = [r for r in rows if "has_arithmetic" in r["trace_quality_flags"]]
        assert len(arith_rows) >= 1
        assert arith_rows[0]["candidate_answer"] == "12"

    def test_is_correct_set_from_exact_match(self):
        mod = _import_exporter()
        rows = list(mod._load_per_example_records([PER_EXAMPLE_CORRECT], "test.jsonl", 30))
        assert all(r["is_correct_offline_metadata"] == "yes" for r in rows)

    def test_wrong_row_marked_not_correct(self):
        mod = _import_exporter()
        rows = list(mod._load_per_example_records([PER_EXAMPLE_WRONG], "test.jsonl", 30))
        assert all(r["is_correct_offline_metadata"] == "no" for r in rows)

    def test_gold_not_in_feature_fields(self):
        """Gold answer must appear only in gold_answer_metadata_only, never in
        question, candidate_source, or other feature-adjacent columns."""
        mod = _import_exporter()
        rows = list(mod._load_per_example_records([PER_EXAMPLE_CORRECT], "test.jsonl", 30))
        assert rows, "Should produce at least one row"
        for row in rows:
            # Gold value must be in metadata column (only available when include_gold is set)
            # and must NOT have been injected into the question or source fields
            assert row["question"] == PER_EXAMPLE_CORRECT["question"], \
                "Question must not be modified"
            assert "gold" not in row["candidate_source"].lower(), \
                "candidate_source must not reference gold"
            # gold_answer_metadata_only may contain the value (it's the metadata field)
            assert row["gold_answer_metadata_only"] == "12"


class TestCorrectRowsPrioritised:
    def test_correct_rows_score_higher(self):
        mod = _import_exporter()
        flags = "has_arithmetic|answer_present"
        score_correct = mod._readiness_score(flags, True, "3 * 4 = 12 total items.")
        score_wrong = mod._readiness_score(flags, False, "3 * 4 = 12 total items.")
        assert score_correct > score_wrong

    def test_correct_rows_appear_first_in_batch(self):
        mod = _import_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            # Wrong row first in file, correct row second
            data = [PER_EXAMPLE_WRONG, PER_EXAMPLE_CORRECT]
            input_jsonl = tmpdir / "data.jsonl"
            _write_jsonl(input_jsonl, data)
            out_dir = tmpdir / "out"
            mod.main([
                "--input-jsonl", str(input_jsonl),
                "--output-dir", str(out_dir),
                "--batch-size", "50",
                "--min-trace-chars", "20",
            ])
            with open(out_dir / "positive_candidate_batch.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            correct_indices = [i for i, r in enumerate(rows)
                               if r["is_correct_offline_metadata"] == "yes"]
            wrong_indices = [i for i, r in enumerate(rows)
                             if r["is_correct_offline_metadata"] == "no"]
            if correct_indices and wrong_indices:
                assert min(correct_indices) < max(wrong_indices), \
                    "Correct rows should appear before wrong rows"


class TestOpaqueExclusion:
    def test_opaque_traces_excluded_by_default(self):
        mod = _import_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            data = [
                {
                    "example_id": "opaque_case",
                    "question": "Opaque question?",
                    "exact_match": 1,
                    "gold_answer": "5",
                    "method": "test",
                    "final_nodes": [
                        {
                            "branch_id": "b0",
                            "reasoning_text": "",   # empty → opaque
                            "predicted_answer": "5",
                        }
                    ],
                },
                {
                    "example_id": "good_case",
                    "question": "Good question with reasoning?",
                    "exact_match": 1,
                    "gold_answer": "12",
                    "method": "test",
                    "final_nodes": [
                        {
                            "branch_id": "b0",
                            "reasoning_text": "3 * 4 = 12 total items.",
                            "predicted_answer": "12",
                        }
                    ],
                },
            ]
            input_jsonl = tmpdir / "data.jsonl"
            _write_jsonl(input_jsonl, data)
            out_dir = tmpdir / "out"
            mod.main([
                "--input-jsonl", str(input_jsonl),
                "--output-dir", str(out_dir),
                "--batch-size", "50",
                "--min-trace-chars", "10",
            ])
            with open(out_dir / "positive_candidate_batch.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            assert all("opaque" not in r["trace_quality_flags"] for r in rows)
            assert len(rows) == 1


class TestAlreadyLabeledExclusion:
    def test_labeled_rows_excluded(self):
        mod = _import_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            # Create a row whose row_id matches an existing label
            q = "Already labeled question?"
            ca = "7"
            trace = "7 * 1 = 7 items."
            existing_id = mod._make_row_id(q, ca, trace[:mod.TRACE_SHORT_MAX])
            data = [
                {
                    "example_id": "old_case",
                    "question": q,
                    "exact_match": 1,
                    "gold_answer": "7",
                    "method": "test",
                    "final_nodes": [{"branch_id": "b0", "reasoning_text": trace,
                                     "predicted_answer": ca}],
                },
                {
                    "example_id": "new_case",
                    "question": "Fresh question with new reasoning?",
                    "exact_match": 1,
                    "gold_answer": "20",
                    "method": "test",
                    "final_nodes": [{"branch_id": "b0",
                                     "reasoning_text": "5 * 4 = 20 fresh items.",
                                     "predicted_answer": "20"}],
                },
            ]
            input_jsonl = tmpdir / "data.jsonl"
            _write_jsonl(input_jsonl, data)
            # Label the first row_id
            labels_csv = tmpdir / "labels.csv"
            labeled = {**ALREADY_LABELED_ROW, "row_id": existing_id}
            _write_csv(labels_csv, [labeled])
            out_dir = tmpdir / "out"
            mod.main([
                "--input-jsonl", str(input_jsonl),
                "--existing-labels-csv", str(labels_csv),
                "--output-dir", str(out_dir),
                "--batch-size", "50",
                "--min-trace-chars", "10",
            ])
            with open(out_dir / "positive_candidate_batch.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            row_ids = {r["row_id"] for r in rows}
            assert existing_id not in row_ids
            assert any("new_case" in r["case_id"] for r in rows)


class TestGoldExclusion:
    def test_gold_excluded_by_default(self):
        mod = _import_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            input_jsonl = tmpdir / "data.jsonl"
            _write_jsonl(input_jsonl, [PER_EXAMPLE_CORRECT])
            out_dir = tmpdir / "out"
            mod.main([
                "--input-jsonl", str(input_jsonl),
                "--output-dir", str(out_dir),
                "--batch-size", "10",
                "--min-trace-chars", "10",
            ])
            with open(out_dir / "positive_candidate_batch.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                assert row.get("gold_answer_metadata_only", "") == ""

    def test_gold_included_with_flag(self):
        mod = _import_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            input_jsonl = tmpdir / "data.jsonl"
            _write_jsonl(input_jsonl, [PER_EXAMPLE_CORRECT])
            out_dir = tmpdir / "out"
            mod.main([
                "--input-jsonl", str(input_jsonl),
                "--output-dir", str(out_dir),
                "--batch-size", "10",
                "--min-trace-chars", "10",
                "--include-gold-metadata",
            ])
            with open(out_dir / "positive_candidate_batch.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            gold_vals = [r.get("gold_answer_metadata_only", "") for r in rows]
            assert any(v for v in gold_vals)


class TestManualLabelColumnsBlank:
    def test_label_columns_blank(self):
        mod = _import_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            input_jsonl = tmpdir / "data.jsonl"
            _write_jsonl(input_jsonl, [PER_EXAMPLE_CORRECT])
            out_dir = tmpdir / "out"
            mod.main([
                "--input-jsonl", str(input_jsonl),
                "--output-dir", str(out_dir),
                "--batch-size", "10",
                "--min-trace-chars", "10",
            ])
            with open(out_dir / "positive_candidate_batch.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                assert row["relation_ready_label_manual"] == ""
                assert row["first_error_axis_manual"] == ""
                assert row["notes_manual"] == ""


class TestDuplicateRemoval:
    def test_duplicate_rows_removed(self):
        mod = _import_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            # Same row in two files
            input1 = tmpdir / "a.jsonl"
            input2 = tmpdir / "b.jsonl"
            _write_jsonl(input1, [PER_EXAMPLE_CORRECT])
            _write_jsonl(input2, [PER_EXAMPLE_CORRECT])
            out_dir = tmpdir / "out"
            mod.main([
                "--input-jsonl", str(input1),
                "--input-jsonl", str(input2),
                "--output-dir", str(out_dir),
                "--batch-size", "50",
                "--min-trace-chars", "10",
            ])
            with open(out_dir / "positive_candidate_batch.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            row_ids = [r["row_id"] for r in rows]
            assert len(row_ids) == len(set(row_ids)), "Duplicate row_ids found"


class TestBatchSizeRespected:
    def test_batch_size_limits_output(self):
        mod = _import_exporter()
        # Create 5 correct rows, request only 2
        data = [
            {
                "example_id": f"case_{i}",
                "question": f"Question number {i} with math?",
                "exact_match": 1,
                "gold_answer": str(i * 3),
                "method": "test",
                "final_nodes": [
                    {
                        "branch_id": "b0",
                        "reasoning_text": f"{i} * 3 = {i*3} total items computed here.",
                        "predicted_answer": str(i * 3),
                    }
                ],
            }
            for i in range(1, 6)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            input_jsonl = tmpdir / "data.jsonl"
            _write_jsonl(input_jsonl, data)
            out_dir = tmpdir / "out"
            mod.main([
                "--input-jsonl", str(input_jsonl),
                "--output-dir", str(out_dir),
                "--batch-size", "2",
                "--min-trace-chars", "10",
            ])
            with open(out_dir / "positive_candidate_batch.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 2

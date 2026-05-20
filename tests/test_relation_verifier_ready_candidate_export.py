"""Tests for export_relation_verifier_ready_candidate_batch.py"""
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
        "export_relation_verifier_ready_candidate_batch",
        "scripts/export_relation_verifier_ready_candidate_batch.py",
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAILURE_RECORDS = [
    {
        "case_id": "test_case_1",
        "question": "How many apples did Maria buy?",
        "gold_answer_metadata_only": "15",
        "failure_type": "output_layer_mismatch",
        "all_candidate_answers": ["15", "10"],
        "all_candidate_traces": [
            "Maria bought 3 bags with 5 apples each: 3 * 5 = 15.",
            '{"action": "final", "answer": "10"}',
        ],
        "failure_hints": {},
    }
]

UNIFIED_EVIDENCE = [
    {
        "case_id": "unified_case_1",
        "problem_statement": "John earns $12 per hour and works 8 hours. How much does he earn?",
        "gold_answer_metadata_only": "96",
        "candidate_nodes": [
            {
                "candidate_id": "direct_reserve_0",
                "source_family": "direct_reserve",
                "final_answer": "96",
                "normalized_answer": "96",
                "trace_text": "John earns 12 * 8 = 96 dollars.",
                "step_text": None,
            },
            {
                "candidate_id": "direct_reserve_1",
                "source_family": "direct_reserve",
                "final_answer": "84",
                "normalized_answer": "84",
                "trace_text": "",  # empty — should be opaque
                "step_text": None,
            },
        ],
    }
]

SEED_ROWS = [
    {
        "row_id": "rrseed_aaa",
        "case_id": "seed_case_1",
        "candidate_source": "formula_family",
        "question": "There are 4 groups of 6 students each. Total?",
        "candidate_trace": "answer = 4 * 6\nprint(answer)",
        "candidate_answer": "24",
        "target_phrase": "total students",
    }
]

LABELED_CSV_ROWS = [
    {
        "row_id": "rrpool_existing_aaa",
        "problem_id": "old_case",
        "question": "Already labeled question?",
        "candidate_answer": "5",
        "candidate_trace_short": "5 + 0 = 5",
        "trace_quality_flags": "has_arithmetic|answer_present",
        "relation_ready_label_manual": "ready",
        "first_error_axis_manual": "",
        "notes_manual": "",
        "gold_answer_metadata_only": "",
        "source_artifact": "",
        "candidate_source": "",
        "case_id": "",
    }
]


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
        src = pathlib.Path("scripts/export_relation_verifier_ready_candidate_batch.py").read_text()
        tree = ast.parse(src)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module.split(".")[0])
        for pkg in FORBIDDEN_IMPORTS:
            assert pkg not in imported, f"Forbidden import found: {pkg}"


class TestSchemaDetection:
    def test_candidate_nodes_detected(self):
        mod = _import_exporter()
        schema = mod._detect_schema(UNIFIED_EVIDENCE[0])
        assert schema == "candidate_nodes"

    def test_failure_records_detected(self):
        mod = _import_exporter()
        schema = mod._detect_schema(FAILURE_RECORDS[0])
        assert schema == "failure_records"

    def test_seed_rows_detected(self):
        mod = _import_exporter()
        schema = mod._detect_schema(SEED_ROWS[0])
        assert schema == "seed_rows"


class TestCandidateNodesLoader:
    def test_extracts_non_opaque_node(self):
        mod = _import_exporter()
        rows = list(mod._load_candidate_nodes(UNIFIED_EVIDENCE, "test.jsonl"))
        # Should produce 2 candidates (one with trace, one without)
        assert len(rows) == 2
        # First has arithmetic trace
        has_arith = [r for r in rows if "has_arithmetic" in r["trace_quality_flags"]]
        assert len(has_arith) == 1
        assert has_arith[0]["candidate_answer"] == "96"

    def test_gold_excluded_from_feature_fields(self):
        mod = _import_exporter()
        rows = list(mod._load_candidate_nodes(UNIFIED_EVIDENCE, "test.jsonl"))
        for row in rows:
            assert row["gold_answer_metadata_only"] not in (row["candidate_trace_short"],
                                                             row["question"])

    def test_row_id_deterministic(self):
        mod = _import_exporter()
        rows1 = list(mod._load_candidate_nodes(UNIFIED_EVIDENCE, "test.jsonl"))
        rows2 = list(mod._load_candidate_nodes(UNIFIED_EVIDENCE, "test.jsonl"))
        assert [r["row_id"] for r in rows1] == [r["row_id"] for r in rows2]


class TestFailureRecordsLoader:
    def test_extracts_both_candidates(self):
        mod = _import_exporter()
        rows = list(mod._load_failure_records(FAILURE_RECORDS, "test.jsonl"))
        assert len(rows) == 2

    def test_arithmetic_trace_flagged(self):
        mod = _import_exporter()
        rows = list(mod._load_failure_records(FAILURE_RECORDS, "test.jsonl"))
        arith_rows = [r for r in rows if "has_arithmetic" in r["trace_quality_flags"]]
        assert len(arith_rows) == 1
        assert "3 * 5" in arith_rows[0]["candidate_trace_short"]


class TestSeedRowsLoader:
    def test_extracts_seed_row(self):
        mod = _import_exporter()
        rows = list(mod._load_seed_rows(SEED_ROWS, "test.jsonl"))
        assert len(rows) == 1
        assert "has_code" in rows[0]["trace_quality_flags"]

    def test_preserves_existing_row_id(self):
        mod = _import_exporter()
        rows = list(mod._load_seed_rows(SEED_ROWS, "test.jsonl"))
        assert rows[0]["row_id"] == "rrseed_aaa"


class TestAlreadyLabeledExclusion:
    def test_labeled_rows_excluded(self):
        mod = _import_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            labels_csv = pathlib.Path(tmp) / "labels.csv"
            _write_csv(labels_csv, LABELED_CSV_ROWS)
            labeled_ids = mod.load_labeled_ids([labels_csv])
        assert "rrpool_existing_aaa" in labeled_ids

    def test_end_to_end_exclusion(self):
        """Already-labeled rows must not appear in batch output."""
        mod = _import_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            # Write a failure record that matches an already-labeled row_id
            q = "Already labeled question?"
            ca = "5"
            trace = "5 + 0 = 5"
            existing_id = mod._make_row_id(q, ca, trace[:mod.TRACE_SHORT_MAX])
            failure_data = [{
                "case_id": "old_case",
                "question": q,
                "gold_answer_metadata_only": "5",
                "failure_type": "",
                "all_candidate_answers": [ca],
                "all_candidate_traces": [trace],
                "failure_hints": {},
            }]
            # Also add a fresh non-opaque row
            failure_data.append({
                "case_id": "new_case",
                "question": "Fresh question with multi-step?",
                "gold_answer_metadata_only": "20",
                "failure_type": "",
                "all_candidate_answers": ["20"],
                "all_candidate_traces": ["5 * 4 = 20 apples total."],
                "failure_hints": {},
            })
            input_jsonl = tmpdir / "failures.jsonl"
            _write_jsonl(input_jsonl, failure_data)
            labels_csv = tmpdir / "labels.csv"
            labeled_row = {**LABELED_CSV_ROWS[0], "row_id": existing_id}
            _write_csv(labels_csv, [labeled_row])
            out_dir = tmpdir / "out"
            mod.main([
                "--input-jsonl", str(input_jsonl),
                "--existing-labels-csv", str(labels_csv),
                "--output-dir", str(out_dir),
                "--batch-size", "50",
            ])
            out_csv = out_dir / "ready_candidate_batch.csv"
            with open(out_csv, newline="") as f:
                rows = list(csv.DictReader(f))
            row_ids = {r["row_id"] for r in rows}
            assert existing_id not in row_ids, "Already-labeled row must be excluded"
            assert any("new_case" in r["case_id"] for r in rows), "Fresh row must be included"


class TestOpaqueExclusion:
    def test_opaque_rows_not_in_batch(self):
        mod = _import_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            data = [
                {
                    "case_id": "opaque_case",
                    "question": "Opaque question?",
                    "gold_answer_metadata_only": "",
                    "failure_type": "",
                    "all_candidate_answers": ["7"],
                    "all_candidate_traces": [""],  # empty → opaque
                    "failure_hints": {},
                },
                {
                    "case_id": "good_case",
                    "question": "Good question with reasoning?",
                    "gold_answer_metadata_only": "",
                    "failure_type": "",
                    "all_candidate_answers": ["12"],
                    "all_candidate_traces": ["3 * 4 = 12 total items."],
                    "failure_hints": {},
                },
            ]
            input_jsonl = tmpdir / "data.jsonl"
            _write_jsonl(input_jsonl, data)
            out_dir = tmpdir / "out"
            mod.main([
                "--input-jsonl", str(input_jsonl),
                "--output-dir", str(out_dir),
                "--batch-size", "50",
            ])
            with open(out_dir / "ready_candidate_batch.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 1
            assert "has_arithmetic" in rows[0]["trace_quality_flags"]


class TestGoldExclusion:
    def test_gold_excluded_by_default(self):
        mod = _import_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            input_jsonl = tmpdir / "evidence.jsonl"
            _write_jsonl(input_jsonl, UNIFIED_EVIDENCE)
            out_dir = tmpdir / "out"
            mod.main([
                "--input-jsonl", str(input_jsonl),
                "--output-dir", str(out_dir),
                "--batch-size", "50",
            ])
            with open(out_dir / "ready_candidate_batch.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            # gold_answer_metadata_only column should be blank
            for row in rows:
                assert row.get("gold_answer_metadata_only", "") == "", \
                    "Gold must be blank by default"

    def test_gold_included_when_flag_set(self):
        mod = _import_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            input_jsonl = tmpdir / "evidence.jsonl"
            _write_jsonl(input_jsonl, UNIFIED_EVIDENCE)
            out_dir = tmpdir / "out"
            mod.main([
                "--input-jsonl", str(input_jsonl),
                "--output-dir", str(out_dir),
                "--batch-size", "50",
                "--include-gold-metadata",
            ])
            with open(out_dir / "ready_candidate_batch.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            gold_values = [r.get("gold_answer_metadata_only", "") for r in rows]
            assert any(v for v in gold_values), "Gold should be present when flag is set"


class TestManualLabelColumnsBlank:
    def test_label_columns_are_blank(self):
        mod = _import_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            input_jsonl = tmpdir / "evidence.jsonl"
            _write_jsonl(input_jsonl, UNIFIED_EVIDENCE)
            out_dir = tmpdir / "out"
            mod.main([
                "--input-jsonl", str(input_jsonl),
                "--output-dir", str(out_dir),
                "--batch-size", "50",
            ])
            with open(out_dir / "ready_candidate_batch.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                assert row["relation_ready_label_manual"] == ""
                assert row["first_error_axis_manual"] == ""
                assert row["notes_manual"] == ""


class TestBatchSizeRespected:
    def test_batch_size_limits_output(self):
        mod = _import_exporter()
        # Create 5 non-opaque rows but request only 2
        data = [
            {
                "case_id": f"case_{i}",
                "question": f"Question number {i}?",
                "gold_answer_metadata_only": str(i),
                "failure_type": "",
                "all_candidate_answers": [str(i * 3)],
                "all_candidate_traces": [f"{i} * 3 = {i*3} units."],
                "failure_hints": {},
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
            ])
            with open(out_dir / "ready_candidate_batch.csv", newline="") as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 2

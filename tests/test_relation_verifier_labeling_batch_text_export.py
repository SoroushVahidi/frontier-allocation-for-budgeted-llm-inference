"""Tests for export_relation_verifier_labeling_batch_text.py"""
from __future__ import annotations

import csv
import importlib.util as ilu
import pathlib
import sys
import tempfile

import pytest

FORBIDDEN_IMPORTS = {"openai", "anthropic", "cohere", "requests", "httpx", "boto3"}


def _import_exporter():
    sys.path.insert(0, str(pathlib.Path("scripts").resolve().parent))
    spec = ilu.spec_from_file_location(
        "export_relation_verifier_labeling_batch_text",
        "scripts/export_relation_verifier_labeling_batch_text.py",
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

AUDIT_ROWS = [
    {
        "row_id": f"rrpool_{i:04d}",
        "problem_id": f"pid{i}",
        "case_id": f"cid{i}",
        "split_group_id": "train",
        "candidate_source": "cohere_run_cand_0",
        "source_artifact": "failures.jsonl",
        "suggested_priority": "high" if i < 5 else "medium",
        "trace_quality_flags": "has_arithmetic|answer_present",
        "question": f"Question number {i}?",
        "target_phrase": f"target {i}",
        "target_semantic_type": "count",
        "candidate_answer": str(i * 10),
        "candidate_trace_short": f"The answer is {i * 10} because {i} * 10 = {i * 10}.",
        "gold_answer_metadata_only": str(i * 10 + 1),
        "relation_ready_label_manual": "",
        "first_error_axis_manual": "",
        "notes_manual": "",
    }
    for i in range(12)
]


def write_csv(rows: list[dict], path: pathlib.Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_api_imports():
    src = pathlib.Path("scripts/export_relation_verifier_labeling_batch_text.py").read_text()
    import_lines = [l for l in src.splitlines() if l.strip().startswith(("import ", "from "))]
    for lib in FORBIDDEN_IMPORTS:
        for line in import_lines:
            assert lib not in line, f"Forbidden import '{lib}' found: {line}"


def test_exports_only_high_priority():
    mod = _import_exporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        csv_path = d / "audit.csv"
        out_dir = d / "out"
        write_csv(AUDIT_ROWS, csv_path)
        ret = mod.main([
            "--input-csv", str(csv_path),
            "--output-dir", str(out_dir),
            "--priority", "high",
            "--start-index", "0",
            "--batch-size", "10",
        ])
        assert ret == 0
        batch_files = list(out_dir.glob("labeling_batch_high_*.md"))
        assert len(batch_files) == 1
        content = batch_files[0].read_text()
        # Only 5 high-priority rows exist; batch capped at 5
        assert "Question number 0?" in content
        assert "Question number 4?" in content
        # Medium rows must not appear
        assert "Question number 5?" not in content


def test_respects_start_index_and_batch_size():
    mod = _import_exporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        csv_path = d / "audit.csv"
        out_dir = d / "out"
        write_csv(AUDIT_ROWS, csv_path)
        ret = mod.main([
            "--input-csv", str(csv_path),
            "--output-dir", str(out_dir),
            "--priority", "all",
            "--start-index", "2",
            "--batch-size", "3",
        ])
        assert ret == 0
        batch_files = list(out_dir.glob("labeling_batch_all_*.md"))
        content = batch_files[0].read_text()
        # Should contain rows at index 2, 3, 4 (question numbers 2, 3, 4)
        assert "Question number 2?" in content
        assert "Question number 4?" in content
        assert "Question number 0?" not in content
        assert "Question number 5?" not in content


def test_gold_excluded_by_default():
    mod = _import_exporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        csv_path = d / "audit.csv"
        out_dir = d / "out"
        write_csv(AUDIT_ROWS, csv_path)
        mod.main([
            "--input-csv", str(csv_path),
            "--output-dir", str(out_dir),
            "--priority", "high",
            "--batch-size", "5",
        ])
        batch_files = list(out_dir.glob("labeling_batch_*.md"))
        content = batch_files[0].read_text()
        assert "METADATA ONLY" not in content
        assert "Gold answer" not in content


def test_gold_included_when_requested_and_marked():
    mod = _import_exporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        csv_path = d / "audit.csv"
        out_dir = d / "out"
        write_csv(AUDIT_ROWS, csv_path)
        mod.main([
            "--input-csv", str(csv_path),
            "--output-dir", str(out_dir),
            "--priority", "high",
            "--batch-size", "5",
            "--include-gold-metadata",
        ])
        batch_files = list(out_dir.glob("labeling_batch_*.md"))
        content = batch_files[0].read_text()
        assert "METADATA ONLY" in content
        assert "Gold answer" in content


def test_manual_label_fields_are_blank_placeholders():
    mod = _import_exporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        csv_path = d / "audit.csv"
        out_dir = d / "out"
        write_csv(AUDIT_ROWS, csv_path)
        mod.main([
            "--input-csv", str(csv_path),
            "--output-dir", str(out_dir),
            "--priority", "all",
            "--batch-size", "5",
        ])
        batch_files = list(out_dir.glob("labeling_batch_*.md"))
        content = batch_files[0].read_text()
        assert "relation_ready_label_manual" in content
        assert "first_error_axis_manual" in content
        assert "notes_manual" in content
        # Should be fill-in prompts, not pre-filled values
        assert "fill:" in content


def test_trace_truncated_to_max_chars():
    mod = _import_exporter()
    long_trace = "A" * 2000
    rows = [
        {**AUDIT_ROWS[0], "candidate_trace_short": long_trace, "suggested_priority": "all"}
    ]
    # Patch priority to avoid filtering
    rows[0]["suggested_priority"] = "medium"
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        csv_path = d / "audit.csv"
        out_dir = d / "out"
        write_csv(rows, csv_path)
        mod.main([
            "--input-csv", str(csv_path),
            "--output-dir", str(out_dir),
            "--priority", "all",
            "--batch-size", "1",
            "--max-trace-chars", "100",
        ])
        batch_files = list(out_dir.glob("labeling_batch_*.md"))
        content = batch_files[0].read_text()
        assert "truncated" in content
        # Should not contain more than ~100 A's in a row
        assert "A" * 101 not in content


def test_report_written():
    mod = _import_exporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        csv_path = d / "audit.csv"
        out_dir = d / "out"
        write_csv(AUDIT_ROWS, csv_path)
        mod.main([
            "--input-csv", str(csv_path),
            "--output-dir", str(out_dir),
            "--priority", "all",
            "--batch-size", "5",
        ])
        assert (out_dir / "labeling_batch_report.md").exists()
        report = (out_dir / "labeling_batch_report.md").read_text()
        assert "Gold" in report
        assert "NO" in report  # gold excluded by default


def test_start_index_beyond_group_returns_error():
    mod = _import_exporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        d = pathlib.Path(tmpdir)
        csv_path = d / "audit.csv"
        out_dir = d / "out"
        write_csv(AUDIT_ROWS, csv_path)
        ret = mod.main([
            "--input-csv", str(csv_path),
            "--output-dir", str(out_dir),
            "--priority", "high",
            "--start-index", "100",
            "--batch-size", "5",
        ])
        assert ret != 0


def test_missing_csv_returns_error():
    mod = _import_exporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        ret = mod.main([
            "--input-csv", str(pathlib.Path(tmpdir) / "nonexistent.csv"),
            "--output-dir", str(pathlib.Path(tmpdir) / "out"),
            "--priority", "all",
        ])
        assert ret != 0

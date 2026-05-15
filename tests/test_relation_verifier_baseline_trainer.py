"""Tests for train_relation_verifier_baseline.py"""
from __future__ import annotations

import importlib.util as ilu
import json
import pathlib
import sys
import tempfile

import pytest

FORBIDDEN_IMPORTS = {"openai", "anthropic", "cohere", "requests", "httpx", "boto3"}


def _import_trainer():
    sys.path.insert(0, str(pathlib.Path("scripts").resolve().parent))
    spec = ilu.spec_from_file_location(
        "train_relation_verifier_baseline",
        "scripts/train_relation_verifier_baseline.py",
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixture: tiny training dataset
# ---------------------------------------------------------------------------

TINY_ROWS = [
    {
        "row_id": f"r{i}",
        "problem_id": f"pid{i}",
        "case_id": f"cid{i}",
        "split_group_id": "train",
        "feature_text": f"question: How many items? | candidate_answer: {i} | candidate_source: direct",
        "structured_features": {"question": f"How many items?", "candidate_answer": str(i)},
        "label": i % 2,
        "auxiliary_axis": "",
        "provenance": "fixture",
    }
    for i in range(10)
]


def write_jsonl(rows: list[dict], path: pathlib.Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_api_imports():
    src = pathlib.Path("scripts/train_relation_verifier_baseline.py").read_text()
    for lib in FORBIDDEN_IMPORTS:
        assert lib not in src, f"Forbidden import '{lib}' found in trainer"


def test_dry_run_no_training():
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(TINY_ROWS, jpath)
        ret = mod.main(
            ["--dataset-jsonl", str(jpath), "--output-dir", str(outdir), "--mode", "dry_run"]
        )
        assert ret == 0
        assert (outdir / "metrics.json").exists()
        assert (outdir / "training_report.md").exists()
        assert (outdir / "predictions.jsonl").exists()
        # No model in dry run
        assert not (outdir / "model.joblib").exists()


def test_dry_run_report_contains_warning():
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(TINY_ROWS, jpath)
        mod.main(
            ["--dataset-jsonl", str(jpath), "--output-dir", str(outdir), "--mode", "dry_run"]
        )
        report = (outdir / "training_report.md").read_text()
        assert "TINY" in report or "tiny" in report


def test_train_mode_writes_predictions():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(TINY_ROWS, jpath)
        ret = mod.main(
            [
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
            ]
        )
        assert ret == 0
        assert (outdir / "predictions.jsonl").exists()
        preds = []
        with open(outdir / "predictions.jsonl") as f:
            for line in f:
                line = line.strip()
                if line:
                    preds.append(json.loads(line))
        assert len(preds) == len(TINY_ROWS)


def test_train_mode_writes_metrics():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(TINY_ROWS, jpath)
        mod.main(
            [
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
            ]
        )
        metrics = json.loads((outdir / "metrics.json").read_text())
        assert "accuracy" in metrics
        assert "f1_macro" in metrics
        assert "warning" in metrics


def test_leakage_check_passes_clean_data():
    mod = _import_trainer()
    issues = mod.check_leakage(TINY_ROWS)
    assert issues == [], f"Unexpected leakage issues on clean data: {issues}"


def test_leakage_check_catches_forbidden_key():
    mod = _import_trainer()
    bad_rows = [
        {
            **TINY_ROWS[0],
            "feature_text": "gold_answer_metadata_only: 42 | question: How many?",
        }
    ]
    issues = mod.check_leakage(bad_rows)
    assert len(issues) > 0
    assert any("gold_answer_metadata_only" in issue for issue in issues)


def test_gold_answer_metadata_only_never_in_features():
    mod = _import_trainer()
    # Construct rows where structured_features has a forbidden key (simulates a bug in builder)
    bad_rows = [
        {
            **TINY_ROWS[0],
            "structured_features": {"gold_answer_metadata_only": "secret", "question": "Q"},
        }
    ]
    issues = mod.check_leakage(bad_rows)
    assert any("gold_answer_metadata_only" in i for i in issues)


def test_empty_dataset_returns_error():
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "empty.jsonl"
        jpath.write_text("")
        outdir = pathlib.Path(tmpdir) / "out"
        ret = mod.main(
            ["--dataset-jsonl", str(jpath), "--output-dir", str(outdir), "--mode", "dry_run"]
        )
        assert ret != 0


def test_missing_dataset_returns_error():
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        outdir = pathlib.Path(tmpdir) / "out"
        ret = mod.main(
            [
                "--dataset-jsonl", str(pathlib.Path(tmpdir) / "nonexistent.jsonl"),
                "--output-dir", str(outdir),
                "--mode", "dry_run",
            ]
        )
        assert ret != 0

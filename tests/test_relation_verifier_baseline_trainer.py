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


# ---------------------------------------------------------------------------
# Fixture: medium dataset with repeated problem_ids for grouped CV tests
# ---------------------------------------------------------------------------

# 40 rows, 10 problem groups of 4, balanced classes within each group
MEDIUM_ROWS = []
for pid in range(10):
    for case in range(4):
        row_idx = pid * 4 + case
        MEDIUM_ROWS.append({
            "row_id": f"m{row_idx}",
            "problem_id": f"mpid{pid}",
            "case_id": f"mcid{row_idx}",
            "split_group_id": "train",
            "feature_text": (
                f"question: How many left after removing {row_idx} from {100 + row_idx}? "
                f"| candidate_answer: {100} | candidate_source: direct"
            ),
            "structured_features": {
                "question": f"How many left? {row_idx}",
                "candidate_answer": str(100),
            },
            "label": row_idx % 2,
            "auxiliary_axis": "",
            "provenance": "fixture",
        })


# ---------------------------------------------------------------------------
# Confusion matrix
# ---------------------------------------------------------------------------

def test_train_metrics_contain_confusion_matrix():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(MEDIUM_ROWS, jpath)
        mod.main([
            "--dataset-jsonl", str(jpath),
            "--output-dir", str(outdir),
            "--mode", "train",
            "--seed", "42",
        ])
        metrics = json.loads((outdir / "metrics.json").read_text())
        assert "confusion_matrix" in metrics, "metrics.json must contain confusion_matrix"
        cm_info = metrics["confusion_matrix"]
        assert "matrix" in cm_info
        mat = cm_info["matrix"]
        assert len(mat) == 2 and len(mat[0]) == 2, "Confusion matrix must be 2×2"
        assert "label_names" in cm_info
        assert cm_info["label_names"] == ["not_ready", "ready"]


def test_train_report_contains_confusion_matrix_table():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(MEDIUM_ROWS, jpath)
        mod.main([
            "--dataset-jsonl", str(jpath),
            "--output-dir", str(outdir),
            "--mode", "train",
            "--seed", "42",
        ])
        report = (outdir / "training_report.md").read_text()
        assert "confusion matrix" in report.lower() or "Confusion matrix" in report


# ---------------------------------------------------------------------------
# PR-AUC
# ---------------------------------------------------------------------------

def test_train_metrics_contain_pr_auc():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(MEDIUM_ROWS, jpath)
        mod.main([
            "--dataset-jsonl", str(jpath),
            "--output-dir", str(outdir),
            "--mode", "train",
            "--seed", "42",
        ])
        metrics = json.loads((outdir / "metrics.json").read_text())
        assert "pr_auc_ready" in metrics, "metrics.json must contain pr_auc_ready"
        pr_auc = metrics["pr_auc_ready"]
        assert pr_auc is not None, "pr_auc_ready must not be None when predict_proba is available"
        assert 0.0 <= pr_auc <= 1.0, f"PR-AUC must be in [0, 1], got {pr_auc}"


def test_train_report_contains_pr_auc():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(MEDIUM_ROWS, jpath)
        mod.main([
            "--dataset-jsonl", str(jpath),
            "--output-dir", str(outdir),
            "--mode", "train",
            "--seed", "42",
        ])
        report = (outdir / "training_report.md").read_text()
        assert "PR-AUC" in report or "pr_auc" in report.lower()


# ---------------------------------------------------------------------------
# Threshold sweep
# ---------------------------------------------------------------------------

def test_threshold_sweep_returns_threshold_and_metrics():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(MEDIUM_ROWS, jpath)
        mod.main([
            "--dataset-jsonl", str(jpath),
            "--output-dir", str(outdir),
            "--mode", "train",
            "--seed", "42",
            "--threshold-sweep",
        ])
        metrics = json.loads((outdir / "metrics.json").read_text())
        ts = metrics.get("threshold_sweep")
        assert ts is not None, "threshold_sweep must be present when --threshold-sweep is passed"
        assert "best_threshold" in ts
        assert "best_ready_f1" in ts
        assert "best_macro_f1" in ts
        assert "sweep" in ts
        assert isinstance(ts["sweep"], list) and len(ts["sweep"]) > 0
        assert 0.0 < ts["best_threshold"] < 1.0


def test_threshold_sweep_absent_without_flag():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(MEDIUM_ROWS, jpath)
        mod.main([
            "--dataset-jsonl", str(jpath),
            "--output-dir", str(outdir),
            "--mode", "train",
            "--seed", "42",
        ])
        metrics = json.loads((outdir / "metrics.json").read_text())
        assert metrics.get("threshold_sweep") is None


def test_threshold_sweep_report_contains_best_threshold():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(MEDIUM_ROWS, jpath)
        mod.main([
            "--dataset-jsonl", str(jpath),
            "--output-dir", str(outdir),
            "--mode", "train",
            "--seed", "42",
            "--threshold-sweep",
        ])
        report = (outdir / "training_report.md").read_text()
        assert "threshold" in report.lower()
        assert "post-hoc" in report.lower() or "diagnostic" in report.lower(), (
            "Report must note that sweep is post-hoc/diagnostic")


# ---------------------------------------------------------------------------
# Grouped CV
# ---------------------------------------------------------------------------

def test_grouped_cv_uses_problem_id():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(MEDIUM_ROWS, jpath)
        ret = mod.main([
            "--dataset-jsonl", str(jpath),
            "--output-dir", str(outdir),
            "--mode", "train",
            "--seed", "42",
            "--grouped-cv",
        ])
        assert ret == 0
        metrics = json.loads((outdir / "metrics.json").read_text())
        assert metrics.get("grouped_cv") is True
        assert metrics.get("group_field") == "problem_id", (
            f"Expected group_field=problem_id, got {metrics.get('group_field')!r}")


def test_grouped_cv_fallback_when_no_group_field():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows_no_pid = [
        {k: v for k, v in r.items() if k not in ("problem_id", "case_id")}
        for r in MEDIUM_ROWS
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows_no_pid, jpath)
        import io
        captured = io.StringIO()
        import warnings as _warnings
        with _warnings.catch_warnings(record=True) as w:
            _warnings.simplefilter("always")
            ret = mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
                "--grouped-cv",
            ])
        assert ret == 0
        # Warning must have been issued or metrics must note the fallback
        metrics = json.loads((outdir / "metrics.json").read_text())
        # group_field should be None (fell back to standard CV)
        assert metrics.get("group_field") is None
        assert metrics.get("grouped_cv_warning") is not None, (
            "grouped_cv_warning must be set when no group field found")


def test_dry_run_no_training_with_new_flags():
    """dry_run must still produce no model when new flags are passed."""
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(MEDIUM_ROWS, jpath)
        ret = mod.main([
            "--dataset-jsonl", str(jpath),
            "--output-dir", str(outdir),
            "--mode", "dry_run",
            "--grouped-cv",
            "--threshold-sweep",
        ])
        assert ret == 0
        assert not (outdir / "model.joblib").exists(), "dry_run must not save a model"


def test_predictions_contain_proba_ready():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(MEDIUM_ROWS, jpath)
        mod.main([
            "--dataset-jsonl", str(jpath),
            "--output-dir", str(outdir),
            "--mode", "train",
            "--seed", "42",
        ])
        preds = []
        with open(outdir / "predictions.jsonl") as f:
            for line in f:
                if line.strip():
                    preds.append(json.loads(line))
        assert len(preds) == len(MEDIUM_ROWS)
        for p in preds:
            assert "proba_ready" in p, "Each prediction must include proba_ready"
            if p["proba_ready"] is not None:
                assert 0.0 <= p["proba_ready"] <= 1.0

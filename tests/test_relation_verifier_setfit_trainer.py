"""Tests for train_relation_verifier_setfit.py

All tests mock SetFitModel and Trainer so they do not download models
or require a GPU.
"""
from __future__ import annotations

import importlib.util as ilu
import json
import pathlib
import sys
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

FORBIDDEN_IMPORTS = {"openai", "anthropic", "cohere", "requests", "httpx", "boto3"}
WORKTREE_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _import_trainer():
    script = WORKTREE_ROOT / "scripts" / "train_relation_verifier_setfit.py"
    spec = ilu.spec_from_file_location("train_relation_verifier_setfit", script)
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_rows(n: int = 40, n_problems: int = 10) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append({
            "row_id": f"r{i}",
            "problem_id": f"pid{i % n_problems}",
            "case_id": f"cid{i}",
            "split_group_id": "train",
            "feature_text": (
                f"question: How many? | candidate_answer: {i} | candidate_source: direct"
            ),
            "structured_features": {"question": "How many?", "candidate_answer": str(i)},
            "label": i % 2,
            "auxiliary_axis": "",
            "provenance": "fixture",
        })
    return rows


def write_jsonl(rows: list[dict], path: pathlib.Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _fake_proba(val_texts):
    """Return deterministic fake probability scores."""
    rng = np.random.default_rng(42)
    n = len(val_texts)
    raw = rng.random(n)
    # Return as (n, 2) array so column 1 is proba_ready
    return np.column_stack([1 - raw, raw])


def _mock_train_fold(mod):
    """Patch _train_fold to return fake OOF scores without running SetFit."""
    def fake_train_fold(train_texts, train_labels, val_texts, **kwargs):
        proba = _fake_proba(val_texts)
        proba_ready = proba[:, 1].tolist()
        preds = [1 if s >= 0.5 else 0 for s in proba_ready]
        return proba_ready, preds
    return patch.object(mod, "_train_fold", side_effect=fake_train_fold)


# ---------------------------------------------------------------------------
# No forbidden provider API imports
# ---------------------------------------------------------------------------

def test_no_api_imports():
    src = (WORKTREE_ROOT / "scripts" / "train_relation_verifier_setfit.py").read_text()
    for lib in FORBIDDEN_IMPORTS:
        assert lib not in src, f"Forbidden import '{lib}' found in script"


# ---------------------------------------------------------------------------
# Dry run does not train
# ---------------------------------------------------------------------------

def test_dry_run_does_not_call_train_fold():
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)

        called = []
        original = mod._train_fold
        def patched(*a, **kw):
            called.append(True)
            return original(*a, **kw)
        mod._train_fold = patched
        try:
            ret = mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "dry_run",
            ])
        finally:
            mod._train_fold = original

        assert ret == 0
        assert not called, "dry_run must not invoke _train_fold"


def test_dry_run_creates_expected_files():
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        ret = mod.main([
            "--dataset-jsonl", str(jpath),
            "--output-dir", str(outdir),
            "--mode", "dry_run",
        ])
        assert ret == 0
        assert (outdir / "metrics.json").exists()
        assert (outdir / "training_report.md").exists()
        assert (outdir / "predictions.jsonl").exists()
        assert not (outdir / "run_manifest.json").exists()


# ---------------------------------------------------------------------------
# Gold fields excluded from features
# ---------------------------------------------------------------------------

def test_gold_fields_not_in_clean_rows():
    mod = _import_trainer()
    rows = _make_rows(10)
    issues = mod.check_leakage(rows)
    assert issues == []


def test_gold_field_in_feature_text_detected():
    mod = _import_trainer()
    rows = _make_rows(5)
    rows[0]["feature_text"] = "gold_answer_metadata_only: 42 | question: How many?"
    issues = mod.check_leakage(rows)
    assert any("gold_answer_metadata_only" in i for i in issues)


def test_gold_field_in_structured_features_detected():
    mod = _import_trainer()
    rows = _make_rows(5)
    rows[0]["structured_features"]["notes_manual"] = "secret"
    issues = mod.check_leakage(rows)
    assert any("notes_manual" in i for i in issues)


def test_leakage_aborts_training():
    mod = _import_trainer()
    rows = _make_rows(10)
    rows[0]["feature_text"] = "relation_ready_label_manual: ready | question: Q"
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        ret = mod.main([
            "--dataset-jsonl", str(jpath),
            "--output-dir", str(outdir),
            "--mode", "train",
        ])
        assert ret != 0


# ---------------------------------------------------------------------------
# Grouped CV avoids group leakage
# ---------------------------------------------------------------------------

def test_grouped_cv_uses_problem_id():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40, n_problems=10)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        with _mock_train_fold(mod):
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
        assert metrics.get("group_field") == "problem_id"


def test_grouped_cv_fallback_without_group_fields():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    rows_no_grp = [{k: v for k, v in r.items() if k not in ("problem_id", "case_id")} for r in rows]
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows_no_grp, jpath)
        import warnings as _w
        with _mock_train_fold(mod), _w.catch_warnings(record=True):
            _w.simplefilter("always")
            ret = mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
                "--grouped-cv",
            ])
        assert ret == 0
        metrics = json.loads((outdir / "metrics.json").read_text())
        assert metrics.get("group_field") is None
        assert metrics.get("grouped_cv_warning") is not None


# ---------------------------------------------------------------------------
# Metrics include PR-AUC and confusion matrix
# ---------------------------------------------------------------------------

def test_metrics_contain_pr_auc():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        with _mock_train_fold(mod):
            mod.main(["--dataset-jsonl", str(jpath), "--output-dir", str(outdir), "--mode", "train", "--seed", "42"])
        metrics = json.loads((outdir / "metrics.json").read_text())
        assert "pr_auc_ready" in metrics
        pr_auc = metrics["pr_auc_ready"]
        assert pr_auc is not None
        assert 0.0 <= pr_auc <= 1.0


def test_metrics_contain_confusion_matrix():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        with _mock_train_fold(mod):
            mod.main(["--dataset-jsonl", str(jpath), "--output-dir", str(outdir), "--mode", "train", "--seed", "42"])
        metrics = json.loads((outdir / "metrics.json").read_text())
        assert "confusion_matrix" in metrics
        cm_info = metrics["confusion_matrix"]
        assert "matrix" in cm_info
        mat = cm_info["matrix"]
        assert len(mat) == 2 and len(mat[0]) == 2
        assert cm_info["label_names"] == ["not_ready", "ready"]


# ---------------------------------------------------------------------------
# Threshold sweep
# ---------------------------------------------------------------------------

def test_threshold_sweep_present_when_requested():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        with _mock_train_fold(mod):
            mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
                "--threshold-sweep",
            ])
        metrics = json.loads((outdir / "metrics.json").read_text())
        ts = metrics.get("threshold_sweep")
        assert ts is not None
        assert "best_threshold" in ts
        assert "best_ready_f1" in ts
        assert "sweep" in ts and len(ts["sweep"]) > 0


def test_threshold_sweep_absent_without_flag():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        with _mock_train_fold(mod):
            mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
            ])
        metrics = json.loads((outdir / "metrics.json").read_text())
        assert metrics.get("threshold_sweep") is None


# ---------------------------------------------------------------------------
# Output files created in train mode
# ---------------------------------------------------------------------------

def test_train_mode_creates_all_output_files():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        with _mock_train_fold(mod):
            ret = mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
            ])
        assert ret == 0
        for fname in ("metrics.json", "training_report.md", "predictions.jsonl", "run_manifest.json"):
            assert (outdir / fname).exists(), f"Expected {fname} in output dir"


def test_predictions_count_matches_input_rows():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        with _mock_train_fold(mod):
            mod.main(["--dataset-jsonl", str(jpath), "--output-dir", str(outdir), "--mode", "train", "--seed", "42"])
        preds = [json.loads(l) for l in (outdir / "predictions.jsonl").open() if l.strip()]
        assert len(preds) == len(rows)
        for p in preds:
            assert "proba_ready" in p


# ---------------------------------------------------------------------------
# --limit-rows smoke test
# ---------------------------------------------------------------------------

def test_limit_rows_truncates_dataset():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        with _mock_train_fold(mod):
            ret = mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
                "--limit-rows", "20",
            ])
        assert ret == 0
        metrics = json.loads((outdir / "metrics.json").read_text())
        assert metrics["n_samples"] == 20


def test_limit_rows_dry_run():
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        ret = mod.main([
            "--dataset-jsonl", str(jpath),
            "--output-dir", str(outdir),
            "--mode", "dry_run",
            "--limit-rows", "10",
        ])
        assert ret == 0
        m = json.loads((outdir / "metrics.json").read_text())
        assert m["total_rows"] == 10


# ---------------------------------------------------------------------------
# Model artifacts stay under output dir
# ---------------------------------------------------------------------------

def test_model_artifacts_stay_under_output_dir():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)

        fold_output_dirs = []
        original_train_fold = mod._train_fold

        def tracking_train_fold(*args, **kwargs):
            od = kwargs.get("output_dir", pathlib.Path(tmpdir))
            fold_output_dirs.append(od)
            proba_ready, preds = _fake_proba(kwargs.get("val_texts", [None])), []
            val_texts = kwargs.get("val_texts", [])
            pr = _fake_proba(val_texts)[:, 1].tolist()
            pd_ = [1 if s >= 0.5 else 0 for s in pr]
            return pr, pd_

        mod._train_fold = tracking_train_fold
        try:
            mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
            ])
        finally:
            mod._train_fold = original_train_fold

        for od in fold_output_dirs:
            assert str(od).startswith(str(outdir)), (
                f"Fold output dir {od!r} is outside output_dir {outdir!r}"
            )

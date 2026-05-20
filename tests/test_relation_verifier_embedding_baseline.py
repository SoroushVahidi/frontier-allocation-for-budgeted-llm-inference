"""Tests for train_relation_verifier_embedding_baseline.py

All tests mock or stub the SentenceTransformer model so they do not
download models or require a GPU.
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
    script_path = WORKTREE_ROOT / "scripts" / "train_relation_verifier_embedding_baseline.py"
    spec = ilu.spec_from_file_location("train_relation_verifier_embedding_baseline", script_path)
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_rows(n: int = 20, n_problems: int = 5) -> list[dict]:
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


def _fake_encode(texts, batch_size=32, show_progress_bar=False,
                 convert_to_numpy=True, normalize_embeddings=False):
    """Return deterministic fake 16-dim embeddings."""
    rng = np.random.default_rng(42)
    return rng.standard_normal((len(texts), 16)).astype(np.float32)


def _mock_sentence_transformer():
    """Return a mock SentenceTransformer that uses _fake_encode."""
    mock_model = MagicMock()
    mock_model.encode = _fake_encode
    return mock_model


# ---------------------------------------------------------------------------
# Task A-style check: no forbidden imports in source
# ---------------------------------------------------------------------------

def test_no_api_imports():
    src = (WORKTREE_ROOT / "scripts" / "train_relation_verifier_embedding_baseline.py").read_text()
    for lib in FORBIDDEN_IMPORTS:
        assert lib not in src, f"Forbidden import '{lib}' found in script"


# ---------------------------------------------------------------------------
# Dry run does not embed or train
# ---------------------------------------------------------------------------

def test_dry_run_avoids_embedding_and_training():
    mod = _import_trainer()
    rows = _make_rows(20)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)

        embed_called = []

        original_embed = mod._embed

        def patched_embed(*args, **kwargs):
            embed_called.append(True)
            return original_embed(*args, **kwargs)

        mod._embed = patched_embed
        try:
            ret = mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "dry_run",
            ])
        finally:
            mod._embed = original_embed

        assert ret == 0
        assert not embed_called, "dry_run must not call _embed"
        assert not (outdir / "embeddings_cache.npy").exists()
        assert (outdir / "metrics.json").exists()
        assert (outdir / "training_report.md").exists()


def test_dry_run_writes_expected_files():
    mod = _import_trainer()
    rows = _make_rows(20)
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
# Gold fields not used as features
# ---------------------------------------------------------------------------

def test_gold_fields_not_in_features():
    mod = _import_trainer()
    rows = _make_rows(20)
    issues = mod.check_leakage(rows)
    assert issues == [], f"Clean rows should have no leakage issues: {issues}"


def test_gold_field_in_feature_text_detected():
    mod = _import_trainer()
    bad_rows = _make_rows(2)
    bad_rows[0]["feature_text"] = "gold_answer_metadata_only: 42 | question: How many?"
    issues = mod.check_leakage(bad_rows)
    assert any("gold_answer_metadata_only" in i for i in issues)


def test_gold_field_in_structured_features_detected():
    mod = _import_trainer()
    bad_rows = _make_rows(2)
    bad_rows[0]["structured_features"]["relation_ready_label_manual"] = "ready"
    issues = mod.check_leakage(bad_rows)
    assert any("relation_ready_label_manual" in i for i in issues)


def test_leakage_aborts_training():
    mod = _import_trainer()
    rows = _make_rows(10)
    rows[0]["feature_text"] = "notes_manual: secret info | question: How many?"
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        ret = mod.main([
            "--dataset-jsonl", str(jpath),
            "--output-dir", str(outdir),
            "--mode", "train",
        ])
        assert ret != 0, "Training must fail when leakage is detected"


# ---------------------------------------------------------------------------
# Grouped CV does not leak across groups
# ---------------------------------------------------------------------------

def test_grouped_cv_uses_problem_id():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40, n_problems=10)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        embeddings = _fake_encode([r["feature_text"] for r in rows])

        with patch.object(mod, "_embed", return_value=embeddings):
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


def test_grouped_cv_fallback_when_no_group_field():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    rows_no_pid = [{k: v for k, v in r.items() if k not in ("problem_id", "case_id")} for r in rows]

    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows_no_pid, jpath)
        embeddings = _fake_encode([r["feature_text"] for r in rows_no_pid])

        import warnings as _warnings
        with patch.object(mod, "_embed", return_value=embeddings):
            with _warnings.catch_warnings(record=True):
                _warnings.simplefilter("always")
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
# Metrics include confusion matrix and PR-AUC
# ---------------------------------------------------------------------------

def test_metrics_contain_confusion_matrix():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        embeddings = _fake_encode([r["feature_text"] for r in rows])

        with patch.object(mod, "_embed", return_value=embeddings):
            mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
            ])
        metrics = json.loads((outdir / "metrics.json").read_text())
        assert "confusion_matrix" in metrics
        cm_info = metrics["confusion_matrix"]
        assert "matrix" in cm_info
        mat = cm_info["matrix"]
        assert len(mat) == 2 and len(mat[0]) == 2
        assert cm_info["label_names"] == ["not_ready", "ready"]


def test_metrics_contain_pr_auc():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        embeddings = _fake_encode([r["feature_text"] for r in rows])

        with patch.object(mod, "_embed", return_value=embeddings):
            mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
            ])
        metrics = json.loads((outdir / "metrics.json").read_text())
        assert "pr_auc_ready" in metrics
        pr_auc = metrics["pr_auc_ready"]
        assert pr_auc is not None
        assert 0.0 <= pr_auc <= 1.0


# ---------------------------------------------------------------------------
# logreg path with fake embeddings
# ---------------------------------------------------------------------------

def test_logreg_path_works():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        embeddings = _fake_encode([r["feature_text"] for r in rows])

        with patch.object(mod, "_embed", return_value=embeddings):
            ret = mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--classifier", "logreg",
                "--seed", "42",
            ])
        assert ret == 0
        metrics = json.loads((outdir / "metrics.json").read_text())
        assert "accuracy" in metrics
        assert "f1_macro" in metrics


# ---------------------------------------------------------------------------
# linear_svm path with fake embeddings
# ---------------------------------------------------------------------------

def test_linear_svm_path_works():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        embeddings = _fake_encode([r["feature_text"] for r in rows])

        with patch.object(mod, "_embed", return_value=embeddings):
            ret = mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--classifier", "linear_svm",
                "--seed", "42",
            ])
        assert ret == 0
        metrics = json.loads((outdir / "metrics.json").read_text())
        assert "accuracy" in metrics
        # SVM produces scores via decision_function; pr_auc should still be present
        assert "pr_auc_ready" in metrics


def test_linear_svm_predictions_contain_score_ready():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        embeddings = _fake_encode([r["feature_text"] for r in rows])

        with patch.object(mod, "_embed", return_value=embeddings):
            mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--classifier", "linear_svm",
                "--seed", "42",
            ])
        preds = []
        with open(outdir / "predictions.jsonl") as f:
            for line in f:
                if line.strip():
                    preds.append(json.loads(line))
        assert len(preds) == len(rows)
        for p in preds:
            assert "score_ready" in p


# ---------------------------------------------------------------------------
# Threshold sweep
# ---------------------------------------------------------------------------

def test_threshold_sweep_works():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        embeddings = _fake_encode([r["feature_text"] for r in rows])

        with patch.object(mod, "_embed", return_value=embeddings):
            ret = mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
                "--threshold-sweep",
            ])
        assert ret == 0
        metrics = json.loads((outdir / "metrics.json").read_text())
        ts = metrics.get("threshold_sweep")
        assert ts is not None
        assert "best_threshold" in ts
        assert "best_ready_f1" in ts
        assert "sweep" in ts
        assert isinstance(ts["sweep"], list) and len(ts["sweep"]) > 0
        assert 0.0 < ts["best_threshold"] < 1.0


def test_threshold_sweep_absent_without_flag():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        embeddings = _fake_encode([r["feature_text"] for r in rows])

        with patch.object(mod, "_embed", return_value=embeddings):
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
        embeddings = _fake_encode([r["feature_text"] for r in rows])

        with patch.object(mod, "_embed", return_value=embeddings):
            ret = mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
            ])
        assert ret == 0
        assert (outdir / "metrics.json").exists()
        assert (outdir / "training_report.md").exists()
        assert (outdir / "predictions.jsonl").exists()
        assert (outdir / "run_manifest.json").exists()


def test_predictions_count_matches_rows():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        embeddings = _fake_encode([r["feature_text"] for r in rows])

        with patch.object(mod, "_embed", return_value=embeddings):
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
        assert len(preds) == len(rows)


# ---------------------------------------------------------------------------
# Cache path must stay under output dir
# ---------------------------------------------------------------------------

def test_cache_path_under_output_dir():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)

        embed_calls = []
        original_embed = mod._embed

        def patched_embed(texts, model_name, device, batch_size, output_dir, use_cache):
            embed_calls.append(str(output_dir))
            # Return fake embeddings without actually loading a model
            return _fake_encode(texts)

        mod._embed = patched_embed
        try:
            mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
                "--cache-embeddings",
            ])
        finally:
            mod._embed = original_embed

        # Verify _embed was called with output_dir == outdir
        assert len(embed_calls) == 1
        assert embed_calls[0] == str(outdir)


def test_cache_file_written_under_output_dir():
    pytest.importorskip("sklearn")
    mod = _import_trainer()
    rows = _make_rows(40)
    with tempfile.TemporaryDirectory() as tmpdir:
        jpath = pathlib.Path(tmpdir) / "rows.jsonl"
        outdir = pathlib.Path(tmpdir) / "out"
        write_jsonl(rows, jpath)
        embeddings = _fake_encode([r["feature_text"] for r in rows])
        outdir.mkdir(parents=True, exist_ok=True)
        cache_path = outdir / "embeddings_cache.npy"
        np.save(str(cache_path), embeddings)

        # With cache already written, _embed should load it and not re-encode
        with patch.object(mod, "_embed", return_value=embeddings) as mock_embed:
            mod.main([
                "--dataset-jsonl", str(jpath),
                "--output-dir", str(outdir),
                "--mode", "train",
                "--seed", "42",
                "--cache-embeddings",
            ])

        # Cache file must be inside output dir, not in /tmp or elsewhere
        assert not cache_path.is_symlink()
        resolved = cache_path.resolve()
        assert str(resolved).startswith(str(outdir.resolve()))

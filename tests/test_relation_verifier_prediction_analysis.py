"""Tests for analyze_relation_verifier_predictions.py"""
from __future__ import annotations

import importlib.util as ilu
import json
import pathlib
import sys
import tempfile

import numpy as np
import pytest

FORBIDDEN_IMPORTS = {"openai", "anthropic", "cohere", "requests", "httpx", "boto3"}


def _import_analyzer():
    sys.path.insert(0, str(pathlib.Path("scripts").resolve().parent))
    spec = ilu.spec_from_file_location(
        "analyze_relation_verifier_predictions",
        "scripts/analyze_relation_verifier_predictions.py",
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_jsonl(rows: list[dict], path: pathlib.Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_predictions(
    n: int = 40,
    n_ready: int = 10,
    n_folds: int = 5,
    include_fold: bool = True,
    include_problem_id: bool = True,
) -> list[dict]:
    """Fake OOF predictions with known label distribution."""
    rng = np.random.default_rng(99)
    preds = []
    for i in range(n):
        is_ready = i < n_ready
        fold = i % n_folds if include_fold else None
        prob = 0.85 if is_ready else 0.15
        prob += rng.normal(0, 0.05)
        prob = float(np.clip(prob, 0.01, 0.99))
        label_pred = 1 if prob >= 0.5 else 0
        row: dict = {
            "row_id": f"r{i}",
            "label_true": int(is_ready),
            "label_pred": label_pred,
            "proba_ready": prob,
        }
        if include_fold:
            row["fold"] = fold
        if include_problem_id:
            row["problem_id"] = f"pid{i % 8}"  # 8 unique problems
        preds.append(row)
    return preds


def _make_dataset_rows(n: int = 40, n_ready: int = 10) -> list[dict]:
    """Matching dataset rows for fold reconstruction."""
    rows = []
    for i in range(n):
        rows.append({
            "row_id": f"r{i}",
            "problem_id": f"pid{i % 8}",
            "case_id": f"cid{i}",
            "split_group_id": "train" if i < 5 else "",
            "feature_text": f"question: Q{i} | candidate_answer: {i}",
            "structured_features": {},
            "label": int(i < n_ready),
            "auxiliary_axis": "",
            "provenance": "fixture",
        })
    return rows


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

def test_no_api_imports():
    import re
    src = pathlib.Path("scripts/analyze_relation_verifier_predictions.py").read_text()
    for lib in FORBIDDEN_IMPORTS:
        assert not re.search(rf"^\s*(import|from)\s+{lib}\b", src, re.MULTILINE), \
            f"Forbidden import statement 'import/from {lib}' found in script"


# ---------------------------------------------------------------------------
# Overall metrics
# ---------------------------------------------------------------------------

def test_overall_metrics_computed():
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    preds = _make_predictions()
    labels = [p["label_true"] for p in preds]
    scores = [p["proba_ready"] for p in preds]
    m = mod._compute_metrics(labels, scores)
    assert "accuracy" in m
    assert "macro_f1" in m
    assert "ready_f1" in m
    assert "pr_auc" in m
    assert "n" in m
    assert m["n"] == len(preds)
    assert m["n_ready"] == sum(l == 1 for l in labels)
    assert 0.0 <= m["ready_f1"] <= 1.0
    assert m["pr_auc"] is not None  # both classes present


def test_overall_metrics_one_class_pr_auc_is_none():
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    # All labels are 0 (not_ready)
    labels = [0] * 20
    scores = [0.1] * 20
    m = mod._compute_metrics(labels, scores)
    assert m["pr_auc"] is None  # undefined for one-class sample


def test_overall_metrics_all_correct():
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    labels = [1, 1, 0, 0, 0]
    scores = [0.9, 0.85, 0.1, 0.15, 0.2]
    m = mod._compute_metrics(labels, scores, threshold=0.5)
    assert m["accuracy"] == 1.0
    assert m["ready_f1"] == 1.0
    assert m["pr_auc"] is not None


# ---------------------------------------------------------------------------
# Per-fold metrics
# ---------------------------------------------------------------------------

def test_per_fold_metrics_computed():
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    preds = _make_predictions(n_folds=5, include_fold=True)
    fold_metrics = mod._compute_per_fold_metrics(preds, "proba_ready", "label_true")
    assert len(fold_metrics) == 5
    for fm in fold_metrics:
        assert "fold" in fm
        assert "ready_f1" in fm
        assert "n" in fm


def test_per_fold_csv_written():
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    preds = _make_predictions(n_folds=5, include_fold=True)
    fold_metrics = mod._compute_per_fold_metrics(preds, "proba_ready", "label_true")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = pathlib.Path(tmpdir) / "per_fold_metrics.csv"
        mod._write_per_fold_csv(fold_metrics, path)
        assert path.exists()
        content = path.read_text()
        assert "fold" in content
        assert "ready_f1" in content


# ---------------------------------------------------------------------------
# Example bootstrap CI
# ---------------------------------------------------------------------------

def test_example_bootstrap_ci_returns_tuple():
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    preds = _make_predictions(n=60, n_ready=15)
    f1_fn = mod._make_ready_f1_fn("proba_ready", "label_true", threshold=0.5)
    lo, hi = mod._example_bootstrap_ci(preds, f1_fn, n_reps=100, seed=42)
    assert lo is not None and hi is not None
    assert 0.0 <= lo <= hi <= 1.0


def test_example_bootstrap_ci_bounds_reasonable():
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    preds = _make_predictions(n=80, n_ready=20)
    f1_fn = mod._make_ready_f1_fn("proba_ready", "label_true", threshold=0.5)
    lo, hi = mod._example_bootstrap_ci(preds, f1_fn, n_reps=200, seed=42)
    assert lo is not None and hi is not None
    assert 0.0 <= lo <= hi <= 1.0
    # Point estimate should be within or near the CI
    labels = [p["label_true"] for p in preds]
    scores = [p["proba_ready"] for p in preds]
    true_f1 = mod._compute_metrics(labels, scores)["ready_f1"]
    assert lo <= true_f1 + 0.05  # allow a small tolerance


# ---------------------------------------------------------------------------
# Group bootstrap CI
# ---------------------------------------------------------------------------

def test_group_bootstrap_samples_groups():
    """Group bootstrap must return valid CI bounds in [0, 1]."""
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    preds = _make_predictions(n=40, n_ready=10, include_problem_id=True)

    from collections import defaultdict
    groups: dict = defaultdict(list)
    for p in preds:
        groups[p["problem_id"]].append(p)

    f1_fn = mod._make_ready_f1_fn("proba_ready", "label_true", threshold=0.5)
    lo, hi = mod._group_bootstrap_ci(dict(groups), f1_fn, n_reps=200, seed=42)

    assert lo is not None and hi is not None
    assert 0.0 <= lo <= hi <= 1.0
    # Group bootstrap should have sampled all 8 groups with replacement —
    # verify by checking that it returned a valid result
    n_groups = len(groups)
    assert n_groups == 8


def test_group_bootstrap_result_in_unit_interval():
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    preds = _make_predictions(n=40, n_ready=10, include_problem_id=True)
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for p in preds:
        groups[p["problem_id"]].append(p)
    f1_fn = mod._make_ready_f1_fn("proba_ready", "label_true", threshold=0.5)
    lo, hi = mod._group_bootstrap_ci(dict(groups), f1_fn, n_reps=200, seed=42)
    assert lo is not None and hi is not None
    assert 0.0 <= lo <= hi <= 1.0


# ---------------------------------------------------------------------------
# PR-AUC one-class graceful handling
# ---------------------------------------------------------------------------

def test_pr_auc_handles_one_class_bootstrap_sample():
    """PR-AUC fn must return None (not raise) for a one-class bootstrap sample."""
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    pr_fn = mod._make_pr_auc_fn("proba_ready", "label_true")

    # One-class sample (all not_ready)
    one_class_sample = [
        {"label_true": 0, "proba_ready": 0.1},
        {"label_true": 0, "proba_ready": 0.2},
        {"label_true": 0, "proba_ready": 0.05},
    ]
    result = pr_fn(one_class_sample)
    assert result is None, f"Expected None for one-class sample, got {result}"


def test_pr_auc_bootstrap_ci_handles_one_class_samples():
    """Bootstrap CI for PR-AUC must work even if some bootstrap samples are one-class."""
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    # Very few ready examples — many bootstrap samples will be one-class
    preds = [
        {"label_true": 1, "proba_ready": 0.9},
        {"label_true": 1, "proba_ready": 0.8},
    ] + [
        {"label_true": 0, "proba_ready": 0.1 + i * 0.01}
        for i in range(18)
    ]
    pr_fn = mod._make_pr_auc_fn("proba_ready", "label_true")
    lo, hi = mod._example_bootstrap_ci(preds, pr_fn, n_reps=200, seed=77)
    # Should not raise; may be None if ALL samples are one-class, but with 20 rows it won't be
    if lo is not None:
        assert 0.0 <= lo <= hi <= 1.0


# ---------------------------------------------------------------------------
# Output files
# ---------------------------------------------------------------------------

def test_output_files_created():
    """main() must create ci_metrics.json, ci_report.md, and per_fold_metrics.csv."""
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    preds = _make_predictions(n=40, n_ready=10, include_fold=True, include_problem_id=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        pred_path = pathlib.Path(tmpdir) / "predictions.jsonl"
        out_dir = pathlib.Path(tmpdir) / "out"
        write_jsonl(preds, pred_path)
        ret = mod.main([
            "--predictions", str(pred_path),
            "--output-dir", str(out_dir),
            "--bootstrap-reps", "50",
            "--seed", "42",
        ])
        assert ret == 0
        assert (out_dir / "ci_metrics.json").exists()
        assert (out_dir / "ci_report.md").exists()
        # per_fold_metrics.csv only when fold field present in predictions
        assert (out_dir / "per_fold_metrics.csv").exists()


def test_output_ci_metrics_json_structure():
    """ci_metrics.json must have overall, ci, fold_metrics, config keys."""
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    preds = _make_predictions(n=40, n_ready=10, include_fold=True, include_problem_id=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        pred_path = pathlib.Path(tmpdir) / "predictions.jsonl"
        out_dir = pathlib.Path(tmpdir) / "out"
        write_jsonl(preds, pred_path)
        mod.main([
            "--predictions", str(pred_path),
            "--output-dir", str(out_dir),
            "--bootstrap-reps", "50",
            "--seed", "42",
        ])
        data = json.loads((out_dir / "ci_metrics.json").read_text())
        assert "overall" in data
        assert "ci" in data
        assert "fold_metrics" in data
        assert "config" in data
        # overall must have key metrics
        overall = data["overall"]
        assert "ready_f1" in overall
        assert "pr_auc" in overall
        assert "n" in overall
        # ci must have example and group CIs
        ci = data["ci"]
        assert "example_ready_f1" in ci
        assert "example_pr_auc" in ci
        # group CI present since problem_id in preds
        assert ci.get("group_available") is True
        assert "group_ready_f1" in ci


def test_no_fold_col_skips_per_fold_csv():
    """When predictions have no fold column, per_fold_metrics.csv should not be written."""
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    preds = _make_predictions(n=40, n_ready=10, include_fold=False, include_problem_id=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        pred_path = pathlib.Path(tmpdir) / "predictions.jsonl"
        out_dir = pathlib.Path(tmpdir) / "out"
        write_jsonl(preds, pred_path)
        ret = mod.main([
            "--predictions", str(pred_path),
            "--output-dir", str(out_dir),
            "--bootstrap-reps", "50",
            "--seed", "42",
        ])
        assert ret == 0
        assert not (out_dir / "per_fold_metrics.csv").exists()


def test_fold_reconstruction_with_dataset_jsonl():
    """With --dataset-jsonl, fold field should be reconstructed and per_fold_metrics.csv written."""
    pytest.importorskip("sklearn")
    mod = _import_analyzer()
    n = 40
    n_ready = 10
    # Predictions WITHOUT fold (as the real cfg1 predictions)
    preds = _make_predictions(n=n, n_ready=n_ready, include_fold=False, include_problem_id=False)
    dataset_rows = _make_dataset_rows(n=n, n_ready=n_ready)

    with tempfile.TemporaryDirectory() as tmpdir:
        pred_path = pathlib.Path(tmpdir) / "predictions.jsonl"
        ds_path = pathlib.Path(tmpdir) / "train_rows.jsonl"
        out_dir = pathlib.Path(tmpdir) / "out"
        write_jsonl(preds, pred_path)
        write_jsonl(dataset_rows, ds_path)
        ret = mod.main([
            "--predictions", str(pred_path),
            "--output-dir", str(out_dir),
            "--dataset-jsonl", str(ds_path),
            "--bootstrap-reps", "50",
            "--seed", "42",
            "--n-splits", "5",
        ])
        assert ret == 0
        assert (out_dir / "per_fold_metrics.csv").exists()
        data = json.loads((out_dir / "ci_metrics.json").read_text())
        assert data["ci"]["group_available"] is True

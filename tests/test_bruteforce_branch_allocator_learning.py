from __future__ import annotations

import json
from pathlib import Path

from experiments.bruteforce_branch_allocator import (
    ALLOC_FEATURE_NAMES,
    LearningConfig,
    build_candidate_feature_vector,
    evaluate_models,
    load_label_artifacts,
    prepare_learning_tables,
    train_models,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _tiny_artifacts(tmp_path: Path) -> Path:
    labels_dir = tmp_path / "labels"
    candidate_rows = [
        {
            "state_id": "s0",
            "example_id": "e0",
            "dataset_name": "mock",
            "remaining_budget": 3,
            "branch_id": "b0",
            "estimated_value_if_allocate_next": 0.9,
            "allocation_candidates_evaluated": 4,
            "allocation_value_std": 0.02,
            "mode": "exact",
            "branch_vs_outside_gap": 0.3,
            "features_branch_v1": {
                "score": 0.9,
                "depth": 2,
                "stalled_steps": 0,
                "recent_delta": 0.06,
                "verify_count": 1,
                "branch_age": 2,
                "parent_relative_score": 0.2,
            },
        },
        {
            "state_id": "s0",
            "example_id": "e0",
            "dataset_name": "mock",
            "remaining_budget": 3,
            "branch_id": "b1",
            "estimated_value_if_allocate_next": 0.6,
            "allocation_candidates_evaluated": 4,
            "allocation_value_std": 0.02,
            "mode": "exact",
            "branch_vs_outside_gap": -0.3,
            "features_branch_v1": {
                "score": 0.55,
                "depth": 2,
                "stalled_steps": 1,
                "recent_delta": -0.01,
                "verify_count": 0,
                "branch_age": 2,
                "parent_relative_score": -0.2,
            },
        },
        {
            "state_id": "s1",
            "example_id": "e1",
            "dataset_name": "mock",
            "remaining_budget": 4,
            "branch_id": "b0",
            "estimated_value_if_allocate_next": 0.88,
            "allocation_candidates_evaluated": 8,
            "allocation_value_std": 0.03,
            "mode": "approx",
            "branch_vs_outside_gap": 0.2,
            "features_branch_v1": {
                "score": 0.86,
                "depth": 3,
                "stalled_steps": 0,
                "recent_delta": 0.03,
                "verify_count": 1,
                "branch_age": 3,
                "parent_relative_score": 0.14,
            },
        },
        {
            "state_id": "s1",
            "example_id": "e1",
            "dataset_name": "mock",
            "remaining_budget": 4,
            "branch_id": "b1",
            "estimated_value_if_allocate_next": 0.68,
            "allocation_candidates_evaluated": 8,
            "allocation_value_std": 0.04,
            "mode": "approx",
            "branch_vs_outside_gap": -0.2,
            "features_branch_v1": {
                "score": 0.62,
                "depth": 3,
                "stalled_steps": 1,
                "recent_delta": -0.02,
                "verify_count": 0,
                "branch_age": 3,
                "parent_relative_score": -0.14,
            },
        },
        {
            "state_id": "s2",
            "example_id": "e2",
            "dataset_name": "mock",
            "remaining_budget": 5,
            "branch_id": "b0",
            "estimated_value_if_allocate_next": 0.8,
            "allocation_candidates_evaluated": 8,
            "allocation_value_std": 0.05,
            "mode": "approx",
            "branch_vs_outside_gap": 0.05,
            "features_branch_v1": {
                "score": 0.77,
                "depth": 3,
                "stalled_steps": 0,
                "recent_delta": 0.02,
                "verify_count": 1,
                "branch_age": 4,
                "parent_relative_score": 0.08,
            },
        },
        {
            "state_id": "s2",
            "example_id": "e2",
            "dataset_name": "mock",
            "remaining_budget": 5,
            "branch_id": "b1",
            "estimated_value_if_allocate_next": 0.78,
            "allocation_candidates_evaluated": 8,
            "allocation_value_std": 0.05,
            "mode": "approx",
            "branch_vs_outside_gap": -0.05,
            "features_branch_v1": {
                "score": 0.75,
                "depth": 3,
                "stalled_steps": 0,
                "recent_delta": 0.01,
                "verify_count": 1,
                "branch_age": 4,
                "parent_relative_score": -0.08,
            },
        },
    ]

    pairwise_rows = [
        {
            "state_id": "s0",
            "example_id": "e0",
            "dataset_name": "mock",
            "remaining_budget": 3,
            "branch_i": "b0",
            "branch_j": "b1",
            "preference": 1,
            "margin": 0.3,
        },
        {
            "state_id": "s1",
            "example_id": "e1",
            "dataset_name": "mock",
            "remaining_budget": 4,
            "branch_i": "b0",
            "branch_j": "b1",
            "preference": 1,
            "margin": 0.2,
        },
        {
            "state_id": "s2",
            "example_id": "e2",
            "dataset_name": "mock",
            "remaining_budget": 5,
            "branch_i": "b0",
            "branch_j": "b1",
            "preference": 1,
            "margin": 0.02,
        },
    ]

    state_rows = [
        {"state_id": "s0", "candidate_mode": "exact", "dataset_name": "mock"},
        {"state_id": "s1", "candidate_mode": "approx", "dataset_name": "mock"},
        {"state_id": "s2", "candidate_mode": "approx", "dataset_name": "mock"},
    ]

    _write_jsonl(labels_dir / "candidate_labels.jsonl", candidate_rows)
    _write_jsonl(labels_dir / "pairwise_labels.jsonl", pairwise_rows)
    _write_jsonl(labels_dir / "state_summaries.jsonl", state_rows)
    return labels_dir


def test_schema_loading(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    data = load_label_artifacts(labels_dir)
    assert len(data["candidate_labels"]) == 6
    assert len(data["pairwise_labels"]) == 3
    assert len(data["state_summaries"]) == 3


def test_feature_extraction_vector_size_and_mode_flags(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    row = load_label_artifacts(labels_dir)["candidate_labels"][0]
    x = build_candidate_feature_vector(row)
    assert len(x) == len(ALLOC_FEATURE_NAMES)
    idx_exact = ALLOC_FEATURE_NAMES.index("mode_exact")
    idx_approx = ALLOC_FEATURE_NAMES.index("mode_approx")
    assert x[idx_exact] == 1.0
    assert x[idx_approx] == 0.0


def test_train_eval_pipeline_tiny_synthetic(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    cfg = LearningConfig(seed=17, train_ratio=0.67, val_ratio=0.0)
    tables = prepare_learning_tables(load_label_artifacts(labels_dir), cfg)
    models = train_models(tables, cfg)
    summary = evaluate_models(models, tables, cfg)
    assert "pairwise" in summary
    assert "pointwise" in summary
    assert "outside_option" in summary
    assert summary["pairwise"]["pairwise_accuracy_test"] >= 0.0
    assert summary["pairwise"]["ranking_top1_accuracy_test"] >= 0.0


def test_metric_computation_contains_slices(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    cfg = LearningConfig(seed=17, train_ratio=0.67, val_ratio=0.0)
    tables = prepare_learning_tables(load_label_artifacts(labels_dir), cfg)
    models = train_models(tables, cfg)
    summary = evaluate_models(models, tables, cfg)
    pairwise_metrics = summary["pairwise"]
    assert "near_tie_pairwise_accuracy_test" in pairwise_metrics
    assert "far_margin_pairwise_accuracy_test" in pairwise_metrics
    assert "pairwise_accuracy_by_mode" in pairwise_metrics
    assert "pairwise_accuracy_by_budget" in pairwise_metrics
    assert "pairwise_accuracy_by_dataset" in pairwise_metrics

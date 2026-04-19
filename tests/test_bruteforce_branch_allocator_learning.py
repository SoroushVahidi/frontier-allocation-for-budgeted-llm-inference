from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.bruteforce_branch_allocator import (
    ALLOC_FEATURE_NAMES,
    ALLOC_FEATURE_NAMES_V3,
    _build_defer_label_audit,
    _deterministic_cap_rows,
    _fit_pairwise_svm_model,
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
    state_value_rows = [
        {
            "state_id": "s0",
            "Q_commit": 0.5,
            "best_expand_branch": "b0",
            "best_expand_value": 0.9,
            "best_action_overall": "expand:b0",
            "ambiguity_bucket": "high_margin",
        },
        {
            "state_id": "s1",
            "Q_commit": 0.72,
            "best_expand_branch": "b0",
            "best_expand_value": 0.88,
            "best_action_overall": "expand:b0",
            "ambiguity_bucket": "medium_margin",
        },
        {
            "state_id": "s2",
            "Q_commit": 0.79,
            "best_expand_branch": "b0",
            "best_expand_value": 0.8,
            "best_action_overall": "expand:b0",
            "ambiguity_bucket": "near_tie",
        },
    ]

    _write_jsonl(labels_dir / "candidate_labels.jsonl", candidate_rows)
    _write_jsonl(labels_dir / "pairwise_labels.jsonl", pairwise_rows)
    _write_jsonl(labels_dir / "state_summaries.jsonl", state_rows)
    _write_jsonl(labels_dir / "state_value_targets.jsonl", state_value_rows)
    return labels_dir


def test_schema_loading(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    data = load_label_artifacts(labels_dir)
    assert len(data["candidate_labels"]) == 6
    assert len(data["pairwise_labels"]) == 3
    assert len(data["state_summaries"]) == 3
    assert len(data["state_value_targets"]) == 3


def test_value_aware_defer_mode_uses_commit_gap(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    data = load_label_artifacts(labels_dir)
    cfg = LearningConfig(
        seed=3,
        train_lightgbm_ranker=False,
        train_catboost_ranker=False,
        train_pairwise_svm=False,
        defer_target_mode="value_aware",
        defer_oracle_gap_threshold=0.03,
    )
    tables = prepare_learning_tables(data, cfg)
    s2_row = next(r for r in tables["pairwise"] if r["state_id"] == "s2")
    assert float(s2_row["state_Q_commit"]) > 0.0
    assert int(s2_row["ternary_defer_label"]) == 1


def test_defer_label_audit_generation(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    data = load_label_artifacts(labels_dir)
    cfg = LearningConfig(seed=3, train_lightgbm_ranker=False, train_catboost_ranker=False, train_pairwise_svm=False)
    tables = prepare_learning_tables(data, cfg)
    audit = tables["defer_label_audit"]["all"]
    assert audit["total_examples"] == len(tables["pairwise"])
    assert "counts_by_ambiguity_bucket" in audit
    assert "counts_by_best_action_metadata" in audit


def test_backward_compat_without_state_value_targets(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    (labels_dir / "state_value_targets.jsonl").unlink()
    data = load_label_artifacts(labels_dir)
    assert data["state_value_targets"] == []
    cfg = LearningConfig(seed=4, train_lightgbm_ranker=False, train_catboost_ranker=False, train_pairwise_svm=False)
    tables = prepare_learning_tables(data, cfg)
    assert "defer_label_audit" in tables


def test_defer_threshold_sweep_outputs_created() -> None:
    rows = [
        {"ternary_defer_label": 1, "pair_ambiguity_bucket": "near_tie", "state_best_action_overall": "commit_now", "state_best_expand_value": 0.51, "state_Q_commit": 0.5, "pair_regret_if_choose_i": 0.01, "pair_regret_if_choose_j": 0.0, "pair_value_gap": 0.01},
        {"ternary_defer_label": 0, "pair_ambiguity_bucket": "high_margin", "state_best_action_overall": "expand:b0", "state_best_expand_value": 0.9, "state_Q_commit": 0.5, "pair_regret_if_choose_i": 0.2, "pair_regret_if_choose_j": 0.0, "pair_value_gap": 0.2},
    ]
    audit = _build_defer_label_audit(rows)
    assert audit["positive_defer_labels"] == 1
    assert "counts_by_delta_expand_commit_bucket" in audit


def test_defer_threshold_sweep_artifact_from_runner(tmp_path: Path) -> None:
    run_id = "pytest_defer_threshold_sweep"
    cmd = [
        sys.executable,
        "scripts/run_value_aware_target_regime_comparison.py",
        "--run-id",
        run_id,
        "--output-dir",
        str(tmp_path),
        "--max-frontier-states",
        "8",
        "--rollout-samples-per-candidate",
        "3",
        "--max-allocation-samples",
        "6",
        "--frontier-budget",
        "5",
        "--defer-threshold-selection",
        "fixed",
    ]
    subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1], check=True)
    artifact = tmp_path / run_id / "defer_score_audit.json"
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    decomp = payload["value_aware_ambiguity_decomposed"]
    assert "threshold_trace_test" in decomp


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


def test_pairwise_svm_linear_train_and_eval(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    cfg = LearningConfig(seed=17, train_ratio=0.67, val_ratio=0.0, train_lightgbm_ranker=False, train_catboost_ranker=False)
    tables = prepare_learning_tables(load_label_artifacts(labels_dir), cfg)
    models = train_models(tables, cfg, model_artifact_dir=tmp_path / "models")
    assert models["pairwise_svm_linear"]["model_type"] == "pairwise_linear_svm"
    summary = evaluate_models(models, tables, cfg)
    assert "pairwise_svm_linear" in summary
    assert summary["pairwise_svm_linear"]["pairwise_accuracy_test"] >= 0.0


def test_pairwise_svm_nystroem_capped_subsampling_deterministic(tmp_path: Path) -> None:
    rows = [
        {"state_id": f"s{i}", "branch_i": "bi", "branch_j": "bj", "example_id": f"e{i}"}
        for i in range(64)
    ]
    a, capped_a = _deterministic_cap_rows(rows, cap=10, seed=123)
    b, capped_b = _deterministic_cap_rows(rows, cap=10, seed=123)
    c, _ = _deterministic_cap_rows(rows, cap=10, seed=124)
    assert capped_a and capped_b
    assert [r["state_id"] for r in a] == [r["state_id"] for r in b]
    assert [r["state_id"] for r in a] != [r["state_id"] for r in c]


def test_pairwise_svm_nystroem_variant_train(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    cfg = LearningConfig(
        seed=17,
        train_ratio=0.67,
        val_ratio=0.0,
        train_pairwise=False,
        train_pairwise_svm=True,
        train_pairwise_svm_nystroem=True,
        svm_max_train_rows_for_nystroem=2,
        svm_nystroem_components=8,
        train_lightgbm_ranker=False,
        train_catboost_ranker=False,
    )
    tables = prepare_learning_tables(load_label_artifacts(labels_dir), cfg)
    model = _fit_pairwise_svm_model(tables["pairwise"], cfg, tmp_path / "artifacts")
    assert model["model_type"] == "pairwise_nystroem_svm"
    assert model["status"] in {"ok", "single_class_train", "insufficient_train_rows"}


def test_train_cli_parser_supports_svm_flags() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "train_bruteforce_branch_allocator.py"
    spec = importlib.util.spec_from_file_location("train_bruteforce_branch_allocator_script", script_path)
    assert spec and spec.loader
    parser_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser_module)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "sys.argv",
            [
                "train_bruteforce_branch_allocator.py",
                "--labels-dir",
                "dummy",
                "--train-pairwise-svm-nystroem",
                "--svm-c",
                "0.7",
                "--svm-use-sample-weight",
                "--svm-nystroem-gamma",
                "0.05",
                "--svm-max-train-rows-for-nystroem",
                "123",
                "--svm-nystroem-components",
                "64",
                "--svm-class-weight-balanced",
                "--svm-margin-calibration",
                "platt",
            ],
        )
        args = parser_module.parse_args()
    assert args.train_pairwise_svm_nystroem
    assert args.svm_c == 0.7
    assert args.svm_nystroem_gamma == 0.05


def test_v3_feature_construction_present(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    cfg = LearningConfig(seed=17, train_ratio=0.67, val_ratio=0.0, feature_set="v3")
    tables = prepare_learning_tables(load_label_artifacts(labels_dir), cfg)
    x = tables["candidates"][0]["x"]
    assert len(x) == len(ALLOC_FEATURE_NAMES_V3)
    assert "frontier_topk_gap_1" in ALLOC_FEATURE_NAMES_V3


def test_ternary_defer_label_materialization(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    cfg = LearningConfig(seed=17, train_ratio=0.67, val_ratio=0.0, feature_set="v3", defer_use_outside_option=True)
    tables = prepare_learning_tables(load_label_artifacts(labels_dir), cfg)
    row = tables["pairwise"][0]
    assert "ternary_defer_label" in row
    assert "ternary_defer_label_name" in row


def test_precomputed_penalized_defer_label_is_preserved(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    data = load_label_artifacts(labels_dir)
    for idx, row in enumerate(data["pairwise_labels"]):
        row["ternary_defer_label"] = 1 if idx == 0 else 2
        row["ternary_defer_label_name"] = (
            "defer_or_outside_option"
            if int(row["ternary_defer_label"]) == 1
            else "allocate_to_branch_i"
        )
        row["ternary_defer_label_source"] = "penalized_marginal_value_with_budget_price"
    cfg = LearningConfig(seed=17, train_ratio=0.67, val_ratio=0.0, defer_target_mode="precomputed")
    tables = prepare_learning_tables(data, cfg)
    row = tables["pairwise"][0]
    assert int(row["ternary_defer_label"]) == 1
    assert str(row["ternary_defer_label_name"]) == "defer_or_outside_option"


def test_pairwise_defer_classifier_training_and_metrics(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    cfg = LearningConfig(
        seed=17,
        train_ratio=0.67,
        val_ratio=0.0,
        feature_set="v3",
        train_pairwise=False,
        train_pairwise_defer_classifier=True,
        train_lightgbm_ranker=False,
        train_catboost_ranker=False,
    )
    tables = prepare_learning_tables(load_label_artifacts(labels_dir), cfg)
    models = train_models(tables, cfg, model_artifact_dir=tmp_path / "models")
    assert "pairwise_defer_classifier" in models
    summary = evaluate_models(models, tables, cfg)["pairwise_defer_classifier"]
    if summary.get("model_status") == "ok":
        assert "accepted_only_accuracy_test" in summary
        assert "coverage_test" in summary
        assert "defer_f1_test" in summary
    else:
        assert summary.get("model_status") in {"insufficient_train_rows", "single_class_train"}


def test_train_cli_parser_supports_defer_flags() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "train_bruteforce_branch_allocator.py"
    spec = importlib.util.spec_from_file_location("train_bruteforce_branch_allocator_script_defer", script_path)
    assert spec and spec.loader
    parser_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser_module)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "sys.argv",
            [
                "train_bruteforce_branch_allocator.py",
                "--labels-dir",
                "dummy",
                "--feature-set",
                "v3",
                "--train-pairwise-defer-classifier",
                "--defer-abs-margin-threshold",
                "0.02",
                "--defer-relative-margin-threshold",
                "0.12",
                "--defer-std-threshold",
                "0.05",
                "--defer-outside-gap-threshold",
                "0.01",
                "--defer-model-type",
                "multinomial_logreg",
            ],
        )
        args = parser_module.parse_args()
    assert args.feature_set == "v3"
    assert args.train_pairwise_defer_classifier
    assert args.defer_abs_margin_threshold == 0.02


def test_oracle_proxy_target_materialization(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    cfg = LearningConfig(
        seed=17,
        train_ratio=0.67,
        val_ratio=0.0,
        feature_set="v3",
        defer_target_mode="oracle_proxy",
        defer_oracle_gap_threshold=0.05,
        defer_oracle_gap_over_std_threshold=1.0,
        defer_oracle_best_vs_outside_threshold=0.06,
    )
    tables = prepare_learning_tables(load_label_artifacts(labels_dir), cfg)
    row = tables["pairwise"][-1]
    assert "pair_best_estimated_value" in row
    assert "pair_value_gap" in row
    assert "pair_oracle_defer_score" in row
    assert row["ternary_defer_label_name"] in {"defer_or_outside_option", "allocate_to_branch_i", "allocate_to_branch_j"}


def test_defer_calibration_and_threshold_trace(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    cfg = LearningConfig(
        seed=17,
        train_ratio=0.67,
        val_ratio=0.33,
        feature_set="v3",
        train_pairwise=False,
        train_pairwise_defer_classifier=True,
        train_lightgbm_ranker=False,
        train_catboost_ranker=False,
        defer_target_mode="oracle_proxy",
        defer_calibration="temperature",
        threshold_grid_size=5,
    )
    tables = prepare_learning_tables(load_label_artifacts(labels_dir), cfg)
    models = train_models(tables, cfg, model_artifact_dir=tmp_path / "models")
    summary = evaluate_models(models, tables, cfg)["pairwise_defer_classifier"]
    if summary.get("model_status") == "ok":
        assert "threshold_trace_test" in summary
        assert len(summary["threshold_trace_test"]) >= 3
        assert "best_accepted_accuracy_under_min_coverage_test" in summary
        assert "best_coverage_under_min_accepted_accuracy_test" in summary
    else:
        assert summary.get("model_status") in {"insufficient_train_rows", "single_class_train"}


def test_train_cli_parser_supports_oracle_proxy_and_calibration_flags() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "train_bruteforce_branch_allocator.py"
    spec = importlib.util.spec_from_file_location("train_bruteforce_branch_allocator_script_oracle_proxy", script_path)
    assert spec and spec.loader
    parser_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser_module)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "sys.argv",
            [
                "train_bruteforce_branch_allocator.py",
                "--labels-dir",
                "dummy",
                "--train-pairwise-defer-classifier",
                "--defer-target-mode",
                "oracle_proxy",
                "--defer-oracle-gap-threshold",
                "0.04",
                "--defer-oracle-gap-over-std-threshold",
                "0.9",
                "--defer-oracle-best-vs-outside-threshold",
                "0.02",
                "--defer-calibration",
                "platt",
                "--defer-decision-threshold",
                "0.6",
                "--min-commit-confidence",
                "0.5",
                "--commit-margin-threshold",
                "0.08",
            ],
        )
        args = parser_module.parse_args()
    assert args.defer_target_mode == "oracle_proxy"
    assert args.defer_calibration == "platt"
    assert args.defer_decision_threshold == 0.6


def test_train_cli_parser_supports_precomputed_defer_target_mode() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "train_bruteforce_branch_allocator.py"
    spec = importlib.util.spec_from_file_location("train_bruteforce_branch_allocator_script_precomputed", script_path)
    assert spec and spec.loader
    parser_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser_module)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "sys.argv",
            [
                "train_bruteforce_branch_allocator.py",
                "--labels-dir",
                "dummy",
                "--defer-target-mode",
                "precomputed",
            ],
        )
        args = parser_module.parse_args()
    assert args.defer_target_mode == "precomputed"


def test_defer_fallback_policy_metrics_and_unresolved_accounting(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    cfg = LearningConfig(
        seed=17,
        train_ratio=0.67,
        val_ratio=0.33,
        feature_set="v3",
        train_pairwise=True,
        train_pointwise=True,
        train_pairwise_defer_classifier=True,
        train_lightgbm_ranker=False,
        train_catboost_ranker=False,
        defer_target_mode="oracle_proxy",
        enable_defer_fallback=True,
        defer_fallback_policy="outside_option_aware_backup",
    )
    tables = prepare_learning_tables(load_label_artifacts(labels_dir), cfg)
    models = train_models(tables, cfg, model_artifact_dir=tmp_path / "models")
    summary = evaluate_models(models, tables, cfg)["pairwise_defer_classifier"]
    if summary.get("model_status") == "ok":
        assert "resolved_accuracy_test" in summary
        assert "resolved_coverage_test" in summary
        assert "unresolved_rate_after_fallback_test" in summary
        assert summary["resolved_coverage_test"] <= 1.0
        assert summary["unresolved_rate_after_fallback_test"] >= 0.0
    else:
        assert summary.get("model_status") in {"insufficient_train_rows", "single_class_train"}


def test_deferred_specialist_training_and_eval(tmp_path: Path) -> None:
    labels_dir = _tiny_artifacts(tmp_path)
    cfg = LearningConfig(
        seed=17,
        train_ratio=0.67,
        val_ratio=0.33,
        feature_set="v3",
        train_pairwise=False,
        train_pairwise_deferred_specialist=True,
        deferred_specialist_target_mode="hybrid",
        train_lightgbm_ranker=False,
        train_catboost_ranker=False,
    )
    tables = prepare_learning_tables(load_label_artifacts(labels_dir), cfg)
    models = train_models(tables, cfg, model_artifact_dir=tmp_path / "models")
    assert "pairwise_deferred_specialist" in models
    summary = evaluate_models(models, tables, cfg)["pairwise_deferred_specialist"]
    if summary.get("model_status") == "ok":
        assert "deferred_subset_accuracy" in summary
    else:
        assert summary.get("model_status") in {"insufficient_train_rows", "single_class_train"}


def test_train_cli_parser_supports_fallback_flags() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "train_bruteforce_branch_allocator.py"
    spec = importlib.util.spec_from_file_location("train_bruteforce_branch_allocator_script_fallback", script_path)
    assert spec and spec.loader
    parser_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser_module)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "sys.argv",
            [
                "train_bruteforce_branch_allocator.py",
                "--labels-dir",
                "dummy",
                "--enable-defer-fallback",
                "--defer-fallback-policy",
                "pointwise_value_backup",
                "--fallback-min-confidence",
                "0.61",
                "--outside-option-keep-unresolved-threshold",
                "0.04",
                "--train-pairwise-deferred-specialist",
                "--deferred-specialist-target-mode",
                "hybrid",
            ],
        )
        args = parser_module.parse_args()
    assert args.enable_defer_fallback
    assert args.defer_fallback_policy == "pointwise_value_backup"
    assert args.fallback_min_confidence == 0.61
    assert args.train_pairwise_deferred_specialist

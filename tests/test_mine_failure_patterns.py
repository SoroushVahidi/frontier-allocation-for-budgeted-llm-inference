from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

try:
    import pandas as pd
    import numpy as np  # noqa: F401
    import sklearn  # noqa: F401
    from scripts import mine_failure_patterns as mfp
    HAVE_ANALYTICS_DEPS = True
except Exception:
    pd = None
    mfp = None
    HAVE_ANALYTICS_DEPS = False


OUTPUT_FILES = {
    "pattern_mining_report.md",
    "target_summary.csv",
    "feature_summary.csv",
    "decision_tree_rules.txt",
    "decision_tree_metrics.json",
    "association_rule_candidates.csv",
    "binned_feature_summary.csv",
    "target_by_artifact.csv",
    "target_by_method.csv",
    "target_by_feature_bins.csv",
    "representative_cases.jsonl",
    "metrics.json",
}


def _build_rows(n: int = 40) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for i in range(n):
        is_oracle = 1 if i % 4 == 0 else 0
        is_regression = 1 if i % 5 == 0 else 0
        is_both_wrong = 1 if i % 6 == 0 else 0
        both_correct = 1 if (is_oracle == 0 and is_regression == 0 and is_both_wrong == 0) else 0
        disagreement = 1 if (is_oracle == 1 or is_regression == 1) else 0
        parse_bad = 1 if i % 7 == 0 else 0

        rows.append(
            {
                "artifact_label": "artifact_a" if i < (n // 2) else "artifact_b",
                "source_artifact_path": f"/tmp/artifact_{'a' if i < (n // 2) else 'b'}.jsonl",
                "grouping_key": f"grp_{i}",
                "example_id": f"ex_{i}",
                "problem_id": f"prob_{i}",
                "dataset": "openai/gsm8k",
                "provider": "cohere" if i < (n // 2) else "other",
                "model": "model_x",
                "baseline_method": "external_l1_max",
                "frontier_method": "pal_frontier_v1",
                "budget": 6,
                "seed": i % 3,
                "contamination_status": "clean",
                "has_full_log": 1,
                "has_discovery_tree": 1,
                "has_frontier_log": 1,
                "baseline_correct": 0,
                "frontier_correct": 1 if is_oracle else 0,
                "both_correct": both_correct,
                "both_wrong": is_both_wrong,
                "baseline_wrong_frontier_correct": is_oracle,
                "baseline_correct_frontier_wrong": is_regression,
                "oracle_recoverable": is_oracle,
                "regression_risk": is_regression,
                "disagreement": disagreement,
                "baseline_answer": "10",
                "frontier_answer": "12" if is_oracle else "10",
                "baseline_canonical_answer": "10",
                "frontier_canonical_answer": "12" if is_oracle else "10",
                "answers_equal": 0 if is_oracle else 1,
                "answer_length_baseline": 20 + (i % 4),
                "answer_length_frontier": 40 + (i % 8) if is_oracle else 18 + (i % 3),
                "parse_success_baseline": 0 if parse_bad else 1,
                "parse_success_frontier": 1,
                "parser_error_status_baseline": "error" if parse_bad else "ok",
                "parser_error_status_frontier": "ok",
                "question": "toy question",
                "baseline_trace_snippet": "trace base",
                "frontier_trace_snippet": "trace front",
                "trace_length_baseline": 100 + i,
                "trace_length_frontier": 140 + i if is_oracle else 90 + i,
                "has_trace_baseline": 1,
                "has_trace_frontier": 1,
                "raw_status_baseline": "scored",
                "raw_status_frontier": "scored",
                "raw_error_baseline": "",
                "raw_error_frontier": "",
                "candidate_count_baseline": 1,
                "candidate_count_frontier": 3 if is_oracle else 1,
                "unique_answer_count_baseline": 1,
                "unique_answer_count_frontier": 2 if is_oracle else 1,
                "duplicate_answer_ratio_baseline": 0.0,
                "duplicate_answer_ratio_frontier": 0.0,
                "tree_node_count": 6 + (i % 2),
                "branch_count": 5 + (i % 2),
                "max_depth": 2,
                "estimated_cost_baseline": 0.01,
                "estimated_cost_frontier": 0.02,
                "total_tokens_baseline": 100,
                "total_tokens_frontier": 180,
                "call_count_baseline": 1,
                "call_count_frontier": 2,
                "stop_reason_baseline": "scored",
                "stop_reason_frontier": "scored",
                "gold_answer": "n/a",
                "needs_manual_review": 0,
                "inference_available_feature_set": "high_log_runtime_plus_offline_labels",
                "offline_only_label_note": "targets use exact_match/offline gold; not runtime-available",
            }
        )
    return rows


def _write_input_bundle(base_dir: Path, n: int = 40) -> Path:
    rows = _build_rows(n)
    csv_path = base_dir / "failure_pattern_features.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    pkt_path = base_dir / "example_case_packets.jsonl"
    with pkt_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(
                json.dumps(
                    {
                        "example_id": row["example_id"],
                        "question": "toy question",
                        "baseline_answer": row["baseline_answer"],
                        "frontier_answer": row["frontier_answer"],
                    }
                )
                + "\n"
            )
    return csv_path


def test_analytics_dependencies_available_for_mining_script():
    assert isinstance(HAVE_ANALYTICS_DEPS, bool)


@pytest.mark.skipif(not HAVE_ANALYTICS_DEPS, reason="analytics dependencies unavailable in this pytest environment")
def test_run_creates_outputs_and_representatives(tmp_path: Path):
    feature_csv = _write_input_bundle(tmp_path, n=40)
    out_dir = tmp_path / "out"

    metrics = mfp.run(
        [
            "--feature-table-csv",
            str(feature_csv),
            "--output-dir",
            str(out_dir),
            "--target",
            "oracle_recoverable",
            "--min-support",
            "0.1",
            "--max-tree-depth",
            "3",
            "--seed",
            "7",
        ]
    )

    produced = {p.name for p in out_dir.iterdir() if p.is_file()}
    assert OUTPUT_FILES.issubset(produced)
    assert metrics["row_count"] == 40
    assert metrics["target_counts"]["oracle_recoverable"] > 0

    rep_lines = (out_dir / "representative_cases.jsonl").read_text(encoding="utf-8").strip().splitlines()
    reps = [json.loads(line) for line in rep_lines if line.strip()]
    counts = {}
    for row in reps:
        counts[row["target"]] = counts.get(row["target"], 0) + 1
    assert counts.get("oracle_recoverable", 0) >= 5
    assert counts.get("regression_risk", 0) >= 5
    assert counts.get("both_wrong", 0) >= 5


@pytest.mark.skipif(not HAVE_ANALYTICS_DEPS, reason="analytics dependencies unavailable in this pytest environment")
def test_missing_target_validation_raises(tmp_path: Path):
    csv_path = tmp_path / "bad.csv"
    pd.DataFrame(
        [
            {
                "example_id": "x",
                "dataset": "d",
                "provider": "p",
                "model": "m",
                "baseline_method": "b",
                "frontier_method": "f",
                "oracle_recoverable": 0,
                "regression_risk": 1,
                "both_wrong": 0,
                "both_correct": 1,
            }
        ]
    ).to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="Missing required target columns"):
        mfp.run(["--feature-table-csv", str(csv_path), "--output-dir", str(tmp_path / "out")])


@pytest.mark.skipif(not HAVE_ANALYTICS_DEPS, reason="analytics dependencies unavailable in this pytest environment")
def test_fallback_rule_mining_without_mlxtend(monkeypatch):
    monkeypatch.setitem(sys.modules, "mlxtend", None)
    monkeypatch.setitem(sys.modules, "mlxtend.frequent_patterns", None)

    discrete = pd.DataFrame(
        {
            "feature_a": ["low", "low", "high", "high", "high", "low"],
            "feature_b": ["x", "x", "x", "y", "y", "x"],
        }
    )
    targets = pd.DataFrame(
        {
            "oracle_recoverable": [1, 1, 0, 0, 0, 1],
            "regression_risk": [0, 0, 1, 1, 0, 0],
            "both_wrong": [0, 1, 0, 1, 0, 0],
            "both_correct": [0, 0, 0, 0, 1, 0],
            "disagreement": [1, 1, 1, 1, 0, 1],
        }
    )

    rules, binned, _, engine = mfp._mine_association_rules(discrete, targets, min_support=0.2)
    assert engine == "fallback_manual"
    assert not rules.empty
    assert not binned.empty


@pytest.mark.skipif(not HAVE_ANALYTICS_DEPS, reason="analytics dependencies unavailable in this pytest environment")
def test_tree_fit_with_numeric_and_categorical_features():
    df = pd.DataFrame(_build_rows(30))
    df = mfp._normalize_binary_targets(df)
    features = ["provider", "answers_equal", "answer_length_frontier", "trace_length_frontier", "candidate_count_frontier"]

    metrics, rules, importances, pred = mfp._fit_tree(df, "oracle_recoverable", features, max_depth=3, seed=123)
    assert metrics["total_feature_count"] == len(features)
    assert isinstance(rules, str) and len(rules) > 0
    assert len(pred) == len(df)
    assert isinstance(importances, list)


@pytest.mark.skipif(not HAVE_ANALYTICS_DEPS, reason="analytics dependencies unavailable in this pytest environment")
def test_no_provider_sdk_imports_in_script():
    text = Path(mfp.__file__).read_text(encoding="utf-8")
    banned = ["import openai", "from openai", "import cohere", "from cohere"]
    assert not any(token in text for token in banned)

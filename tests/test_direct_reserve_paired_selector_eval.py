from __future__ import annotations

import csv
import json
import pickle
import subprocess
import sys
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer

REPO = Path(__file__).resolve().parents[1]


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _build_synth_validation(root: Path) -> None:
    _write_csv(
        root / "per_case_method_results.csv",
        [
            "example_id",
            "seed",
            "budget",
            "method",
            "gold_answer",
            "normalized_selected_answer",
            "final_selected_answer",
            "stratum",
            "top2_support_gap",
            "answer_entropy",
            "action_count",
        ],
        [
            ["ex1", "1", "4", "direct_reserve_strong_plus_diverse_v1", "10", "10", "10", "absent_from_tree", "0.0", "1.0", "4"],
            ["ex1", "1", "4", "direct_reserve_strong_plus_diverse_margin_gated_v1", "10", "10", "10", "absent_from_tree", "0.0", "1.0", "4"],
            ["ex2", "1", "4", "direct_reserve_strong_plus_diverse_v1", "20", "9", "9", "control_correct", "0.0", "1.0", "4"],
            ["ex2", "1", "4", "direct_reserve_strong_plus_diverse_margin_gated_v1", "20", "9", "9", "control_correct", "0.0", "1.0", "4"],
        ],
    )
    _write_csv(
        root / "candidate_branch_table.csv",
        [
            "example_id",
            "seed",
            "budget",
            "method",
            "normalized_candidate_answer",
            "answer_group",
            "is_selected",
            "branch_depth",
            "branch_prompt_style",
        ],
        [
            ["ex1", "1", "4", "direct_reserve_strong_plus_diverse_v1", "10", "10", "1", "1", "direct_reserve"],
            ["ex1", "1", "4", "direct_reserve_strong_plus_diverse_v1", "8", "8", "0", "1", "direct_reserve"],
            ["ex2", "1", "4", "direct_reserve_strong_plus_diverse_v1", "9", "9", "1", "1", "direct_reserve"],
            ["ex2", "1", "4", "direct_reserve_strong_plus_diverse_v1", "20", "20", "0", "1", "direct_reserve"],
        ],
    )
    _write_csv(root / "answer_group_summary.csv", ["example_id", "seed", "budget", "method", "answer_group", "support"], [])
    (root / "planned_cases.csv").write_text(
        "example_id,seed,budget\nex1,1,4\nex2,1,4\n",
        encoding="utf-8",
    )


def _build_model(path: Path) -> None:
    vec = DictVectorizer(sparse=False)
    X = vec.fit_transform(
        [
            {"f_answer_group_support": 2.0, "f_branch_depth": 1.0, "m__direct_reserve_strong_plus_diverse_v1": 1.0},
            {"f_answer_group_support": 1.0, "f_branch_depth": 1.0, "m__direct_reserve_strong_plus_diverse_v1": 1.0},
        ]
    )
    y = [1, 0]
    rf = RandomForestClassifier(n_estimators=20, random_state=7)
    rf.fit(X, y)
    with path.open("wb") as f:
        pickle.dump({"vectorizer": vec, "rf": rf}, f)


def _build_training_dataset(path: Path) -> None:
    _write_csv(
        path,
        [
            "example_id",
            "seed",
            "budget",
            "excluded_from_training",
            "is_gold_candidate",
            "method",
            "stratum",
            "prompt_style",
            "source_type",
            "branch_depth",
            "answer_group_support",
            "answer_group_rank",
            "action_count",
            "top2_support_gap",
            "answer_entropy",
            "n_methods_sharing_norm_answer",
            "selected_by_method",
            "match_strict_f3_final",
            "match_external_l1_max_final",
            "match_direct_reserve_strong_v1_final",
            "match_direct_reserve_strong_plus_diverse_v1_final",
            "extraction_ok",
            "problem_gold_present",
            "problem_present_not_selected",
            "diverse_gold_in_pool",
            "normalized_answer",
        ],
        [
            ["ex1", "1", "4", "0", "1", "direct_reserve_strong_plus_diverse_v1", "absent_from_tree", "direct_reserve", "candidate_branch_table", "1", "2", "1", "4", "0.0", "1.0", "0", "1", "0", "0", "0", "1", "1", "1", "0", "1", "10"],
            ["ex1", "1", "4", "0", "0", "direct_reserve_strong_plus_diverse_v1", "absent_from_tree", "direct_reserve", "candidate_branch_table", "1", "1", "2", "4", "0.0", "1.0", "0", "0", "0", "0", "0", "1", "1", "1", "0", "1", "8"],
            ["ex2", "1", "4", "0", "1", "direct_reserve_strong_plus_diverse_v1", "control_correct", "direct_reserve", "candidate_branch_table", "1", "1", "1", "4", "0.0", "1.0", "0", "0", "0", "0", "0", "1", "1", "1", "1", "1", "20"],
            ["ex2", "1", "4", "0", "0", "direct_reserve_strong_plus_diverse_v1", "control_correct", "direct_reserve", "candidate_branch_table", "1", "1", "2", "4", "0.0", "1.0", "0", "1", "0", "0", "0", "1", "1", "1", "1", "1", "9"],
        ],
    )


def test_paired_eval_uses_same_pool_and_outputs_threshold_rows(tmp_path: Path) -> None:
    v = tmp_path / "validation"
    _build_synth_validation(v)
    m = tmp_path / "selected_model.joblib"
    _build_model(m)
    ts = "PAIRED_SYNTH"
    subprocess.check_call(
        [
            sys.executable,
            str(REPO / "scripts" / "run_direct_reserve_paired_selector_eval.py"),
            "--validation-output",
            str(v),
            "--model-path",
            str(m),
            "--thresholds",
            "0.00,0.10",
            "--timestamp",
            ts,
        ],
        cwd=REPO,
    )
    out = REPO / "outputs" / f"direct_reserve_paired_selector_eval_{ts}"
    assert (out / "summary.csv").exists()
    assert (out / "threshold_sweep.csv").exists()
    assert (out / "case_level_selection.csv").exists()
    rows = list(csv.DictReader((out / "case_level_selection.csv").open("r", encoding="utf-8")))
    assert rows
    assert all(int(r.get("same_candidate_pool_used", 0)) == 1 for r in rows)
    th = list(csv.DictReader((out / "threshold_sweep.csv").open("r", encoding="utf-8")))
    assert {r["threshold"] for r in th} == {"0.00", "0.10"}


def test_default_selector_model_is_rf_not_hgb(tmp_path: Path) -> None:
    v = tmp_path / "validation"
    _build_synth_validation(v)
    m = tmp_path / "selected_model.joblib"
    _build_model(m)
    ts = "PAIRED_RF_DEFAULT"
    subprocess.check_call(
        [
            sys.executable,
            str(REPO / "scripts" / "run_direct_reserve_paired_selector_eval.py"),
            "--validation-output",
            str(v),
            "--model-path",
            str(m),
            "--timestamp",
            ts,
        ],
        cwd=REPO,
    )
    out = REPO / "outputs" / f"direct_reserve_paired_selector_eval_{ts}"
    summary = list(csv.DictReader((out / "summary.csv").open("r", encoding="utf-8")))
    assert summary and summary[0]["selector_model"] == "rf"


def test_overlapping_artifact_not_labeled_fresh(tmp_path: Path) -> None:
    v = tmp_path / "cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T151700Z"
    _build_synth_validation(v)
    # Simulate explicit overlap report
    _write_csv(v / "overlap_report.csv", ["overlap_count"], [["2"]])
    m = tmp_path / "selected_model.joblib"
    _build_model(m)
    ts = "PAIRED_OVERLAP_LABEL"
    subprocess.check_call(
        [
            sys.executable,
            str(REPO / "scripts" / "run_direct_reserve_paired_selector_eval.py"),
            "--validation-output",
            str(v),
            "--model-path",
            str(m),
            "--timestamp",
            ts,
        ],
        cwd=REPO,
    )
    out = REPO / "outputs" / f"direct_reserve_paired_selector_eval_{ts}"
    row = list(csv.DictReader((out / "summary.csv").open("r", encoding="utf-8")))[0]
    assert row["source_type"] != "true_fresh_zero_overlap"
    assert row["is_true_fresh_zero_overlap"] == "0"


def test_model_load_failure_stops_gracefully_without_retrain(tmp_path: Path) -> None:
    v = tmp_path / "validation"
    _build_synth_validation(v)
    bad = tmp_path / "bad_model.joblib"
    bad.write_text("not-a-pickle", encoding="utf-8")
    ts = "PAIRED_STOP_GRACEFUL"
    subprocess.check_call(
        [
            sys.executable,
            str(REPO / "scripts" / "run_direct_reserve_paired_selector_eval.py"),
            "--validation-output",
            str(v),
            "--model-path",
            str(bad),
            "--timestamp",
            ts,
        ],
        cwd=REPO,
    )
    out = REPO / "outputs" / f"direct_reserve_paired_selector_eval_{ts}"
    row = list(csv.DictReader((out / "summary.csv").open("r", encoding="utf-8")))[0]
    assert row["n_cases"] == "0"
    assert row["model_load_status"] in {"load_failed", "load_failed_no_training_dataset"}


def test_model_load_failure_retrains_and_writes_manifest(tmp_path: Path) -> None:
    v = tmp_path / "validation"
    _build_synth_validation(v)
    bad = tmp_path / "bad_model.joblib"
    bad.write_text("not-a-pickle", encoding="utf-8")
    train = tmp_path / "examples.csv"
    _build_training_dataset(train)
    ts = "PAIRED_RETRAIN_OK"
    subprocess.check_call(
        [
            sys.executable,
            str(REPO / "scripts" / "run_direct_reserve_paired_selector_eval.py"),
            "--validation-output",
            str(v),
            "--model-path",
            str(bad),
            "--allow-retrain-on-load-failure",
            "--training-dataset",
            str(train),
            "--timestamp",
            ts,
        ],
        cwd=REPO,
    )
    out = REPO / "outputs" / f"direct_reserve_paired_selector_eval_{ts}"
    row = list(csv.DictReader((out / "summary.csv").open("r", encoding="utf-8")))[0]
    assert row["model_load_status"] == "retrained_fallback"
    assert (out / "retrained_model_manifest.json").exists()
    assert (out / "feature_schema_used.json").exists()
    assert (out / "training_dataset_path.txt").exists()
    manifest = json.loads((out / "retrained_model_manifest.json").read_text(encoding="utf-8"))
    assert manifest.get("model_type", "").startswith("random_forest")


def test_policy_sweep_outputs_written(tmp_path: Path) -> None:
    v = tmp_path / "validation"
    _build_synth_validation(v)
    m = tmp_path / "selected_model.joblib"
    _build_model(m)
    ts = "PAIRED_POLICY_SWEEP"
    subprocess.check_call(
        [
            sys.executable,
            str(REPO / "scripts" / "run_direct_reserve_paired_selector_eval.py"),
            "--validation-output",
            str(v),
            "--model-path",
            str(m),
            "--thresholds",
            "0.00,0.10",
            "--timestamp",
            ts,
        ],
        cwd=REPO,
    )
    pol = REPO / "outputs" / f"direct_reserve_paired_selector_policy_sweep_{ts}"
    assert (pol / "policy_summary.csv").exists()
    assert (pol / "policy_case_level_selection.csv").exists()
    assert (pol / "policy_improvement_cases.csv").exists()
    assert (pol / "policy_degradation_cases.csv").exists()
    assert (pol / "policy_control_degradation_cases.csv").exists()
    assert (pol / "README.md").exists()


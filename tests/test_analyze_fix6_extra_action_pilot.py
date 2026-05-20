import csv
import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import analyze_fix6_extra_action_pilot as analyzer


def _write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys = set()
        for row in rows:
            keys.update(row.keys())
        fieldnames = sorted(keys)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _build_minimal_fixture(base: Path):
    pilot_root = base / "pilot"
    fix6_root = base / "fix6"
    postrun_root = base / "postrun"
    postrun_root.mkdir(parents=True, exist_ok=True)

    selected_cases = [
        {
            "example_id": "ex1",
            "dataset": "openai/gsm8k",
            "seed_parent": 41,
            "budget_parent": 6,
            "residual_category": "residual_external_consensus",
            "offline_labels": {
                "fix24_correct": False,
                "tale_correct": True,
                "all_methods_wrong": False,
                "oracle_observable_correct": True,
            },
            "fix24_answer_canonical": "10",
            "tale_answer_canonical": "11",
            "frontier_answer_canonical": "10",
            "l1_answer_canonical": "11",
            "s1_answer_canonical": "11",
        },
        {
            "example_id": "ex2",
            "dataset": "openai/gsm8k",
            "seed_parent": 41,
            "budget_parent": 6,
            "residual_category": "residual_frontier_pool_miss",
            "offline_labels": {
                "fix24_correct": True,
                "tale_correct": True,
                "all_methods_wrong": False,
                "oracle_observable_correct": True,
            },
            "fix24_answer_canonical": "20",
            "tale_answer_canonical": "20",
            "frontier_answer_canonical": "20",
            "l1_answer_canonical": "20",
            "s1_answer_canonical": "20",
        },
    ]
    _write_jsonl(pilot_root / "selected_cases.jsonl", selected_cases)

    _write_csv(
        pilot_root / "extra_action_plan.csv",
        [
            {
                "example_id": "ex1",
                "dataset": "openai/gsm8k",
                "primary_action": "extra_tale_retry",
                "secondary_action": "extra_frontier_diverse",
                "proxy_method_frontier": "direct_reserve_semantic_frontier_v2",
                "proxy_method_tale": "external_tale_prompt_budgeting",
                "fresh_seed": "53",
                "reason": "test",
            },
            {
                "example_id": "ex2",
                "dataset": "openai/gsm8k",
                "primary_action": "extra_frontier_diverse",
                "secondary_action": "extra_tale_retry",
                "proxy_method_frontier": "direct_reserve_semantic_frontier_v2",
                "proxy_method_tale": "external_tale_prompt_budgeting",
                "fresh_seed": "53",
                "reason": "test",
            },
        ],
    )

    _write_csv(
        fix6_root / "fix6_state_feature_table.csv",
        [
            {
                "example_id": "ex1",
                "dataset": "openai/gsm8k",
                "seed": "41",
                "budget": "6",
                "low_depth_flag": "True",
                "external_agreement_signature": "l1=s1=tale",
                "candidate_count": "2",
                "answer_diversity_cluster_count": "1",
                "state_signal": "A",
                "gold_forbidden_feature": "secret",
                "correctness_forbidden_feature": "also_secret",
            },
            {
                "example_id": "ex2",
                "dataset": "openai/gsm8k",
                "seed": "41",
                "budget": "6",
                "low_depth_flag": "False",
                "external_agreement_signature": "l1=s1=tale",
                "candidate_count": "4",
                "answer_diversity_cluster_count": "2",
                "state_signal": "B",
                "gold_forbidden_feature": "secret",
                "correctness_forbidden_feature": "also_secret",
            },
        ],
    )

    _write_csv(
        fix6_root / "fix6_residual_failure_cases.csv",
        [
            {
                "example_id": "ex1",
                "dataset": "openai/gsm8k",
                "seed": "41",
                "budget": "6",
                "fix24_correct": "False",
                "tale_correct": "True",
                "root_cause_label": "residual_external_consensus",
            },
            {
                "example_id": "ex2",
                "dataset": "openai/gsm8k",
                "seed": "41",
                "budget": "6",
                "fix24_correct": "True",
                "tale_correct": "True",
                "root_cause_label": "residual_frontier_pool_miss",
            },
        ],
    )

    _write_csv(
        fix6_root / "fix6_action_availability.csv",
        [
            {
                "example_id": "ex1",
                "dataset": "openai/gsm8k",
                "seed": "41",
                "budget": "6",
                "avail_logged_frontier_alternative_proxy": "True",
                "avail_logged_external_alternative_proxy": "False",
            },
            {
                "example_id": "ex2",
                "dataset": "openai/gsm8k",
                "seed": "41",
                "budget": "6",
                "avail_logged_frontier_alternative_proxy": "False",
                "avail_logged_external_alternative_proxy": "True",
            },
        ],
    )

    _write_csv(
        fix6_root / "fix6_oracle_action_table.csv",
        [
            {"example_id": "ex1", "dataset": "openai/gsm8k", "seed": "41", "budget": "6"},
            {"example_id": "ex2", "dataset": "openai/gsm8k", "seed": "41", "budget": "6"},
        ],
    )

    return pilot_root, fix6_root, postrun_root


def _pilot_rows_complete() -> list[dict]:
    return [
        {
            "example_id": "ex1",
            "dataset": "openai/gsm8k",
            "method": "direct_reserve_semantic_frontier_v2",
            "seed": 53,
            "budget": 6,
            "status": "scored",
            "final_answer_canonical": "11",
            "gold_answer_canonical": "11",
            "exact_match": 1,
            "promotion_review_record": {"ok": 1},
            "promotion_review_validation": {"ok": 1},
            "enough_for_promotion_review": "yes",
        },
        {
            "example_id": "ex1",
            "dataset": "openai/gsm8k",
            "method": "external_tale_prompt_budgeting",
            "seed": 53,
            "budget": 6,
            "status": "scored",
            "final_answer_canonical": "10",
            "gold_answer_canonical": "11",
            "exact_match": 0,
            "promotion_review_record": {"ok": 1},
            "promotion_review_validation": {"ok": 1},
            "enough_for_promotion_review": "yes",
        },
        {
            "example_id": "ex2",
            "dataset": "openai/gsm8k",
            "method": "direct_reserve_semantic_frontier_v2",
            "seed": 53,
            "budget": 6,
            "status": "scored",
            "final_answer_canonical": "19",
            "gold_answer_canonical": "20",
            "exact_match": 0,
            "promotion_review_record": {"ok": 1},
            "promotion_review_validation": {"ok": 1},
            "enough_for_promotion_review": "partial",
        },
        {
            "example_id": "ex2",
            "dataset": "openai/gsm8k",
            "method": "external_tale_prompt_budgeting",
            "seed": 53,
            "budget": 6,
            "status": "scored",
            "final_answer_canonical": "20",
            "gold_answer_canonical": "20",
            "exact_match": 1,
            "promotion_review_record": {"ok": 1},
            "promotion_review_validation": {"ok": 1},
            "enough_for_promotion_review": "yes",
        },
    ]


def test_missing_pilot_rows_produces_readiness_report(tmp_path: Path):
    pilot_root, fix6_root, postrun_root = _build_minimal_fixture(tmp_path)
    out = tmp_path / "out_missing"

    result = analyzer.run_analysis(
        pilot_root=pilot_root,
        fix6_root=fix6_root,
        main_postrun_root=postrun_root,
        output_root=out,
        expected_rows=4,
        expected_examples=2,
    )

    assert result["mode"] == "readiness"
    assert (out / "pilot_readiness_report.md").exists()
    assert (out / "pilot_readiness_metrics.json").exists()
    assert not (out / "pilot_analysis_report.md").exists()


def test_incomplete_pilot_rows_produces_readiness_report(tmp_path: Path):
    pilot_root, fix6_root, postrun_root = _build_minimal_fixture(tmp_path)
    _write_jsonl(
        pilot_root / "runner_output" / "job1" / "per_example_records.jsonl",
        _pilot_rows_complete()[:3],
    )
    out = tmp_path / "out_incomplete"

    result = analyzer.run_analysis(
        pilot_root=pilot_root,
        fix6_root=fix6_root,
        main_postrun_root=postrun_root,
        output_root=out,
        expected_rows=4,
        expected_examples=2,
    )

    assert result["mode"] == "readiness"
    metrics = json.loads((out / "pilot_readiness_metrics.json").read_text())
    assert metrics["validation"]["row_count"] == 3


def test_complete_tiny_pilot_produces_outputs_and_training_rows(tmp_path: Path):
    pilot_root, fix6_root, postrun_root = _build_minimal_fixture(tmp_path)
    _write_jsonl(
        pilot_root / "runner_output" / "job1" / "per_example_records.jsonl",
        _pilot_rows_complete(),
    )

    out = tmp_path / "out_complete"
    result = analyzer.run_analysis(
        pilot_root=pilot_root,
        fix6_root=fix6_root,
        main_postrun_root=postrun_root,
        output_root=out,
        expected_rows=4,
        expected_examples=2,
    )

    assert result["mode"] == "complete"
    for name in [
        "pilot_analysis_report.md",
        "pilot_analysis_metrics.json",
        "extra_action_outcomes.csv",
        "extra_action_outcomes.jsonl",
        "lovec_training_rows.csv",
        "action_value_summary.csv",
        "action_value_by_residual_category.csv",
        "action_value_by_state_feature_bins.csv",
        "pilot_regression_cases.jsonl",
        "pilot_recovery_cases.jsonl",
        "recommended_lovec_policy.json",
    ]:
        assert (out / name).exists(), name

    with (out / "extra_action_outcomes.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4


def test_gold_exact_fields_excluded_from_training_features(tmp_path: Path):
    pilot_root, fix6_root, postrun_root = _build_minimal_fixture(tmp_path)
    _write_jsonl(
        pilot_root / "runner_output" / "job1" / "per_example_records.jsonl",
        _pilot_rows_complete(),
    )
    out = tmp_path / "out_feature_guard"
    analyzer.run_analysis(
        pilot_root=pilot_root,
        fix6_root=fix6_root,
        main_postrun_root=postrun_root,
        output_root=out,
        expected_rows=4,
        expected_examples=2,
    )

    with (out / "lovec_training_rows.csv").open() as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
    feature_cols = [c for c in cols if c.startswith("state_")]
    lowered = "|".join(feature_cols).lower()
    assert "gold" not in lowered
    assert "exact" not in lowered
    assert "correct" not in lowered


def test_duplicate_pilot_rows_are_detected():
    rows = _pilot_rows_complete()
    rows.append(rows[0].copy())
    summary = analyzer.validate_pilot_rows(rows, expected_rows=5, expected_examples=2)
    assert summary.complete is False
    assert summary.duplicate_count == 1
    assert any("duplicate_rows" in reason for reason in summary.reasons)


def test_recovery_regression_deltas_computed_correctly(tmp_path: Path):
    pilot_root, fix6_root, postrun_root = _build_minimal_fixture(tmp_path)
    _write_jsonl(
        pilot_root / "runner_output" / "job1" / "per_example_records.jsonl",
        _pilot_rows_complete(),
    )
    out = tmp_path / "out_delta"
    analyzer.run_analysis(
        pilot_root=pilot_root,
        fix6_root=fix6_root,
        main_postrun_root=postrun_root,
        output_root=out,
        expected_rows=4,
        expected_examples=2,
    )

    with (out / "extra_action_outcomes.csv").open() as f:
        rows = list(csv.DictReader(f))

    ex1_frontier = next(r for r in rows if r["example_id"] == "ex1" and r["action_type"] == "extra_frontier")
    ex2_frontier = next(r for r in rows if r["example_id"] == "ex2" and r["action_type"] == "extra_frontier")
    assert int(ex1_frontier["delta_vs_fix24"]) == 1
    assert ex1_frontier["delta_label_vs_fix24"] == "recovery"
    assert int(ex2_frontier["delta_vs_fix24"]) == -1
    assert ex2_frontier["delta_label_vs_fix24"] == "regression"


def test_no_provider_api_calls(tmp_path: Path, monkeypatch):
    pilot_root, fix6_root, postrun_root = _build_minimal_fixture(tmp_path)
    _write_jsonl(
        pilot_root / "runner_output" / "job1" / "per_example_records.jsonl",
        _pilot_rows_complete(),
    )

    real_create = socket.create_connection

    def _deny_network(*args, **kwargs):
        raise AssertionError("network call attempted")

    monkeypatch.setattr(socket, "create_connection", _deny_network)

    out = tmp_path / "out_no_api"
    analyzer.run_analysis(
        pilot_root=pilot_root,
        fix6_root=fix6_root,
        main_postrun_root=postrun_root,
        output_root=out,
        expected_rows=4,
        expected_examples=2,
    )

    monkeypatch.setattr(socket, "create_connection", real_create)

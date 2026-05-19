from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _run_script(repo_root: Path, pilot_root: Path, fix6_root: Path, out_root: Path, expected_rows: int, expected_cases: int):
    cmd = [
        "python3",
        "scripts/analyze_fix6_extra_action_pilot.py",
        "--pilot-root",
        str(pilot_root),
        "--fix6-root",
        str(fix6_root),
        "--main-postrun-root",
        str(repo_root / "outputs/overnight_fix5_postrun_eval_20260519_20260519T134633Z"),
        "--output-root",
        str(out_root),
        "--expected-rows",
        str(expected_rows),
        "--expected-cases",
        str(expected_cases),
    ]
    return subprocess.run(cmd, cwd=repo_root, check=True, capture_output=True, text=True)


def _minimal_selected(pilot_root: Path, n: int = 2):
    selected = []
    plan = []
    for i in range(1, n + 1):
        eid = f"ex{i}"
        selected.append(
            {
                "example_id": eid,
                "dataset": "openai/gsm8k",
                "fix24_answer_canonical": "10",
                "tale_answer_canonical": "11",
                "l1_answer_canonical": "10",
                "s1_answer_canonical": "11",
                "frontier_answer_canonical": "10",
                "residual_category": "residual_tale_complementarity",
                "offline_labels": {"fix24_correct": False, "tale_correct": True},
            }
        )
        plan.append(
            {
                "example_id": eid,
                "dataset": "openai/gsm8k",
                "primary_action": "extra_frontier_diverse",
                "secondary_action": "extra_tale_retry",
                "proxy_method_frontier": "direct_reserve_semantic_frontier_v2",
                "proxy_method_tale": "external_tale_prompt_budgeting",
                "fresh_seed": 53,
                "reason": "test",
            }
        )
    _write_jsonl(pilot_root / "selected_cases.jsonl", selected)
    _write_csv(pilot_root / "extra_action_plan.csv", plan, list(plan[0].keys()))


def _minimal_fix6_tables(fix6_root: Path, n: int = 2):
    state_rows = []
    residual_rows = []
    avail_rows = []
    oracle_rows = []
    for i in range(1, n + 1):
        eid = f"ex{i}"
        state_rows.append(
            {
                "artifact": "overnight_300_unbiased",
                "split_kind": "unbiased",
                "example_id": eid,
                "dataset": "openai/gsm8k",
                "seed": 41,
                "budget": 6,
                "low_depth_flag": i == 1,
                "weak_search_flag": i == 1,
                "external_agreement_signature": "l1=s1!=tale",
                "candidate_count": 2,
                "base_policy_answer_canonical": "10",
            }
        )
        residual_rows.append(
            {
                "artifact": "overnight_300_unbiased",
                "example_id": eid,
                "fix24_correct": "False",
                "tale_correct": "True",
                "root_cause_label": "residual_tale_complementarity",
            }
        )
        avail_rows.append(
            {
                "artifact": "overnight_300_unbiased",
                "example_id": eid,
                "avail_logged_frontier_alternative_proxy": "True",
                "avail_logged_external_alternative_proxy": "True",
            }
        )
        oracle_rows.append(
            {
                "artifact": "overnight_300_unbiased",
                "example_id": eid,
                "oracle_observable_action": "logged_frontier_alternative_proxy",
                "oracle_observable_correct": "True",
            }
        )

    _write_csv(fix6_root / "fix6_state_feature_table.csv", state_rows, list(state_rows[0].keys()))
    _write_csv(fix6_root / "fix6_residual_failure_cases.csv", residual_rows, list(residual_rows[0].keys()))
    _write_csv(fix6_root / "fix6_action_availability.csv", avail_rows, list(avail_rows[0].keys()))
    _write_csv(fix6_root / "fix6_oracle_action_table.csv", oracle_rows, list(oracle_rows[0].keys()))


def _pilot_rows_complete(pilot_root: Path):
    rows = [
        {
            "example_id": "ex1",
            "dataset": "openai/gsm8k",
            "seed": 53,
            "budget": 6,
            "provider": "cohere",
            "method": "direct_reserve_semantic_frontier_v2",
            "status": "scored",
            "exact_match": 1,
            "final_answer_canonical": "10",
            "cohere_logical_api_calls": 2,
            "total_tokens": 200,
            "latency_seconds": 1.0,
            "promotion_review_record": {"candidate_trace": "ok"},
            "promotion_review_validation": {"enough_for_promotion_review": "yes", "runtime_failure_reviewable": "yes"},
            "question": "q1",
            "result_metadata": {},
        },
        {
            "example_id": "ex1",
            "dataset": "openai/gsm8k",
            "seed": 53,
            "budget": 6,
            "provider": "cohere",
            "method": "external_tale_prompt_budgeting",
            "status": "scored",
            "exact_match": 0,
            "final_answer_canonical": "11",
            "cohere_logical_api_calls": 1,
            "total_tokens": 150,
            "latency_seconds": 0.8,
            "promotion_review_record": {"candidate_trace": "ok"},
            "promotion_review_validation": {"enough_for_promotion_review": "yes", "runtime_failure_reviewable": "yes"},
            "question": "q1",
            "result_metadata": {},
        },
        {
            "example_id": "ex2",
            "dataset": "openai/gsm8k",
            "seed": 53,
            "budget": 6,
            "provider": "cohere",
            "method": "direct_reserve_semantic_frontier_v2",
            "status": "scored",
            "exact_match": 0,
            "final_answer_canonical": "12",
            "cohere_logical_api_calls": 2,
            "total_tokens": 210,
            "latency_seconds": 1.1,
            "promotion_review_record": {"candidate_trace": "ok"},
            "promotion_review_validation": {"enough_for_promotion_review": "yes", "runtime_failure_reviewable": "yes"},
            "question": "q2",
            "result_metadata": {},
        },
        {
            "example_id": "ex2",
            "dataset": "openai/gsm8k",
            "seed": 53,
            "budget": 6,
            "provider": "cohere",
            "method": "external_tale_prompt_budgeting",
            "status": "scored",
            "exact_match": 1,
            "final_answer_canonical": "11",
            "cohere_logical_api_calls": 1,
            "total_tokens": 140,
            "latency_seconds": 0.9,
            "promotion_review_record": {"candidate_trace": "ok"},
            "promotion_review_validation": {"enough_for_promotion_review": "yes", "runtime_failure_reviewable": "yes"},
            "question": "q2",
            "result_metadata": {},
        },
    ]
    _write_jsonl(
        pilot_root
        / "runner_output/cohere_real_model_cost_normalized_validation_fix6_extra_action_live_TEST/per_example_records.jsonl",
        rows,
    )


def test_missing_pilot_rows_produces_readiness_report(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    pilot_root = tmp_path / "pilot"
    fix6_root = tmp_path / "fix6"
    out_root = tmp_path / "out"
    _minimal_selected(pilot_root, n=2)

    _run_script(repo_root, pilot_root, fix6_root, out_root, expected_rows=4, expected_cases=2)

    assert (out_root / "pilot_readiness_report.md").exists()
    assert (out_root / "pilot_readiness_metrics.json").exists()
    assert not (out_root / "pilot_analysis_report.md").exists()


def test_incomplete_pilot_rows_produces_readiness_report(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    pilot_root = tmp_path / "pilot"
    fix6_root = tmp_path / "fix6"
    out_root = tmp_path / "out"
    _minimal_selected(pilot_root, n=2)
    _write_jsonl(
        pilot_root
        / "runner_output/cohere_real_model_cost_normalized_validation_fix6_extra_action_live_TEST/per_example_records.jsonl",
        [
            {
                "example_id": "ex1",
                "dataset": "openai/gsm8k",
                "seed": 53,
                "budget": 6,
                "provider": "cohere",
                "method": "direct_reserve_semantic_frontier_v2",
                "status": "scored",
            }
        ],
    )

    _run_script(repo_root, pilot_root, fix6_root, out_root, expected_rows=4, expected_cases=2)
    metrics = json.loads((out_root / "pilot_readiness_metrics.json").read_text())
    assert metrics["ready"] is False
    assert metrics["reason"] == "pilot_rows_incomplete"


def test_complete_tiny_pilot_produces_outcomes_and_training_rows(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    pilot_root = tmp_path / "pilot"
    fix6_root = tmp_path / "fix6"
    out_root = tmp_path / "out"

    _minimal_selected(pilot_root, n=2)
    _minimal_fix6_tables(fix6_root, n=2)
    _pilot_rows_complete(pilot_root)

    _run_script(repo_root, pilot_root, fix6_root, out_root, expected_rows=4, expected_cases=2)

    assert (out_root / "pilot_analysis_report.md").exists()
    assert (out_root / "pilot_analysis_metrics.json").exists()
    assert (out_root / "extra_action_outcomes.csv").exists()
    assert (out_root / "lovec_training_rows.csv").exists()
    assert (out_root / "recommended_lovec_policy.json").exists()

    rows = list(csv.DictReader((out_root / "extra_action_outcomes.csv").open()))
    assert len(rows) == 2

    # ex1: frontier correct while fix24 false -> recovery
    ex1 = next(r for r in rows if r["example_id"] == "ex1")
    assert ex1["frontier_effect_label"] == "recovery"
    assert ex1["delta_frontier_vs_fix24"] == "1"


def test_gold_exact_fields_excluded_from_feature_columns(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    pilot_root = tmp_path / "pilot"
    fix6_root = tmp_path / "fix6"
    out_root = tmp_path / "out"

    _minimal_selected(pilot_root, n=2)
    _minimal_fix6_tables(fix6_root, n=2)
    _pilot_rows_complete(pilot_root)

    _run_script(repo_root, pilot_root, fix6_root, out_root, expected_rows=4, expected_cases=2)

    header = list(csv.DictReader((out_root / "lovec_training_rows.csv").open()).fieldnames or [])
    low = "|".join(header).lower()
    assert "gold" not in low
    assert "exact_match" not in low
    # label columns are allowed, but feature columns should not include *correct* names.
    feature_cols = [h for h in header if h.startswith("f_")]
    assert not any("correct" in h.lower() for h in feature_cols)


def test_duplicate_pilot_rows_detected(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    pilot_root = tmp_path / "pilot"
    fix6_root = tmp_path / "fix6"
    out_root = tmp_path / "out"
    _minimal_selected(pilot_root, n=2)

    dup = {
        "example_id": "ex1",
        "dataset": "openai/gsm8k",
        "seed": 53,
        "budget": 6,
        "provider": "cohere",
        "method": "direct_reserve_semantic_frontier_v2",
        "status": "scored",
    }
    _write_jsonl(
        pilot_root
        / "runner_output/cohere_real_model_cost_normalized_validation_fix6_extra_action_live_TEST/per_example_records.jsonl",
        [dup, dup, dup, dup],
    )

    _run_script(repo_root, pilot_root, fix6_root, out_root, expected_rows=4, expected_cases=2)
    metrics = json.loads((out_root / "pilot_readiness_metrics.json").read_text())
    assert metrics["reason"] == "duplicate_rows_detected"


def test_no_provider_api_calls_by_script(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    pilot_root = tmp_path / "pilot"
    fix6_root = tmp_path / "fix6"
    out_root = tmp_path / "out"
    _minimal_selected(pilot_root, n=1)

    # Missing rows path should finish without any provider integration.
    r = _run_script(repo_root, pilot_root, fix6_root, out_root, expected_rows=2, expected_cases=1)
    assert r.returncode == 0
    assert (out_root / "pilot_readiness_report.md").exists()

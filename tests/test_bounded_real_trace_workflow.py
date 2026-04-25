from __future__ import annotations

import csv
import json
import shutil
import subprocess
from pathlib import Path


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def test_bounded_collection_dry_run_and_stratification(tmp_path: Path) -> None:
    loss_csv = tmp_path / "per_case_results.csv"
    _write_csv(
        loss_csv,
        ["example_id", "dataset", "question", "gold_answer", "failure_type", "absent_from_tree", "present_not_selected", "is_correct"],
        [
            ["a1", "openai/gsm8k", "q1", "4", "absent_from_tree", "1", "0", "0"],
            ["a2", "openai/gsm8k", "q2", "6", "present_not_selected", "0", "1", "0"],
            ["a3", "openai/gsm8k", "q3", "8", "correct", "0", "0", "1"],
        ],
    )

    ts = "20260425T_BOUNDED_COLLECTION_TEST"
    out = Path("outputs") / f"bounded_real_trace_collection_{ts}"
    if out.exists():
        shutil.rmtree(out)

    subprocess.run(
        [
            "python",
            "scripts/run_bounded_real_trace_collection.py",
            "--timestamp",
            ts,
            "--loss-artifact",
            str(loss_csv),
            "--absent-count",
            "1",
            "--present-count",
            "1",
            "--control-count",
            "1",
            "--budgets",
            "4",
            "--seeds",
            "11",
            "--dry-run",
        ],
        check=True,
    )

    assert (out / "planned_cases.csv").exists()
    assert (out / "collection_summary.csv").exists()
    assert (out / "run_manifest.json").exists()

    manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["real_api_enabled"] is False

    with (out / "planned_cases.csv").open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    assert {r["stratum"] for r in rows} == {"absent_from_tree", "present_not_selected", "control_correct"}


def test_grouped_problem_holdout_no_leakage_and_pairwise_model(tmp_path: Path) -> None:
    examples = tmp_path / "examples.csv"
    _write_csv(
        examples,
        [
            "provider",
            "model",
            "dataset",
            "seed",
            "budget",
            "example_id",
            "method",
            "candidate_answer_normalized",
            "selected_answer_group",
            "gold_answer",
            "normalized_gold_answer",
            "was_selected_by_current_controller",
            "answer_group_support",
            "label",
            "stratum",
        ],
        [
            ["cohere", "command-r", "openai/gsm8k", "11", "4", "e1", "strict_f3", "4", "4", "4", "4", "1", "2", "1", "present_not_selected"],
            ["cohere", "command-r", "openai/gsm8k", "11", "4", "e1", "strict_f3", "5", "4", "4", "4", "0", "1", "0", "present_not_selected"],
            ["cohere", "command-r", "openai/gsm8k", "11", "6", "e2", "strict_f3", "8", "8", "9", "9", "1", "1", "0", "absent_from_tree"],
            ["cohere", "command-r", "openai/gsm8k", "11", "6", "e2", "strict_f3", "9", "8", "9", "9", "0", "2", "1", "absent_from_tree"],
            ["cohere", "command-r", "openai/gsm8k", "23", "8", "e3", "strict_f3", "7", "7", "7", "7", "1", "2", "1", "control_correct"],
            ["cohere", "command-r", "openai/gsm8k", "23", "8", "e3", "strict_f3", "6", "7", "7", "7", "0", "1", "0", "control_correct"],
            ["cohere", "command-r", "openai/gsm8k", "23", "8", "e4", "strict_f3", "3", "3", "3", "3", "1", "2", "1", "control_correct"],
            ["cohere", "command-r", "openai/gsm8k", "23", "8", "e4", "strict_f3", "1", "3", "3", "3", "0", "1", "0", "control_correct"],
            ["cohere", "command-r", "openai/gsm8k", "23", "8", "e5", "strict_f3", "1", "1", "2", "2", "1", "2", "0", "present_not_selected"],
            ["cohere", "command-r", "openai/gsm8k", "23", "8", "e5", "strict_f3", "2", "1", "2", "2", "0", "1", "1", "present_not_selected"],
        ],
    )

    ts = "20260425T_GROUPED_SPLIT_TEST"
    out = Path("outputs") / f"trace_level_learned_branch_scorer_train_{ts}"
    if out.exists():
        shutil.rmtree(out)

    subprocess.run(
        [
            "python",
            "scripts/train_learned_branch_scorer.py",
            "--timestamp",
            ts,
            "--dataset-examples",
            str(examples),
            "--split",
            "grouped_problem_holdout",
            "--output-prefix",
            "trace_level_learned_branch_scorer_train",
        ],
        check=True,
    )

    with (out / "split_assignments.csv").open("r", encoding="utf-8", newline="") as f:
        assignments = list(csv.DictReader(f))
    split_map: dict[str, set[str]] = {}
    for row in assignments:
        split_map.setdefault(row["example_id"], set()).add(row["assigned_partition"])
    assert all(len(v) == 1 for v in split_map.values())

    with (out / "predictions.csv").open("r", encoding="utf-8", newline="") as f:
        preds = list(csv.DictReader(f))
    assert any(r.get("model") == "pairwise_logistic" for r in preds)


def test_eval_required_outputs_and_columns(tmp_path: Path) -> None:
    pred = tmp_path / "predictions.csv"
    _write_csv(
        pred,
        [
            "provider",
            "seed",
            "budget",
            "dataset",
            "example_id",
            "method",
            "candidate_answer_normalized",
            "label",
            "was_selected_by_current_controller",
            "answer_group_support",
            "score",
            "model",
            "split",
            "stratum",
        ],
        [
            ["cohere", "11", "4", "openai/gsm8k", "e1", "strict_f3", "4", "1", "1", "2", "0.8", "logistic_regression", "grouped_problem_holdout", "present_not_selected"],
            ["cohere", "11", "4", "openai/gsm8k", "e1", "strict_f3", "5", "0", "0", "1", "0.1", "logistic_regression", "grouped_problem_holdout", "present_not_selected"],
            ["cohere", "23", "8", "openai/gsm8k", "e2", "strict_f3", "9", "1", "0", "1", "0.7", "pairwise_logistic", "grouped_problem_holdout", "control_correct"],
            ["cohere", "23", "8", "openai/gsm8k", "e2", "strict_f3", "8", "0", "1", "2", "0.2", "pairwise_logistic", "grouped_problem_holdout", "control_correct"],
        ],
    )

    ts = "20260425T_TRACE_EVAL_REQUIRED_TEST"
    out = Path("outputs") / f"bounded_real_trace_learned_scorer_eval_{ts}"
    if out.exists():
        shutil.rmtree(out)

    subprocess.run(
        [
            "python",
            "scripts/run_trace_level_learned_scorer_eval.py",
            "--timestamp",
            ts,
            "--predictions",
            str(pred),
            "--output-prefix",
            "bounded_real_trace_learned_scorer_eval",
        ],
        check=True,
    )

    required = [
        "summary.csv",
        "selector_comparison.csv",
        "case_level_selection.csv",
        "gold_present_subset_metrics.csv",
        "coverage_vs_selection_breakdown.csv",
        "degradation_cases.csv",
        "per_stratum_summary.csv",
        "split_assignments.csv",
        "README.md",
    ]
    for name in required:
        assert (out / name).exists()

    with (out / "case_level_selection.csv").open("r", encoding="utf-8", newline="") as f:
        fields = list(csv.DictReader(f).fieldnames or [])
    assert {"selector", "selected_gold", "gold_present", "stratum"}.issubset(set(fields))

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def _build_tiny_trace_package(base: Path, with_branch_rows: bool = True) -> None:
    _write_csv(
        base / "ten_case_inputs.csv",
        ["case_idx", "example_id", "seed", "budget", "dataset", "question", "gold_answer_raw", "gold_answer"],
        [
            ["1", "e1", "11", "4", "openai/gsm8k", "q1", "4", "4"],
            ["2", "e2", "23", "8", "openai/gsm8k", "q2", "9", "9"],
        ],
    )
    _write_csv(
        base / "per_case_results.csv",
        ["case_idx", "example_id", "seed", "budget", "method", "runtime_method", "final_answer", "normalized_answer", "is_correct", "failure_type", "actions", "expansions", "verifications", "dataset"],
        [
            ["1", "e1", "11", "4", "strict_f3", "strict_f3", "4", "4", "1", "correct", "4", "3", "1", "openai/gsm8k"],
            ["1", "e1", "11", "4", "external_l1_max", "external_l1_max", "5", "5", "0", "present_not_selected", "1", "1", "0", "openai/gsm8k"],
            ["2", "e2", "23", "8", "strict_f3", "strict_f3", "8", "8", "0", "present_not_selected", "8", "8", "1", "openai/gsm8k"],
        ],
    )
    if with_branch_rows:
        _write_csv(
            base / "branch_table.csv",
            ["example_id", "seed", "budget", "dataset", "provider", "model", "method", "branch_id", "parent_branch_id", "branch_depth", "normalized_answer", "extracted_answer", "branch_score", "base_priority_score"],
            [
                ["e1", "11", "4", "openai/gsm8k", "cohere", "command-r", "strict_f3", "b1", "", "1", "4", "4", "0.9", "0.7"],
                ["e1", "11", "4", "openai/gsm8k", "cohere", "command-r", "strict_f3", "b2", "", "1", "5", "5", "0.2", "0.2"],
                ["e2", "23", "8", "openai/gsm8k", "cohere", "command-r", "strict_f3", "b3", "", "2", "8", "8", "0.2", "0.2"],
                ["e2", "23", "8", "openai/gsm8k", "cohere", "command-r", "strict_f3", "b4", "", "2", "9", "9", "0.6", "0.4"],
            ],
        )
    else:
        _write_csv(base / "branch_table.csv", ["example_id"], [])

    _write_csv(
        base / "action_trace.csv",
        ["example_id", "seed", "budget", "method", "action_index", "group_key", "branch_id", "action"],
        [
            ["e1", "11", "4", "strict_f3", "0", "4", "b1", "expand"],
            ["e1", "11", "4", "strict_f3", "1", "5", "b2", "score"],
            ["e2", "23", "8", "strict_f3", "0", "9", "b4", "expand"],
        ],
    )
    if with_branch_rows:
        _write_csv(
            base / "answer_group_table.csv",
            ["example_id", "seed", "budget", "dataset", "provider", "model", "method", "answer_group", "branch_id"],
            [
                ["e1", "11", "4", "openai/gsm8k", "cohere", "command-r", "strict_f3", "4", "b1"],
                ["e1", "11", "4", "openai/gsm8k", "cohere", "command-r", "strict_f3", "5", "b2"],
                ["e2", "23", "8", "openai/gsm8k", "cohere", "command-r", "strict_f3", "9", "b4"],
            ],
        )
    else:
        _write_csv(
            base / "answer_group_table.csv",
            ["example_id", "seed", "budget", "dataset", "provider", "model", "method", "answer_group", "branch_id"],
            [],
        )
    _write_csv(base / "reasoning_diversity_components.csv", ["example_id", "seed", "budget", "method", "branch_id", "plausibility_score"], [])


def test_trace_level_pipeline_smoke(tmp_path: Path) -> None:
    trace_dir = tmp_path / "trace_pkg"
    _build_tiny_trace_package(trace_dir, with_branch_rows=True)

    ts_data = "20260425T_TRACE_DATASET_TEST"
    ts_train = "20260425T_TRACE_TRAIN_TEST"
    ts_eval = "20260425T_TRACE_EVAL_TEST"

    out_data = Path("outputs") / f"trace_level_learned_branch_scorer_dataset_{ts_data}"
    out_train = Path("outputs") / f"trace_level_learned_branch_scorer_train_{ts_train}"
    out_eval = Path("outputs") / f"trace_level_learned_scorer_eval_{ts_eval}"
    for out in [out_data, out_train, out_eval]:
        if out.exists():
            shutil.rmtree(out)

    subprocess.run(
        [
            "python",
            "scripts/build_trace_level_learned_branch_scorer_dataset.py",
            "--timestamp",
            ts_data,
            "--trace-dir",
            str(trace_dir),
        ],
        check=True,
    )
    assert (out_data / "examples.csv").exists()
    assert (out_data / "case_coverage.csv").exists()

    subprocess.run(
        [
            "python",
            "scripts/train_learned_branch_scorer.py",
            "--timestamp",
            ts_train,
            "--dataset-examples",
            str(out_data / "examples.csv"),
        ],
        check=True,
    )
    assert (out_train / "split_metrics.csv").exists()
    assert (out_train / "case_level_selection_metrics.csv").exists()

    subprocess.run(
        [
            "python",
            "scripts/run_trace_level_learned_scorer_eval.py",
            "--timestamp",
            ts_eval,
            "--predictions",
            str(out_train / "predictions.csv"),
        ],
        check=True,
    )
    assert (out_eval / "summary.csv").exists()
    assert (out_eval / "case_level_selection.csv").exists()
    assert (out_eval / "degradation_cases.csv").exists()

    with (out_data / "examples.csv").open("r", encoding="utf-8", newline="") as f:
        fields = list(csv.DictReader(f).fieldnames or [])
    required = {
        "branch_id",
        "parent_branch_id",
        "candidate_answer_normalized",
        "normalized_gold_answer",
        "is_gold_candidate",
        "was_selected_by_current_controller",
        "source_type",
    }
    assert required.issubset(set(fields))


def test_trace_level_builder_proxy_fallback(tmp_path: Path) -> None:
    trace_dir = tmp_path / "trace_pkg_proxy"
    _build_tiny_trace_package(trace_dir, with_branch_rows=False)

    ts_data = "20260425T_TRACE_DATASET_PROXY_TEST"
    out_data = Path("outputs") / f"trace_level_learned_branch_scorer_dataset_{ts_data}"
    if out_data.exists():
        shutil.rmtree(out_data)

    subprocess.run(
        [
            "python",
            "scripts/build_trace_level_learned_branch_scorer_dataset.py",
            "--timestamp",
            ts_data,
            "--trace-dir",
            str(trace_dir),
        ],
        check=True,
    )

    with (out_data / "examples.csv").open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    assert rows
    assert any(str(r.get("source_type")) == "proxy_answer_group_only" for r in rows)

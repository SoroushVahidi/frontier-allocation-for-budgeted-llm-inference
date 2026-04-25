from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path


def _make_per_example_csv(path: Path) -> None:
    path.write_text(
        "provider,model,dataset,seed,budget,example_id,method,is_correct,failure_type,absent_from_tree,present_not_selected,actions_used,expansions,verifications\n"
        "cohere,command-r-plus-08-2024,openai/gsm8k,11,4,e1,strict_f3,0,present_not_selected,0,1,4,4,1\n"
        "cohere,command-r-plus-08-2024,openai/gsm8k,11,4,e1,external_l1_max,1,correct,0,0,1,1,0\n"
        "cohere,command-r-plus-08-2024,openai/gsm8k,11,4,e1,strict_gate1_cap_k6,0,present_not_selected,0,1,4,4,1\n"
        "cohere,command-r-plus-08-2024,openai/gsm8k,23,8,e2,strict_f3,0,absent_from_tree,1,0,8,8,2\n"
        "cohere,command-r-plus-08-2024,openai/gsm8k,23,8,e2,external_l1_max,0,absent_from_tree,1,0,2,2,0\n"
        "cohere,command-r-plus-08-2024,openai/gsm8k,23,8,e2,strict_gate1_cap_k6,1,correct,0,0,8,8,2\n",
        encoding="utf-8",
    )


def test_dataset_builder_training_eval_smoke(tmp_path: Path) -> None:
    src = tmp_path / "per_example_rows.csv"
    _make_per_example_csv(src)

    ts_data = "20260425T_LEARNED_SCORER_DATASET_TEST"
    ts_train = "20260425T_LEARNED_SCORER_TRAIN_TEST"
    ts_eval = "20260425T_LEARNED_SCORER_EVAL_TEST"

    out_data = Path("outputs") / f"learned_branch_scorer_dataset_{ts_data}"
    out_train = Path("outputs") / f"learned_branch_scorer_train_{ts_train}"
    out_eval = Path("outputs") / f"learned_branch_scorer_eval_{ts_eval}"
    for out in [out_data, out_train, out_eval]:
        if out.exists():
            shutil.rmtree(out)

    subprocess.run(
        [
            "python",
            "scripts/build_learned_branch_scorer_dataset.py",
            "--timestamp",
            ts_data,
            "--input-per-example",
            str(src),
            "--budgets",
            "4,8",
            "--seeds",
            "11,23",
        ],
        check=True,
    )

    assert (out_data / "examples.csv").exists()
    assert (out_data / "feature_schema.json").exists()
    assert (out_data / "dataset_summary.csv").exists()
    assert (out_data / "README.md").exists()

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

    assert (out_train / "metrics.csv").exists()
    assert (out_train / "split_metrics.csv").exists()
    assert (out_train / "predictions.csv").exists()
    assert (out_train / "model_comparison.csv").exists()
    assert (out_train / "selected_model.joblib").exists()

    subprocess.run(
        [
            "python",
            "scripts/run_learned_branch_scorer_eval.py",
            "--timestamp",
            ts_eval,
            "--predictions",
            str(out_train / "predictions.csv"),
        ],
        check=True,
    )

    assert (out_eval / "summary.csv").exists()
    assert (out_eval / "per_budget_seed_summary.csv").exists()
    assert (out_eval / "paired_deltas.csv").exists()
    assert (out_eval / "gold_present_subset_metrics.csv").exists()
    assert (out_eval / "predictions_with_scores.csv").exists()

    with (out_eval / "predictions_with_scores.csv").open("r", encoding="utf-8", newline="") as f:
        fields = list(csv.DictReader(f).fieldnames or [])
    assert "method" in fields
    assert "present_not_selected" in fields
    assert "absent_from_tree" in fields

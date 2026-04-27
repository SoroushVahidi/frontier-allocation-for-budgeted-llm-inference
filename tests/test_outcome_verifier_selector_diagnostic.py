from __future__ import annotations

from pathlib import Path

from scripts.run_outcome_verifier_selector_diagnostic import (
    _group_by_case,
    _loeo_train_predict,
    build_training_rows,
)


def test_answer_bucket_like_training_rows_no_gold_leakage() -> None:
    buckets = [
        {
            "dataset": "openai/gsm8k",
            "example_id": "ex1",
            "seed": 23,
            "budget": 4,
            "normalized_answer": "42",
            "support_count": 3,
            "max_maturity": 2,
            "mean_maturity": 1.5,
            "family_count": 2,
            "candidate_branch_count": 3,
            "equals_external_l1_max": 1,
            "equals_strict_f3": 0,
            "equals_gold_offline": 1,
            "gold_answer": "42",
        },
        {
            "dataset": "openai/gsm8k",
            "example_id": "ex1",
            "seed": 23,
            "budget": 4,
            "normalized_answer": "41",
            "support_count": 1,
            "max_maturity": 1,
            "mean_maturity": 1.0,
            "family_count": 1,
            "candidate_branch_count": 1,
            "equals_external_l1_max": 0,
            "equals_strict_f3": 1,
            "equals_gold_offline": 0,
            "gold_answer": "42",
        },
    ]
    rows = build_training_rows(buckets)
    assert len(rows) == 2
    # label exists, but gold-equality feature does not.
    assert "label_is_correct" in rows[0]
    assert "equals_gold_offline" not in rows[0]


def test_loeo_split_by_example_id_no_train_test_overlap() -> None:
    rows = []
    for ex in ["a", "b", "c"]:
        for ans, label in [("1", 1), ("2", 0)]:
            rows.append(
                {
                    "dataset": "openai/gsm8k",
                    "example_id": ex,
                    "seed": 23,
                    "budget": 4,
                    "normalized_answer": ans,
                    "support_count": 1.0,
                    "max_maturity": 1.0,
                    "mean_maturity": 1.0,
                    "family_count": 1.0,
                    "candidate_branch_count": 1.0,
                    "equals_external_l1_max": 0.0,
                    "equals_strict_f3": 0.0,
                    "parse_success": 1.0,
                    "numeric_parse_success": 1.0,
                    "numeric_abs_value": float(ans),
                    "label_is_correct": label,
                    "gold_answer": "1",
                }
            )
    pred_rows, fold_rows = _loeo_train_predict(rows)
    assert len(pred_rows) == len(rows)
    heldout_ids = {r["example_id"] for r in fold_rows}
    assert heldout_ids == {"a", "b", "c"}


def test_selector_summary_consistency_shape() -> None:
    rows = [
        {"dataset": "d", "seed": 1, "budget": 1, "example_id": "e1"},
        {"dataset": "d", "seed": 1, "budget": 1, "example_id": "e1"},
    ]
    grouped = _group_by_case(rows)
    assert len(grouped) == 1
    assert len(next(iter(grouped.values()))) == 2


def test_script_source_contains_no_real_api_calls() -> None:
    script = Path("scripts/run_outcome_verifier_selector_diagnostic.py").read_text(encoding="utf-8")
    banned = ["requests.post(", "requests.get(", "openai(", "cohere.client", "client.chat(", "api.openai.com"]
    lowered = script.lower()
    for tok in banned:
        assert tok not in lowered

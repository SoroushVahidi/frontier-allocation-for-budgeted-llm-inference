from scripts.evaluate_best_methods_on_external_loss_cases import (
    choose_deployable_answer,
    dedupe_cases,
    select_cases,
)


def test_trace_complete_prioritized_before_final_rows() -> None:
    trace = [{"dataset": "d", "example_id": f"t{i}", "seed": 1, "budget": 4, "_selection_source": "trace_complete"} for i in range(3)]
    final = [{"dataset": "d", "example_id": f"f{i}", "seed": 1, "budget": 4, "_selection_source": "final_row_only"} for i in range(4)]
    selected, stats = select_cases(trace, final, target=5)
    assert [r["example_id"] for r in selected[:3]] == ["t0", "t1", "t2"]
    assert stats["trace_complete_selected"] == 3
    assert stats["final_row_only_selected"] == 2


def test_deduplication_key_dataset_example_seed_budget() -> None:
    rows = [
        {"dataset": "d", "example_id": "e1", "seed": 2, "budget": 4},
        {"dataset": "d", "example_id": "e1", "seed": 2, "budget": 4},
        {"dataset": "d", "example_id": "e1", "seed": 2, "budget": 8},
    ]
    out = dedupe_cases(rows)
    assert len(out) == 2


def test_deployable_selection_does_not_use_gold() -> None:
    row = {
        "our_final_answer": "wrong",
        "selected_answer_group": "also_wrong",
        "selected_answer_support": 0,
        "top1_support": 1,
        "gold_answer": "correct",
    }
    chosen = choose_deployable_answer(row)
    assert chosen in {"wrong", "also_wrong"}
    assert chosen != "correct"


def test_oracle_is_eval_only_convention() -> None:
    # Oracle should be tracked in evaluation tables, not used by deployable chooser.
    row = {
        "our_final_answer": "x",
        "selected_answer_group": "y",
        "oracle_selector_answer": "gold",
        "gold_answer": "gold",
    }
    chosen = choose_deployable_answer(row)
    assert chosen in {"x", "y"}
    assert chosen != row["oracle_selector_answer"]

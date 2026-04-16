from experiments.frontier_router import (
    derive_oracle_labels,
    fit_lightweight_router,
    selector_accuracy_from_predictions,
)


def test_derive_oracle_labels_prefers_correct_then_lower_cost() -> None:
    rows = [
        {
            "example_id": "ex1",
            "strategy": "reasoning_greedy",
            "is_correct": False,
            "actions_used": 1,
            "expansions": 1,
            "verifications": 0,
        },
        {
            "example_id": "ex1",
            "strategy": "adaptive_min_expand_1",
            "is_correct": True,
            "actions_used": 2,
            "expansions": 2,
            "verifications": 0,
        },
        {
            "example_id": "ex1",
            "strategy": "adaptive_min_expand_2",
            "is_correct": True,
            "actions_used": 3,
            "expansions": 3,
            "verifications": 0,
        },
    ]

    labels = derive_oracle_labels(
        rows,
        strategy_order=["reasoning_greedy", "adaptive_min_expand_1", "adaptive_min_expand_2"],
    )

    assert labels == {"ex1": "adaptive_min_expand_1"}


def test_fit_lightweight_router_uses_constant_mode_for_single_class() -> None:
    fit = fit_lightweight_router(
        ["What is 2+2?", "What is 3+3?"],
        ["reasoning_greedy", "reasoning_greedy"],
        seed=7,
    )

    assert fit.mode == "constant"
    assert fit.model.predict(["Hard algebra question"])[0] == "reasoning_greedy"


def test_selector_accuracy_from_predictions_matches_rows() -> None:
    rows = [
        {
            "example_id": "a",
            "strategy": "reasoning_greedy",
            "is_correct": True,
            "actions_used": 1,
        },
        {
            "example_id": "a",
            "strategy": "adaptive_min_expand_1",
            "is_correct": False,
            "actions_used": 2,
        },
        {
            "example_id": "b",
            "strategy": "reasoning_greedy",
            "is_correct": False,
            "actions_used": 1,
        },
        {
            "example_id": "b",
            "strategy": "adaptive_min_expand_1",
            "is_correct": True,
            "actions_used": 2,
        },
    ]

    metrics = selector_accuracy_from_predictions(
        rows,
        {"a": "reasoning_greedy", "b": "adaptive_min_expand_1"},
    )

    assert metrics["accuracy"] == 1.0
    assert metrics["avg_actions"] == 1.5
    assert metrics["n_examples"] == 2.0

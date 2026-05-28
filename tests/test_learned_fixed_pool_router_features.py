from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")
router_mod = pytest.importorskip("scripts.build_and_eval_learned_fixed_pool_router")

_make_pattern_features = router_mod._make_pattern_features
add_calibration_feature_columns = router_mod.add_calibration_feature_columns
apply_dynamic_actions = router_mod.apply_dynamic_actions
compute_calibration_stats = router_mod.compute_calibration_stats


def _base_df() -> pd.DataFrame:
    rows = [
        {
            "scenario_id": "s1",
            "provider": "cohere",
            "dataset": "openai/gsm8k",
            "example_id": "a",
            "seed": 71,
            "budget": 6,
            "question": "What is 2+2?",
            "gold_answer": "4",
            "frontier_answer": "4",
            "L1_answer": "4",
            "S1_answer": "5",
            "TALE_answer": "6",
            "frontier_correct": 1,
            "L1_correct": 1,
            "S1_correct": 0,
            "TALE_correct": 0,
            "pooled4_answer": "4",
            "pooled4_correct": 1,
            "agreement_only_answer": "4",
            "agreement_only_correct": 1,
            "always_s1_correct": 0,
            "oracle_best_source_correct": 1,
            "oracle_best_action_correct": 1,
        },
        {
            "scenario_id": "s1",
            "provider": "cohere",
            "dataset": "openai/gsm8k",
            "example_id": "b",
            "seed": 71,
            "budget": 6,
            "question": "What is 7-3?",
            "gold_answer": "4",
            "frontier_answer": "2",
            "L1_answer": "4",
            "S1_answer": "4",
            "TALE_answer": "4",
            "frontier_correct": 0,
            "L1_correct": 1,
            "S1_correct": 1,
            "TALE_correct": 1,
            "pooled4_answer": "4",
            "pooled4_correct": 1,
            "agreement_only_answer": "4",
            "agreement_only_correct": 1,
            "always_s1_correct": 1,
            "oracle_best_source_correct": 1,
            "oracle_best_action_correct": 1,
        },
    ]
    return pd.DataFrame(rows)


def test_make_pattern_features_detects_two_two_split() -> None:
    f = _make_pattern_features(frontier="10", l1="10", s1="20", tale="20")
    assert f["two_two_split"] == 1
    assert f["all_four_agree"] == 0
    assert f["all_different"] == 0
    assert f["unique_answer_count"] == 2


def test_calibration_features_are_train_derived() -> None:
    train = _base_df().copy()
    test = _base_df().copy()
    # Alter test correctness strongly; train-derived calibration should remain unchanged.
    test["frontier_correct"] = 0
    cal = compute_calibration_stats(train)
    out1 = add_calibration_feature_columns(test, cal)
    out2 = add_calibration_feature_columns(test, cal)
    assert (out1["train_raw_acc_frontier"] == out2["train_raw_acc_frontier"]).all()
    assert (out1["train_best_source_raw"] == out2["train_best_source_raw"]).all()


def test_dynamic_actions_populate_fold_defined_labels() -> None:
    df = _base_df().copy()
    cal = compute_calibration_stats(df)
    out = apply_dynamic_actions(df, cal)
    assert "raw_spread_regime_selector_correct" in out.columns
    assert "beta_shrinkage_regime_selector_correct" in out.columns
    assert "dominant_source_action_correct" in out.columns
    assert set(out["raw_spread_regime_selector_correct"].unique()).issubset({0, 1})
    assert set(out["beta_shrinkage_regime_selector_correct"].unique()).issubset({0, 1})

from __future__ import annotations

import math

import pandas as pd

from scripts.evaluate_rg_eb_action_router import (
    Variant,
    action_answer,
    action_ok,
    bucket_keys,
    fit_model,
    predict_row,
    runtime_features,
    score_post,
    source_stats_from_df,
)


def _base_row(example_id: str = "e1", provider: str = "cohere", dataset: str = "openai/gsm8k") -> dict:
    return {
        "example_id": example_id,
        "scenario_id": f"{provider}_{'gsm8k' if 'gsm8k' in dataset else 'math500'}",
        "provider": provider,
        "dataset": dataset,
        "question": "What is 2 + 3?",
        "gold": "5",
        "frontier_ans": "5",
        "frontier_ok": 1,
        "L1_ans": "5",
        "L1_ok": 1,
        "S1_ans": "4",
        "S1_ok": 0,
        "TALE_ans": "5",
        "TALE_ok": 1,
        "agreement_pattern": "l1=tale!=s1",
        "unique_answer_count": 2,
        "majority_size": 3,
        "has_majority": 1,
        "all_four_agree": 0,
        "all_different": 0,
        "two_two_split": 0,
        "three_one_split": 1,
        "external_majority_exists": 1,
        "external_majority_excludes_frontier": 0,
        "external_majority_excludes_S1": 1,
        "L1_TALE_agree": 1,
        "S1_in_majority": 0,
        "S1_isolated": 1,
        "frontier_in_majority": 1,
        "frontier_isolated": 0,
        "question_length_bucket": "short",
        "number_count_bucket": "0_2",
        "has_fraction": 0,
        "has_equation": 0,
        "difficulty_proxy": "easy",
        "pooled4_decision": "5",
        "agreement_only_decision": "5",
        "beta_shrinkage_decision": "5",
        "c1d_decision": "5",
        "c1a_t005_decision": "5",
        "always_s1_decision": "4",
        "oracle_best_action_decision": "5",
        "pooled4_ok": 1,
        "agreement_only_ok": 1,
        "beta_shrinkage_ok": 1,
        "c1d_ok": 1,
        "c1a_t005_ok": 1,
        "always_s1_ok": 0,
        "oracle_best_action_ok": 1,
        "oracle_best_source_ok": 1,
        "source_split": "official",
    }


def _variant(**kw) -> Variant:
    base = dict(
        name="v",
        family="RGEB-test",
        actions=["pooled4", "agreement_only", "beta_shrinkage", "C1d", "frontier", "S1"],
        alpha0=1.0,
        beta0=1.0,
        scoring="mean",
        lcb_q=0.1,
        min_support=5,
        bucket_mode="hierarchical",
        include_provider_dataset=True,
        provider_free_calibration=False,
    )
    base.update(kw)
    return Variant(**base)


def test_action_label_construction_and_ok():
    row = pd.Series(_base_row())
    stats = source_stats_from_df(pd.DataFrame([_base_row()]))
    ans = action_answer(row, "pooled4", stats)
    assert ans == "5"
    assert action_ok(row, "pooled4", ans) == 1


def test_beta_mean_and_lcb_scoring_order():
    v_mean = _variant(scoring="mean")
    v_lcb = _variant(scoring="lcb")
    mean_score = score_post(ok=8, n=10, v=v_mean)
    lcb_score = score_post(ok=8, n=10, v=v_lcb)
    assert 0.0 <= lcb_score <= mean_score <= 1.0


def test_provider_free_bucket_excludes_provider_dataset():
    row = pd.Series(_base_row())
    stats = source_stats_from_df(pd.DataFrame([_base_row()]))
    f = runtime_features(row, stats)
    v = _variant(bucket_mode="provider_free", include_provider_dataset=False, provider_free_calibration=True)
    keys = bucket_keys(v, f)
    assert keys[0][0] == "provider_free"
    key = keys[0][1]
    assert row["provider"] not in key
    assert row["dataset"] not in key


def test_hierarchical_backoff_and_min_support_global_fallback():
    rows = [_base_row(f"e{i}") for i in range(4)]
    # Not enough support for min_support=5; must fallback to global.
    df = pd.DataFrame(rows)
    v = _variant(min_support=5)
    model = fit_model(df, v)
    pred = predict_row(model, pd.Series(_base_row("e_test")))
    assert pred["backoff_level"] == "global"


def test_deterministic_tie_breaking():
    # Two actions with identical labels/performance -> deterministic first action order.
    row = _base_row()
    row["agreement_only_decision"] = row["pooled4_decision"]
    row["agreement_only_ok"] = row["pooled4_ok"]
    train = pd.DataFrame([row for _ in range(8)])
    v = Variant(
        name="tie",
        family="RGEB-test",
        actions=["agreement_only", "pooled4"],
        alpha0=1.0,
        beta0=1.0,
        scoring="mean",
        lcb_q=0.1,
        min_support=3,
        bucket_mode="coarse",
        include_provider_dataset=False,
        provider_free_calibration=True,
    )
    model = fit_model(train, v)
    pred = predict_row(model, pd.Series(row))
    assert pred["selected_action"] == "agreement_only"


def test_no_gold_in_runtime_feature_keys():
    row = pd.Series(_base_row())
    stats = source_stats_from_df(pd.DataFrame([_base_row()]))
    f = runtime_features(row, stats)
    assert "gold" not in f
    assert all("gold" not in str(k).lower() for k in f.keys())


def test_valid_action_answer_outputs():
    train = pd.DataFrame([_base_row(f"e{i}") for i in range(12)])
    v = _variant(min_support=3)
    model = fit_model(train, v)
    pred = predict_row(model, pd.Series(_base_row("etest")))
    assert pred["selected_action"] in set(v.actions)
    assert isinstance(pred["selected_answer"], str)
    assert pred["selected_answer"] != ""


def test_auxiliary_not_required_for_official_headline_default():
    # Official headline behavior should be compatible with official-only rows.
    df = pd.DataFrame([_base_row(f"e{i}") for i in range(10)])
    v = _variant(min_support=3)
    model = fit_model(df, v)
    pred = predict_row(model, pd.Series(_base_row("e_holdout")))
    assert pred["variant_ok"] in {0, 1}


def test_best_calibrated_source_action_answer():
    rows = []
    for i in range(10):
        r = _base_row(f"e{i}")
        # Make L1 consistently best.
        r["L1_ok"] = 1
        r["S1_ok"] = 0
        r["TALE_ok"] = 0
        r["frontier_ok"] = 0
        r["L1_ans"] = "5"
        rows.append(r)
    df = pd.DataFrame(rows)
    stats = source_stats_from_df(df)
    ans = action_answer(pd.Series(_base_row("etest")), "best_calibrated_source", stats)
    assert ans == "5"


def test_runtime_feature_schema_contains_required_keys():
    row = pd.Series(_base_row())
    stats = source_stats_from_df(pd.DataFrame([_base_row()]))
    f = runtime_features(row, stats)
    required = {
        "agreement_pattern",
        "unique_answer_count",
        "majority_size",
        "external_majority_excludes_frontier",
        "S1_isolated",
        "calib_regime_type",
        "best_calibrated_source",
        "best_minus_second_spread_bucket",
        "source_accuracy_entropy_bucket",
    }
    assert required.issubset(set(f.keys()))

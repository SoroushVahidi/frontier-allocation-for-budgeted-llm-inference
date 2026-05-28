import inspect

import pandas as pd

from scripts.evaluate_fix03_s1_near_peer_gate import (
    SOURCES,
    answer_to_correctness,
    build_calibration,
    choose_pooled4_answer,
    infer_fix03,
)


def _train_df(frontier=6, l1=6, s1=6, tale=6, n=10):
    rows = []
    for i in range(n):
        rows.append(
            {
                "frontier_ok": 1 if i < frontier else 0,
                "L1_ok": 1 if i < l1 else 0,
                "S1_ok": 1 if i < s1 else 0,
                "TALE_ok": 1 if i < tale else 0,
            }
        )
    return pd.DataFrame(rows)


def _row(**kw):
    base = {
        "frontier_ans": "10",
        "L1_ans": "10",
        "S1_ans": "12",
        "TALE_ans": "11",
        "frontier_ok": 1,
        "L1_ok": 1,
        "S1_ok": 0,
        "TALE_ok": 0,
        "majority_answer": "10",
        "majority_size": 2,
        "has_majority": 1,
        "all_four_agree": 0,
        "three_one_split": 0,
        "two_two_split": 0,
        "all_different": 0,
        "no_majority_flag": 0,
        "S1_in_majority": 0,
        "S1_isolated": 1,
        "example_id": "ex1",
        "scenario_id": "cohere_gsm8k",
        "provider": "cohere",
        "dataset": "gsm8k",
        "official_or_auxiliary": "official",
        "question": "q",
        "gold": "10",
        "beta_shrinkage_decision_answer": "12",
        "c1d_decision_answer": "12",
        "pooled4_decision_answer": "10",
        "beta_source": "S1",
        "c1d_source": "S1",
    }
    base.update(kw)
    return pd.Series(base)


def test_near_peer_gate_blocks_unsupported_s1():
    calib = build_calibration(_train_df(frontier=6, l1=6, s1=6, tale=6, n=10))
    r = _row()
    pred = infer_fix03(r, calib, family="fix03a", params={"spread_thr": 0.10, "base": "beta", "dominance_conf_thr": 0.03})
    assert pred["selected_answer"] == "10"
    assert pred["blocked_s1"] == 1


def test_near_peer_gate_does_not_block_s1_with_majority_support():
    calib = build_calibration(_train_df(frontier=6, l1=6, s1=6, tale=6, n=10))
    r = _row(
        frontier_ans="12",
        L1_ans="12",
        S1_ans="12",
        majority_answer="12",
        majority_size=3,
        has_majority=1,
        S1_in_majority=1,
        S1_isolated=0,
        pooled4_decision_answer="12",
        gold="12",
        frontier_ok=1,
        L1_ok=1,
        S1_ok=1,
        TALE_ok=0,
    )
    pred = infer_fix03(r, calib, family="fix03b", params={"spread_thr": 0.10, "base": "beta"})
    assert pred["blocked_s1"] == 0
    assert pred["selected_answer"] == "12"


def test_dominant_mistral_like_calibration_keeps_s1():
    calib = build_calibration(_train_df(frontier=4, l1=3, s1=10, tale=2, n=10))
    r = _row(
        scenario_id="mistral_gsm8k",
        provider="mistral",
        beta_shrinkage_decision_answer="12",
        S1_ans="12",
        pooled4_decision_answer="10",
        S1_ok=1,
    )
    pred = infer_fix03(r, calib, family="fix03a", params={"spread_thr": 0.03, "base": "beta", "dominance_conf_thr": 0.01})
    assert pred["blocked_s1"] == 0
    assert pred["selected_answer"] == "12"


def test_provider_free_variant_requires_no_provider_identity():
    calib = build_calibration(_train_df(frontier=6, l1=6, s1=6, tale=6, n=10))
    r1 = _row(provider="cohere")
    r2 = _row(provider="mistral")
    p1 = infer_fix03(r1, calib, family="fix03d", params={"spread_thr": 0.10, "base": "beta"})
    p2 = infer_fix03(r2, calib, family="fix03d", params={"spread_thr": 0.10, "base": "beta"})
    assert p1["selected_action"] == p2["selected_action"]
    assert p1["selected_answer"] == p2["selected_answer"]


def test_no_gold_labels_used_by_inference_functions():
    src = inspect.getsource(infer_fix03)
    assert 'row.get("gold"' not in src


def test_deterministic_tie_breaking():
    calib = build_calibration(_train_df(frontier=6, l1=6, s1=6, tale=6, n=10))
    r = _row(has_majority=0, majority_answer="", pooled4_decision_answer="10")
    p1 = infer_fix03(r, calib, family="fix03e", params={"spread_thr": 0.08, "base": "beta"})
    p2 = infer_fix03(r, calib, family="fix03e", params={"spread_thr": 0.08, "base": "beta"})
    assert p1["selected_answer"] == p2["selected_answer"]
    assert p1["selected_action"] == p2["selected_action"]


def test_all_variant_families_return_valid_outputs():
    calib = build_calibration(_train_df(frontier=6, l1=6, s1=6, tale=6, n=10))
    r = _row()
    variants = [
        ("fix03a", {"spread_thr": 0.10, "base": "beta", "dominance_conf_thr": 0.03}),
        ("fix03b", {"spread_thr": 0.10, "base": "beta"}),
        ("fix03c", {"spread_thr": 0.10, "base": "beta", "allow_margin": 0.02}),
        ("fix03d", {"spread_thr": 0.10, "base": "beta"}),
        ("fix03e", {"spread_thr": 0.10, "base": "beta"}),
        ("fix03f", {"spread_thr": 0.10, "base": "c1d", "dominance_conf_thr": 0.03}),
    ]
    for fam, params in variants:
        p = infer_fix03(r, calib, family=fam, params=params)
        assert isinstance(p["selected_answer"], str)
        assert isinstance(p["selected_source"], str)
        assert isinstance(p["selected_action"], str)


def test_s1_isolation_feature_works_correctly():
    calib = build_calibration(_train_df(frontier=6, l1=6, s1=6, tale=6, n=10))
    r = _row(S1_isolated=1, S1_in_majority=0)
    p = infer_fix03(r, calib, family="fix03b", params={"spread_thr": 0.10, "base": "beta"})
    assert p["s1_isolated"] == 1


def test_answer_to_correctness_matches_flags():
    r = _row()
    assert answer_to_correctness(r, "10") == 1
    assert answer_to_correctness(r, "12") == 0


def test_choose_pooled4_answer_prefers_majority():
    r = _row(majority_answer="10", has_majority=1, majority_size=2)
    ans, action, src = choose_pooled4_answer(r)
    assert ans == "10"
    assert action == "pooled4_majority"
    assert src == "majority"


def test_sources_contract_stable():
    assert SOURCES == ["frontier", "L1", "S1", "TALE"]

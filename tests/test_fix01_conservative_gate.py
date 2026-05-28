import pandas as pd

from scripts.evaluate_fix01_conservative_gate import (
    build_calibration,
    conservative_override_condition,
    dominant_by_probability_with_gap,
    infer_strengthened_c1d,
)


def _train_df(frontier=6, l1=5, s1=9, tale=4, n=10):
    rows = []
    for i in range(n):
        rows.append(
            {
                "scenario_id": "mistral_gsm8k",
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
        "L1_ans": "11",
        "S1_ans": "12",
        "TALE_ans": "11",
        "frontier_ok": 0,
        "L1_ok": 0,
        "S1_ok": 1,
        "TALE_ok": 0,
        "majority_answer": "11",
        "majority_size": 2,
        "has_majority": 1,
        "all_four_agree": 0,
        "three_one_split": 0,
        "two_two_split": 1,
        "all_different": 0,
        "no_majority_flag": 0,
        "example_id": "ex1",
        "scenario_id": "mistral_gsm8k",
        "provider": "mistral",
        "dataset": "gsm8k",
        "official_or_auxiliary": "official",
        "question": "q",
        "gold": "12",
    }
    base.update(kw)
    return pd.Series(base)


def test_fix01f_dominance_probability_with_gap_selects_best_source():
    calib = build_calibration(_train_df(frontier=4, l1=3, s1=10, tale=2, n=10))
    dominant, probs = dominant_by_probability_with_gap(calib, tau=0.75, delta=0.0, seed=7)
    assert dominant == "S1"
    assert "S1" in probs
    assert probs["S1"] >= 0.75


def test_fix01f_conservative_override_blocks_external_only_majority():
    calib = build_calibration(_train_df(frontier=4, l1=3, s1=10, tale=2, n=10))
    row = _row(
        majority_answer="11",
        majority_size=3,
        has_majority=1,
        frontier_ans="12",
        L1_ans="11",
        S1_ans="12",
        TALE_ans="11",
    )
    allowed = conservative_override_condition(
        row=row,
        calib=calib,
        dominant_src="S1",
        d_prob=0.95,
        tau=0.90,
        delta=0.02,
        override_margin=0.05,
        external_corr_penalty=0.03,
    )
    assert not allowed


def test_fix01f_uses_pooled4_when_near_peer_blocked():
    calib = build_calibration(_train_df(frontier=6, l1=6, s1=6, tale=6, n=10))
    row = _row(has_majority=1, majority_answer="11", majority_size=2)
    pred = infer_strengthened_c1d(
        row=row,
        calib=calib,
        variant="fix01f",
        params={"_near_peer_blocked": True, "_dominant_src": None, "_dom_probs": {}},
        rng_seed=1,
    )
    assert pred["selected_action"] == "pooled4_no_dominance"
    assert pred["selected_source"] in {"pooled4_majority", "frontier"}

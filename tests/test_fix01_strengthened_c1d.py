import inspect

import pandas as pd

from scripts.evaluate_fix01_strengthened_c1d import (
    SOURCES,
    answer_to_correctness,
    beta_posterior_bounds,
    build_calibration,
    choose_pooled4,
    dominant_by_lcb_gap,
    dominant_by_probability,
    infer_strengthened_c1d,
    near_peer_safety_gate,
)


def _train_df(frontier=6, l1=5, s1=9, tale=4, n=10):
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


def test_dominance_lcb_gate_positive_when_gap_large():
    calib = build_calibration(_train_df(frontier=4, l1=3, s1=10, tale=2, n=10))
    dom = dominant_by_lcb_gap(calib, delta_lcb=0.0)
    assert dom == "S1"


def test_probability_of_dominance_gate_returns_source_for_high_tau_when_clear_best():
    calib = build_calibration(_train_df(frontier=4, l1=3, s1=10, tale=2, n=10))
    dom = dominant_by_probability(calib, tau=0.75, delta=0.0, seed=123)
    assert dom == "S1"


def test_near_peer_safety_gate_blocks_false_dominance():
    calib = build_calibration(_train_df(frontier=6, l1=6, s1=6, tale=6, n=10))
    assert not near_peer_safety_gate(calib, spread_min=0.05)


def test_dominant_in_majority_returns_majority():
    calib = build_calibration(_train_df(frontier=4, l1=3, s1=10, tale=2, n=10))
    r = _row(
        majority_answer="12",
        majority_size=3,
        has_majority=1,
        frontier_ans="12",
        L1_ans="12",
        S1_ans="12",
    )
    pred = infer_strengthened_c1d(
        r,
        calib,
        variant="fix01a",
        params={"delta_lcb": 0.0, "override_margin": 0.05},
        rng_seed=1,
    )
    assert pred["selected_answer"] == "12"
    assert pred["selected_action"] == "majority_includes_dominant"


def test_majority_excludes_dominant_returns_dominant_unless_override_passes():
    calib = build_calibration(_train_df(frontier=4, l1=3, s1=10, tale=2, n=10))
    r = _row()
    pred = infer_strengthened_c1d(
        r,
        calib,
        variant="fix01a",
        params={"delta_lcb": 0.0, "override_margin": 0.99},
        rng_seed=1,
    )
    assert pred["selected_source"] == "S1"
    assert pred["selected_answer"] == "12"


def test_inference_function_does_not_use_gold_labels():
    src = inspect.getsource(infer_strengthened_c1d)
    assert "row.get(\"gold\"" not in src


def test_deterministic_tie_breaking_and_repeatability():
    calib = build_calibration(_train_df(frontier=5, l1=5, s1=5, tale=5, n=10))
    r = _row(has_majority=0, majority_answer="", frontier_ans="10")
    a1 = infer_strengthened_c1d(
        r,
        calib,
        variant="fix01b",
        params={"tau": 0.85, "delta": 0.02, "override_margin": 0.05},
        rng_seed=777,
    )
    a2 = infer_strengthened_c1d(
        r,
        calib,
        variant="fix01b",
        params={"tau": 0.85, "delta": 0.02, "override_margin": 0.05},
        rng_seed=777,
    )
    assert a1["selected_answer"] == a2["selected_answer"]
    assert a1["selected_action"] == a2["selected_action"]


def test_all_variants_return_valid_action_source_answer():
    calib = build_calibration(_train_df(frontier=4, l1=3, s1=10, tale=2, n=10))
    r = _row()
    variants = [
        ("fix01a", {"delta_lcb": 0.02, "override_margin": 0.05}),
        ("fix01b", {"tau": 0.85, "delta": 0.02, "override_margin": 0.05}),
        ("fix01c", {"spread_min": 0.05, "delta_lcb": 0.02, "override_margin": 0.05}),
        ("fix01d", {"spread_min": 0.05, "delta_lcb": 0.02, "override_margin": 0.05}),
        ("fix01e", {"spread_threshold": 0.08}),
    ]
    for v, p in variants:
        pred = infer_strengthened_c1d(r, calib, variant=v, params=p, rng_seed=123)
        assert isinstance(pred["selected_answer"], str)
        assert pred["selected_source"]
        assert pred["selected_action"]


def test_answer_to_correctness_matches_source_flags():
    r = _row()
    assert answer_to_correctness(r, "12") == 1
    assert answer_to_correctness(r, "11") == 0


def test_choose_pooled4_returns_frontier_when_no_majority():
    calib = build_calibration(_train_df())
    r = _row(has_majority=0, majority_answer="", frontier_ans="10")
    ans, action, src = choose_pooled4(r, calib)
    assert ans == "10"
    assert action == "frontier_fallback"

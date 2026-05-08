from __future__ import annotations

from experiments.adaptive_retry_router import (
    AdaptiveRouterV3Config,
    compute_adaptive_retry_features,
    choose_adaptive_retry_scaffold_v3,
)


def _route(text: str, enable_percent: bool = False) -> tuple[str, str, bool]:
    cfg = AdaptiveRouterV3Config(enable_percent_base_denominator=enable_percent)
    feats = compute_adaptive_retry_features(text)
    return choose_adaptive_retry_scaffold_v3(text, feats, cfg)


def test_feature_extractor_detects_key_cues() -> None:
    f_diff = compute_adaptive_retry_features("How many more apples does A have than B?")
    assert f_diff["asks_difference"] is True
    f_rate = compute_adaptive_retry_features("A car drives 60 miles per hour for 2 hours.")
    assert f_rate["asks_rate_or_unit"] is True
    f_avg = compute_adaptive_retry_features("What score is needed on the sixth test to get an average of 93?")
    assert f_avg["average_cue"] is True and f_avg["target_score_cue"] is True
    f_ratio = compute_adaptive_retry_features("Each adult gets twice the share of each kid.")
    assert f_ratio["ratio_cue"] is True
    f_comb = compute_adaptive_retry_features("A class is split into 3 groups such that two are equal.")
    assert f_comb["combinatorics_cue"] is True
    f_state = compute_adaptive_retry_features("After day 1 and then day 2, how much remains?")
    assert f_state["state_change_cue"] is True


def test_router_maps_representative_cases() -> None:
    assert _route("What score does she need on the sixth test to get an average of 93?")[1] == "average_target_score"
    assert _route("A class of 200 is split into 3 groups such that two are equal.")[1] == "combinatorics_counting"
    assert _route("Each adult gets twice the share of each kid. What percent does each adult get?")[1] == "ratio_partition"
    assert _route("Day 1 fills part of tank, day 2 adds more, how much remains?")[1] == "state_composition"


def test_percent_base_cases_held_back_by_default() -> None:
    decision, scaffold, held = _route(
        "A balance drops by 9% each hour for 5 hours, then 7% each hour for 3 hours. What was initial charge?"
    )
    assert held is True
    assert scaffold != "percent_base_denominator"
    assert decision in {"abstain", "targeted_retry", "base"}


def test_low_risk_simple_question_stays_base() -> None:
    decision, scaffold, _ = _route("Tom has 3 apples and buys 2 more. How many apples now?")
    assert decision == "base"
    assert scaffold == "base_method_no_retry"

from __future__ import annotations

from types import SimpleNamespace

from scripts.run_conformal_thinking_mode_a import (
    calibrate_upper_threshold,
    difficulty_score,
    finite_sample_lower_risk,
    finite_sample_upper_risk,
    split_calibration_eval,
)


def _cfg() -> SimpleNamespace:
    return SimpleNamespace(
        difficulty_length_weight=0.55,
        difficulty_digit_weight=0.25,
        difficulty_symbol_weight=0.2,
    )


def test_difficulty_score_orders_easy_hard() -> None:
    cfg = _cfg()
    easy = "What is 2 + 2?"
    hard = "A train travels 120 miles at 40 mph, then 150 miles at 50 mph. What is average speed?"
    assert difficulty_score(hard, cfg) >= difficulty_score(easy, cfg)


def test_plus_one_risk_corrections() -> None:
    assert finite_sample_upper_risk(errors=0, n=0) == 0.0
    assert finite_sample_upper_risk(errors=1, n=9) == 0.2
    assert finite_sample_lower_risk(false_negatives=2, n=8) == (3 / 9)


def test_calibration_split_nonempty() -> None:
    ids = [f"id_{i}" for i in range(10)]
    cal, ev = split_calibration_eval(ids, frac=0.5, seed=11)
    assert cal
    assert ev
    assert cal.isdisjoint(ev)
    assert cal | ev == set(ids)


def test_upper_calibration_prefers_low_compute_when_feasible() -> None:
    class Traj:
        def __init__(self, conf: list[float], correct_by_step: list[bool]) -> None:
            self.conf = conf
            self.progress = conf
            self.correct_by_step = correct_by_step

    # all examples become correct by step 2; high threshold should remain feasible and use fewer steps
    calib = [
        Traj([0.3, 0.9, 0.95], [False, True, True]),
        Traj([0.4, 0.85, 0.9], [False, True, True]),
        Traj([0.2, 0.8, 0.92], [False, True, True]),
    ]
    out = calibrate_upper_threshold(calib, risk_target=0.4, grid_points=11, corrected=True)
    assert out["chosen"]["upper_risk"] <= 0.4
    assert 0.0 <= out["chosen"]["threshold"] <= 1.0

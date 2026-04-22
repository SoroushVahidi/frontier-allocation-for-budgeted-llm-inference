from __future__ import annotations

from types import SimpleNamespace

from scripts.run_training_free_difficulty_proxies_mode_a import (
    _choose_instance,
    _mgl_from_failed_lengths,
    cheap_input_proxy,
)


def _cfg() -> SimpleNamespace:
    return SimpleNamespace(
        mgl_floor=1.0,
        cheap_proxy_length_weight=0.8,
        cheap_proxy_digit_weight=0.2,
    )


def test_cheap_proxy_orders_easy_hard() -> None:
    cfg = _cfg()
    easy = "2+2?"
    hard = "A store has 12 shelves and each shelf has 37 items, then 19 are removed from each shelf."
    assert cheap_input_proxy(hard, cfg) >= cheap_input_proxy(easy, cfg)


def test_mgl_update_uses_failed_history() -> None:
    assert _mgl_from_failed_lengths([], fallback=2.0, floor=1.0) == 2.0
    assert _mgl_from_failed_lengths([10, 20, 30], fallback=2.0, floor=1.0) == 20.0


def test_policy_choice_extremes() -> None:
    active = ["a", "b", "c"]
    m = {"a": 1.0, "b": 2.0, "c": 5.0}

    easy, _ = _choose_instance("easy_to_hard_mgl", active, m, rr_cursor=0, rng=__import__("random").Random(0), lambda_t=1.0)
    hard, _ = _choose_instance("hard_to_easy_mgl", active, m, rr_cursor=0, rng=__import__("random").Random(0), lambda_t=1.0)

    assert easy == "a"
    assert hard == "c"

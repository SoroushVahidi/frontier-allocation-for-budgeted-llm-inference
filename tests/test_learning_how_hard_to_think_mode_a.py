from __future__ import annotations

from types import SimpleNamespace

from scripts.run_learning_how_hard_to_think_mode_a import allocate_candidate_slots, difficulty_score


def _cfg() -> SimpleNamespace:
    return SimpleNamespace(
        candidate_action_cap=2,
        min_k=1,
        max_k=4,
        weighted_temp=0.7,
        weighted_alpha=0.75,
        difficulty_length_weight=0.55,
        difficulty_digit_weight=0.2,
        difficulty_symbol_weight=0.15,
        difficulty_multi_step_weight=0.1,
    )


def test_difficulty_score_monotonic_signal() -> None:
    cfg = _cfg()
    easy = "Tom has 2 apples."
    hard = "Tom has 2 apples, buys 13 more, gives 4 away, then doubles the remainder and subtracts 7. What is left?"
    assert difficulty_score(hard, cfg) > difficulty_score(easy, cfg)


def test_allocate_candidate_slots_budget_invariants() -> None:
    cfg = _cfg()
    hardness = [0.2, 0.4, 0.8, 0.9]
    policies = [
        "learning_how_hard_to_think_mode_a",
        "uniform_matched_compute",
        "fixed_k_matched_compute",
        "easy_to_hard_ordering",
        "hard_to_easy_ordering",
    ]

    for policy in policies:
        slots, meta = allocate_candidate_slots(policy, hardness, budget_actions_per_example=6, cfg=cfg)
        assert len(slots) == len(hardness)
        assert all(cfg.min_k <= s <= cfg.max_k for s in slots)
        assert meta["planned_total_actions"] <= meta["target_total_actions"]
        assert meta["effective_unspent_actions"] >= 0


def test_hard_to_easy_allocates_more_to_harder_than_easy_to_hard() -> None:
    cfg = _cfg()
    hardness = [0.1, 0.2, 0.9, 0.95]
    hard_slots, _ = allocate_candidate_slots("hard_to_easy_ordering", hardness, budget_actions_per_example=6, cfg=cfg)
    easy_slots, _ = allocate_candidate_slots("easy_to_hard_ordering", hardness, budget_actions_per_example=6, cfg=cfg)

    hard_tail = hard_slots[2] + hard_slots[3]
    easy_tail = easy_slots[2] + easy_slots[3]
    assert hard_tail >= easy_tail

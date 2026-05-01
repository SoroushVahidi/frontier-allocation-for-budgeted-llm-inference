# COHERE 100-case ours vs external baselines plan

- Methods compared: strict_f3, direct_reserve_semantic_frontier_v2, direct_reserve_semantic_frontier_v2 + outcome_verifier_answer_group_selector_v1, l1_length_control_rl, tale_token_budget_aware_reasoning, s1_simple_test_time_scaling.
- Dataset/split/seed: openai/gsm8k test, seed 20260501, 100 random fixed cases.
- Cohere model: command-a-03-2025.
- Claim boundary: external baselines are MODE-A adapter comparators on matched substrate, not official full-stack reproductions.

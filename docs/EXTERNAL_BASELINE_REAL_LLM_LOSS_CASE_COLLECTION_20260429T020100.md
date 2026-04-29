# External Baseline Real-LLM Loss Case Collection (2026-04-29)

1. Mined artifacts: `outputs/cohere_real_model_cost_normalized_validation_*`, `outputs/real_model_decision_package_*`, plus `outputs/external_baseline_loss_case_live_collection_20260429T015644/`.
2. Pre-live coverage: external_l1_max paired 120; tale/s1 paired 0; self-consistency/ToT paired 0; traced external-win 11.
3. Live API calls were made because thresholds were unmet for TALE/S1, self-consistency/ToT, and traced external-win.
4. Provider/model: Cohere `command-r-plus-08-2024`.
5. Paired real-LLM cases collected (latest collection): 120 (existing dominated; live continuation in progress for missing families).
6. External-win cases found: 31.
7. Most frequent external winners: direct length control (`external_l1_max`).
8. Internal methods losing most: `strict_f3` and `direct_reserve_frontier_gate_v1` in mined artifacts.
9. Dominant preliminary failure type: `external_direct_advantage`, then `present_not_selected`.
10. Trace-rich losses: 11 external-win rows had trace availability flags.
11. Next bottleneck: close missing-family coverage (TALE/S1 + self-consistency/ToT) with bounded continuation and compare selection-stage failures vs direct baseline advantage.

Planned bounded-call estimate: 9 methods x 20 examples x 1 budget = 180 method-example-budget calls (before excluding unresolved methods).

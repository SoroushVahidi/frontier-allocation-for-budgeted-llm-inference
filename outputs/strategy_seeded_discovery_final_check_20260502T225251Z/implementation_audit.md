# Implementation audit (v1 pilot + v2_final design)

## strategy_seeded_semantic_diversity_frontier_v1 (pilot)

- Overrides `_run_direct_attempt` only; caps each root strategy seed via `strategy_seed_max_actions=1`, so attempted depth per strategy was shallow even when `per_attempt_cap` from token budget was ~8.
- Parent `DirectReserveFrontierGateController` still plans up to five direct reserve indices, but each call to `super()._run_direct_attempt` was limited to one expand — **prompt styles differ** (from `direct_prompt_styles`) but **depth was not**.
- `direct_reserve_plus_diverse_kwargs` sets `gate_*` thresholds to **2.0 / -1.0**, so `incumbent_uncertain` is effectively always true when any budget remains; frontier engagement is not strongly gated by direct-stage entropy in this configuration.
- Diagnostic inner controller enabled `diagnostic_semantic_maturation` — useful logging, not a substitute for post-hoc label alignment.

## direct_reserve_strategy_seeded_semantic_frontier_v2_final

- Replaces direct prompt construction to inject each `ROOT_STRATEGY_FAMILY_SPECS` suffix into the literal `expand` prompt (strategy-controlled, not tag-only).
- Budget-aware alternate count (+ deterministic SHA256(question) permutation). Optional early stop hook after seed 0 when multi-step intra-seed extracts agree (`DirectReserveFrontierGateController._stop_additional_direct_reserve_after_attempt`).
- Increased per-seed expands when `budget - reserve_for_frontier` allows (`strategy_seed_min_actions`, `_per_seed_max_actions`).
- Inner `GlobalDiversityAggregationController` inherits strict_f3 with **raised** `duplicate_penalty` / `repeat_expand_family_penalty_weight` as deterministic allocation pressure; telemetry fields forwarded into semantic gate counters in `strategy_seeded_v2_final_audit`.

Gold is used only inside `generator.expand`/evaluation surfaces consistent with DR-v2 baselines — **never** appended to displayed strategy prompts in v2_final.

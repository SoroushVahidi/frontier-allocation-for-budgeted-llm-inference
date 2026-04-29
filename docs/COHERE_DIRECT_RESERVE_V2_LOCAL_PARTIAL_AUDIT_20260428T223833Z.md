# Cohere DR-v2 local partial audit

Status: partial local Codex validation, non-Wulver, diagnostic only.

## Exact commands run
- Smoke run: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260428T222720Z --providers cohere --cohere-model command-r-plus-08-2024 --datasets openai/gsm8k --budgets 4 --seeds 11 --methods direct_reserve_semantic_frontier_v2,external_l1_max,strict_f3,strict_gate1_cap_k6,strict_f3_anti_collapse_weak_v1,tale,s1 --target-scored-per-slice 2 --max-examples 2 --resume`
- Partial bounded run start: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260428T222827Z --providers cohere --cohere-model command-r-plus-08-2024 --datasets openai/gsm8k --budgets 4,6,8 --seeds 11,23 --methods direct_reserve_semantic_frontier_v2,external_l1_max,strict_f3,strict_gate1_cap_k6,strict_f3_anti_collapse_weak_v1,tale,s1 --target-scored-per-slice 20 --max-examples 20 --resume`
- Resume command (exact): `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp 20260428T222827Z --providers cohere --cohere-model command-r-plus-08-2024 --datasets openai/gsm8k --budgets 4,6,8 --seeds 11,23 --methods direct_reserve_semantic_frontier_v2,external_l1_max,strict_f3,strict_gate1_cap_k6,strict_f3_anti_collapse_weak_v1,tale,s1 --target-scored-per-slice 20 --max-examples 20 --resume`

## Completion scope
- Completed datasets: ['openai/gsm8k']
- Completed budgets: [4]
- Completed seeds: [11]
- Matched DR-v2 vs external_l1_max paired cases: 20

## Methods
- Observed methods: direct_reserve_semantic_frontier_v2, external_l1_max, strict_f3, strict_gate1_cap_k6
- Missing methods (requested but not yet observed in this partial run): s1, strict_f3_anti_collapse_weak_v1, tale

## Duplicate/fallback case check
- No explicit duplicate/cycle fallback mechanism is tracked in this runner artifacts; pairing uses unique `(dataset,seed,budget,example_id)` keys.

## Raw accuracy by method (partial)

- strict_gate1_cap_k6: 0.7500
- external_l1_max: 0.7000
- strict_f3: 0.6000
- direct_reserve_semantic_frontier_v2: 0.5500

## Paired DR-v2 vs external_l1_max (partial)
- Paired exact-match delta: -0.1500
- Unique-example accuracy delta: -0.1500

## Cost-normalized comparison (partial)
- acc_per_cost delta (DR-v2 - external_l1_max): -174.96653341364402

## Budget/seed breakdown for completed slices (partial)
- dataset=openai/gsm8k budget=4 seed=11 method=direct_reserve_semantic_frontier_v2 acc=0.5500
- dataset=openai/gsm8k budget=4 seed=11 method=external_l1_max acc=0.7000
- dataset=openai/gsm8k budget=4 seed=11 method=strict_f3 acc=0.6000
- dataset=openai/gsm8k budget=4 seed=11 method=strict_gate1_cap_k6 acc=0.7500

## Hypothesis impact
- Current local partial signal **weakens** the hypothesis that DR-v2 beats Cohere external_l1_max (negative paired delta in observed matched cases).
- This remains diagnostic-only and incomplete.

## Manuscript evidence warning
- Do NOT use this partial audit as canonical or manuscript headline evidence. Complete paired run is required.

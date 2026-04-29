# Local Cohere validation progress (Codex-only, no Wulver)

Status: partial bounded local run completed and artifacts postprocessed.

## Runs executed
1. Smoke run (`TS=20260428T222720Z`):
   - dataset: `openai/gsm8k`
   - budget: `4`
   - seed: `11`
   - methods: `direct_reserve_semantic_frontier_v2, external_l1_max, strict_f3, strict_gate1_cap_k6, strict_f3_anti_collapse_weak_v1, tale, s1`
   - cap: `2` examples
   - output: `outputs/cohere_direct_reserve_v2_vs_external_l1_local_validation_20260428T222720Z/`

2. Bounded run start (`TS=20260428T222827Z`):
   - target config: GSM8K, budgets `4,6,8`, seeds `11,23`, cap `20`
   - run was manually stopped after collecting partial budget-4/seed-11 slices to control runtime/cost.
   - output: `outputs/cohere_direct_reserve_v2_vs_external_l1_local_validation_20260428T222827Z/`

## Partial quantitative snapshot (TS=20260428T222827Z)
- Scored rows: 64
- Methods with scored rows so far:
  - `strict_gate1_cap_k6`: 0.75
  - `external_l1_max`: 0.70
  - `strict_f3`: 0.60
  - `direct_reserve_semantic_frontier_v2`: 0.55
- Paired DR-v2 vs external_l1_max delta (exact-match mean difference): `-0.15` over 20 matched cases.

## Interpretation discipline
- This is **not** full evidence for manuscript integration.
- This is a local partial/diagnostic signal only.
- Full conclusion requires complete paired run across all requested budgets/seeds (and optional MATH-500 extension) with the prepared handoff package.

## Resume command for next local pass
```bash
python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp 20260428T222827Z \
  --providers cohere \
  --cohere-model command-r-plus-08-2024 \
  --datasets openai/gsm8k \
  --budgets 4,6,8 \
  --seeds 11,23 \
  --methods direct_reserve_semantic_frontier_v2,external_l1_max,strict_f3,strict_gate1_cap_k6,strict_f3_anti_collapse_weak_v1,tale,s1 \
  --target-scored-per-slice 20 \
  --max-examples 20 \
  --resume
```

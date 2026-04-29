# Real-Model Experiment Status (Cohere/OpenAI)

**Status: diagnostic (supporting evidence only).**

## Scope
- Real-model runs are not manuscript headline evidence by default.
- They support diagnostics, wiring validation, and continuation planning.

## Durable source of truth for Codex-local Cohere continuation
- `outputs/cohere_compact_ledgers/20260429T_COHERE_FULL_ACCURACY_CODEX_compact_per_example_ledger.csv`
- Older markdown-only progress statements are not authoritative unless ledger-backed.

## Current Cohere full-accuracy state
- Plan dimensions: datasets `openai/gsm8k`, `HuggingFaceH4/MATH-500`; budgets `2,4,6,8`; seeds `11,13,17`; 9 runnable methods.
- `openai/gsm8k`, budget `2`, seed `11`, 9-method matched slice: **incomplete** according to current durable workflow status.

## Historical/provenance-only inputs
- Tiny (10-example) checks.
- Interrupted launch attempts.
- Wulver/Slurm handoff docs and legacy launch notes for non-Codex-local workflows.

## Excluded method reminder
- `direct_reserve_semantic_frontier_v2_thresholded_ordered` remains diagnostic-only and excluded from live runner method set.


## 2026-04-29 minimal Cohere execution update (`20260429T_COHERE_NEURIPS_MINIMAL_RUN1`)
- Targeted minimal run launched for `openai/gsm8k`, budget `2`, seed `11`, nine-method runnable set (excluding thresholded-ordered diagnostic-only method).
- Exactly-100 completed slices: `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`, `external_l1_max`, `tale`, `s1`.
- External comparison checkpoint is now evaluable: `strict_f3=0.54` vs `external_l1_max=0.69` (delta `-0.15`, unfavorable to `strict_f3` in this slice).
- Remaining nonfinal methods in this timestamp: `self_consistency_3` (0/100), `direct_reserve_semantic_frontier_v2_selection_fix_v1` (42/100), and nonfinal over-target `direct_reserve_semantic_frontier_v2` (162/100; excluded from final-only claims).


## 2026-04-29 budget-4 follow-up (`20260429T_COHERE_GSM8K_B4_CLAIM_SAFETY`)
- Completed final slices: `strict_f3` and `external_l1_max` (100/100 each) on `openai/gsm8k`, budget `4`, seed `11`.
- Result: `strict_f3=0.55`, `external_l1_max=0.72`, delta `-0.17` (unfavorable to strict_f3).
- This confirms (not reverses) the budget-2 disadvantage direction in current Cohere diagnostics.
- Remaining budget-4 priority methods are still incomplete (`strict_gate1_cap_k6`, `tale`, `s1`).


## 2026-04-29 DR-v2 100-case validation attempt (`20260429T_COHERE_DR_V2_VS_L1_100CASE`)
- Validation and chunk plan were created for DR-v2-focused methods (`direct_reserve_semantic_frontier_v2`, `direct_reserve_semantic_frontier_v2_selection_fix_v1`, `external_l1_max`, `strict_f3`) at budget 4 / seed 11.
- Update: `external_l1_max` and `direct_reserve_semantic_frontier_v2` are now finalized at 100/100 in this timestamp.
- Current completed subset result is unfavorable to DR-v2: `direct_reserve_semantic_frontier_v2=0.56` vs `external_l1_max=0.72` (delta `-0.16`).
- `direct_reserve_semantic_frontier_v2_selection_fix_v1` and `strict_f3` remain incomplete for this timestamp.

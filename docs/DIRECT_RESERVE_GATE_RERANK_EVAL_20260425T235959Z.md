# DIRECT_RESERVE_GATE_RERANK_EVAL_20260425T235959Z

## Scope and claim discipline
- This package is **diagnostic-only** and does **not** change canonical method status.
- The new method `strict_f3_direct_reserve_gate_rerank_v1` was evaluated via an **offline proxy reconstruction** from existing Cohere GSM8K per-example artifacts (`outputs/real_model_ours_vs_external_validation_20260425T_WULVER_COHERE_LONG/cohere/per_example_rows.csv`).
- Wording here is intentionally conservative and consistent with claim-boundary docs (no universal dominance claims).

## Methods compared
- `external_l1_max`
- `strict_f3`
- `strict_gate1_cap_k6` (not present in this specific source slice; reported as unavailable)
- `strict_f3_direct_reserve_gate_rerank_v1` (diagnostic offline proxy)

## Main metrics (overall, matched cases in this slice)
From `outputs/direct_reserve_gate_rerank_eval_20260425T235959Z/summary.csv`:
- `external_l1_max`: accuracy `0.7153`, absent_from_tree `0.2847`, present_not_selected `0.0000`, n=720.
- `strict_f3`: accuracy `0.5917`, absent_from_tree `0.3194`, present_not_selected `0.0889`, n=720.
- `strict_f3_direct_reserve_gate_rerank_v1` (diagnostic): accuracy `0.8000`, absent_from_tree `0.1722`, present_not_selected `0.0278`, n=720.
- `strict_gate1_cap_k6`: n=0 in this package.

## Required questions

### 1) Did mandatory direct-chain coverage reduce absent-from-tree failures?
- In this diagnostic proxy: **yes** relative to `strict_f3` (`0.3194 -> 0.1722`).
- Interpretation is limited: this is reconstructed from existing strict/external outputs, not a fresh end-to-end real-model run of the new controller.

### 2) Did answer-group reranking reduce present-not-selected failures?
- In this diagnostic proxy: **yes** relative to `strict_f3` (`0.0889 -> 0.0278`).
- Again, this is preliminary evidence only.

### 3) Did the hybrid beat strict_f3?
- In this diagnostic proxy: **yes** on accuracy and both failure rates.

### 4) Did the hybrid beat or narrow the gap to external_l1_max under Cohere?
- In this diagnostic proxy: it exceeds `external_l1_max` aggregate accuracy and has lower absent/present-not-selected rates.
- This should be treated as **hypothesis-strengthening diagnostic evidence**, not final real-model confirmation.

### 5) Is this strong enough for main-paper use, or diagnostic-only?
- **Diagnostic-only for now.**
- Promotion to paper-facing claims should require a matched, direct real-model rerun with the new controller active and fairness checks aligned with existing canonical evaluation contracts.

## Artifacts
- `outputs/direct_reserve_gate_rerank_eval_20260425T235959Z/summary.csv`
- `outputs/direct_reserve_gate_rerank_eval_20260425T235959Z/per_budget_seed_summary.csv`
- `outputs/direct_reserve_gate_rerank_eval_20260425T235959Z/paired_deltas.csv`
- `outputs/direct_reserve_gate_rerank_eval_20260425T235959Z/per_example_rows.csv`

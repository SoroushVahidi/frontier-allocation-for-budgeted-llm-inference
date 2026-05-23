# MATH-500 FTA Transfer Diagnostic (Offline, No API)

## Scope
This analysis is fully offline and uses only existing artifacts.

Primary inputs:
- `outputs/cohere_real_model_cost_normalized_validation_mlj_math500_b6_20260520T220928Z/per_example_records.jsonl`
- `outputs/cohere_real_model_cost_normalized_validation_mlj_math500_b6_recovery_failed31_20260521T124545Z/per_example_records.jsonl`
- `outputs/cohere_real_model_cost_normalized_validation_mlj_math500_b6_20260520T220928Z/math500_repaired_diagnostic_summary.md`
- `docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_mlj_math500_b6_20260520T220928Z.md`
- `docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_mlj_math500_b6_recovery_failed31_20260521T124545Z.md`

Policy implementation used for reconstruction:
- `experiments/support_aware_selector.py` (`apply_combined_fix24_to_row`)

Outputs produced:
- `outputs/math500_fta_transfer_diagnostic_20260523/manifest.json`
- `outputs/math500_fta_transfer_diagnostic_20260523/complete_case_records.csv`
- `outputs/math500_fta_transfer_diagnostic_20260523/gate_decomposition.csv`
- `outputs/math500_fta_transfer_diagnostic_20260523/variant_summary.csv`
- `outputs/math500_fta_transfer_diagnostic_20260523/override_reason_distribution.csv`
- `outputs/math500_fta_transfer_diagnostic_20260523/ldg_fallback_distribution.csv`
- `outputs/math500_fta_transfer_diagnostic_20260523/failure_mode_summary.json`
- `outputs/math500_fta_transfer_diagnostic_20260523/gsm8k_aggregate720_gate_comparison.csv`
- `outputs/math500_fta_transfer_diagnostic_20260523/gsm8k_aggregate720_override_reason_distribution.csv`

All counterfactual variants below are **diagnostic only** and **not claim-safe**.

---

## 1) Exact complete-case set used

- Complete-case set size: **488** examples.
- Complete-case definition: all 4 methods present and scored for the same `(provider=cohere, dataset=HuggingFaceH4/MATH-500, seed=11, budget=6, example_id)`.
- Methods required per example:
  - `direct_reserve_semantic_frontier_v2`
  - `external_l1_max`
  - `s1`
  - `tale`
- Per-example diagnostic table: `outputs/math500_fta_transfer_diagnostic_20260523/complete_case_records.csv`.

Gold/eval fields:
- `per_example_records.jsonl` contains `gold_answer`, `gold_answer_canonical`, and `exact_match`.
- These were used **only for offline evaluation** (accuracy/recovery/regression), not in runtime decision rules.

---

## 2) Recomputed/verified accuracies on complete cases (N=488)

From recomputation on complete cases:
- Frontier (`direct_reserve_semantic_frontier_v2`): **129 / 488 = 26.43%**
- `external_l1_max`: **149 / 488 = 30.53%**
- `s1`: **123 / 488 = 25.20%**
- `tale`: **118 / 488 = 24.18%**
- FTA / FIX-2+FIX-4 (policy-faithful replay): **135 / 488 = 27.66%**
- External-3 majority (TALE>S1>L1 tie-break): **135 / 488 = 27.66%**
- Pooled-4 majority (frontier tie-break): **145 / 488 = 29.71%**

Notes:
- Baseline method accuracies match the repaired summary for frontier/L1/S1/TALE.
- This replay yields FTA=135 (vs 136 in prior note), indicating a small implementation/merge discrepancy in earlier ad-hoc summary generation.

---

## 3) Gate-action decomposition on MATH-500 (policy-faithful)

From `gate_decomposition.csv`:
- Total: **488**
- FIX-2 applied: **207**
- FIX-4 applied after FIX-2 did not apply: **0**
- No gate: **281**

Gate effects vs frontier:
- FIX-2 applied subset:
  - recoveries: **27**
  - regressions: **21**
  - ties: **159**
  - net: **+6**
- FIX-4 subset:
  - recoveries/regressions/ties: **0/0/0**
- No-gate subset:
  - unchanged by definition

Additional trigger context:
- `fix2_is_low_depth` true on **261** cases (53.5%), but FIX-2 does not always switch answer; applied-switch count is 207.

---

## 4) LDG / FIX-2 analysis

Occurrence and selection:
- `single_weak_frontier_branch` in complete cases: **229 / 488 = 46.93%**.
- Low-depth trigger (`fix2_is_low_depth`) total: **261 / 488 = 53.48%**.
- FIX-2 applied-switch count: **207**.

Fallback choice within applied FIX-2 (`ldg_fallback_distribution.csv`):
- TALE: **112**
- L1: **70**
- S1: **25**

LDG net effect (applied subset):
- net **+6** vs frontier (recoveries 27, regressions 21)
- but still weaker than L1 globally.

Does LDG lose because external fallback is worse than L1?
- Yes, partly. TALE-heavy fallback on low-depth rows is costly on this surface where L1 is strongest.

Counterfactual “defer to L1 on low-depth”:
- Variant `ldg_to_l1`: **141/488 = 28.89%**
- Better than current FTA (135/488) by **+6** correct, but still below L1 (149/488).

---

## 5) ECO / FIX-4 analysis

Policy condition (from code): requires
- `override_reason == 'direct_frontier_agree'`
- externals unanimous
- unanimous external answer differs from frontier.

Observed on MATH-500 complete cases:
- FIX-4 applied: **0**
- recoveries/regressions/net: **0/0/0**

Conclusion: ECO is effectively dormant here; no evidence of harm, but no measurable contribution on this artifact.

---

## 6) MATH-500 vs GSM8K aggregate-720 comparison

GSM8K aggregate-720 recomputed from postrun source JSONLs listed in:
- `outputs/final_fix24_all_external_postrun_20260520_20260520T025349Z/aggregate_with_prior_validation.csv`

Computed comparison (`gsm8k_aggregate720_gate_comparison.csv`):
- Total: 720
- FIX-2 applied: 122
- FIX-4 applied: 5
- No gate: 593
- FIX-2 net: **+34** (56 recoveries, 22 regressions)
- FIX-4 net: **+5** (5 recoveries, 0 regressions)

Override distribution comparison:
- MATH-500 top reasons:
  - `single_weak_frontier_branch`: 229
  - `direct_frontier_agree`: 130
  - `frontier_not_run_or_budget_exhausted`: 88
- GSM8K-720 top reasons:
  - `direct_frontier_agree`: 456
  - `single_weak_frontier_branch`: 203
  - `frontier_not_run_or_budget_exhausted`: 6

Baseline ordering:
- MATH-500 complete cases: L1 (30.53) > pooled-4 (29.71) > FTA (27.66) > frontier (26.43)
- GSM8K-720 (from postrun): FIX24 (80.69) > L1 (77.64) > frontier (75.28)

---

## 7) Failure composition on MATH-500

From `failure_mode_summary.json` (N=488):
- All methods wrong / no correct answer in pool: **268** (54.9%)
- Frontier wrong but L1 correct: **58**
- Frontier wrong but some method in pool correct: **91**
- FTA wrong while pool had a correct answer: **83**
- FTA wrong with all methods wrong: **268**

Interpretation:
- Dominant issue is candidate-generation/pool difficulty (many all-wrong cases).
- Secondary issue is selection: among recoverable pool cases, current fallback often does not pick the strongest external on MATH-500.

---

## 8) Offline counterfactual variants (diagnostic only)

From `variant_summary.csv`:
- `always_l1`: 149 (30.53%)
- `frontier_default`: 129 (26.43%)
- `fta_fix2_fix4`: 135 (27.66%)
- `ldg_to_l1`: 141 (28.89%)
- `ldg_to_l1_order`: 141 (28.89%)
- `eco_only`: 129 (26.43%)
- `ldg_only`: 135 (27.66%)
- `external3_majority`: 135 (27.66%)
- `pooled4_majority`: 145 (29.71%)
- `fallback_on_budget_exhausted_to_l1`: 132 (27.05%)

Key deltas:
- FTA vs L1: **-2.87 pp**
- `ldg_to_l1` vs current FTA: **+1.23 pp**
- pooled-4 vs current FTA: **+2.05 pp**

---

## 9) Variant recoveries/regressions vs current FTA

From `variant_summary.csv`:
- `always_l1`: recoveries 46, regressions 32, net +14
- `ldg_to_l1`: recoveries 20, regressions 14, net +6
- `pooled4_majority`: recoveries 22, regressions 12, net +10
- `frontier_default`: recoveries 21, regressions 27, net -6

---

## 10) Conclusion

Primary diagnosis:
1. **L1 dominates on this MATH-500 slice**, while current FIX-2 fallback is TALE-heavy under low-depth triggers.
2. **LDG/FIX-2 is only weakly positive vs frontier** on MATH-500 and not enough to compete with L1.
3. **ECO/FIX-4 is not harmful but effectively inactive** (0 fires) on this artifact.
4. **Pool difficulty is high** (`all methods wrong` > 50%), limiting any selector.
5. Artifact is incomplete upstream but complete-case analysis is still valid for diagnostics.

Transferability assessment:
- The failure-trace principle is **partially transferable** (LDG still gives some recoveries), but the **current fallback choice is miscalibrated for MATH-500**.
- Evidence suggests the current GSM8K-tuned FIX-2+FIX-4 rule is **not directly transferable** to MATH-500 without recalibrating low-depth fallback behavior (at minimum, less TALE-first behavior under LDG on this surface).

Claim boundary:
- These are **offline diagnostics only** and **not claim-safe promotion evidence**.

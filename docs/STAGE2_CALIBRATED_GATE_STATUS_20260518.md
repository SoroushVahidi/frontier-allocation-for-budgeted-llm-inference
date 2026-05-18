# Stage 2 Calibrated Gate Status (2026-05-18)

## A) Stage-2 Status Summary

- Current stage: calibrated baseline-gated allocator prototype (failure-driven allocation), output-only.
- RelationReady verifier phase remains closed for within-method reranking model development; current work is policy validation/integration.
- Raw cross-method verifier scores are not a valid direct routing signal (method-entangled in prior audits).
- Method-calibrated percentile features show useful signal, but current evidence is not yet sufficient for tracked policy promotion.

## B) Evidence Summary

| Step | Evidence | Result | Status |
|---|---|---|---|
| Minimal baseline-gated allocator | `scripts/compare_baseline_gated_hybrid_allocator.py` (commit `4f178ce8`) | Validation failure; gate missed recoveries. | Completed |
| Loss collector + failure inventory | `scripts/collect_baseline_gated_loss_cases.py` (commit `871e7a4b`) + downstream inventories | Sufficient disagreement/opportunity pool; clean enriched table included 245 clean rows. | Completed |
| High-log verifier scoring/calibration | `outputs/overnight_high_log_verifier_calibration_20260518T044646Z/` | 2710 scored candidates; verifier features joined to all feature rows (`1183/1183`), both baseline+frontier available for `1141/1183`; raw PAL/frontier scores flat-low; no Cohere API needed. | Completed |
| Calibrated feature audit | `outputs/calibrated_verifier_feature_audit_20260518T141003Z/` | Frozen features: `frontier_proba_ready_pct_within_method`, `baseline_proba_ready_pct_within_method`; margin/z features as ablation; raw cross-method features excluded. | Completed |
| Calibrated percentile gate (safe) | `scripts/evaluate_calibrated_percentile_gate.py` (commit `ac12d13e`), output `outputs/calibrated_percentile_gate_eval_20260518T141746Z/` | Safe gate `conservative_combo f=0.85 b=0.40 m=0.50`; dev `+1.02pp`, holdout `+0.00pp`, all-artifacts `+0.76pp`; conservative with missed recoveries. | Completed |
| Sensitivity / near-neighbor audit | `outputs/calibrated_percentile_gate_sensitivity_20260518T143150Z/`, `outputs/calibrated_gate_candidate_manual_review_20260518T143150Z/`, `outputs/calibrated_gate_regression_penalized_retest_20260518T145519Z/`, `outputs/calibrated_gate_near_neighbor_audit_20260518T150018Z/` | Best near-neighbor `conservative_combo f=0.80 b=0.45 m=0.50`; holdout `+0.33pp` vs safe, with higher switch volume. | Completed |
| Incremental case review | `outputs/calibrated_gate_incremental_case_review_20260518T151933Z/` | Incremental switches `17`; added recoveries `2` acceptable; added regressions `2` tolerable/explainable (runtime-cap failures); `13/17` marked `insufficient_logs`. | Completed |

## C) Current Recommended Gate Roles

- Safe gate: `conservative_combo f=0.85 b=0.40 m=0.50`
  - Role: conservative output-only candidate / safe baseline prototype.
- Near-neighbor gate: `conservative_combo f=0.80 b=0.45 m=0.50`
  - Role: ablation/diagnostic candidate only.
- Promotion status: not promoted as final tracked project policy.

## D) Why It Is Not Promoted Yet

- Safe gate holdout gain is neutral (`+0.00pp`).
- Near-neighbor gain is modest (`+0.33pp` holdout) and not broad enough for promotion.
- Incremental review showed substantial log insufficiency (`13/17` switched cases tagged `insufficient_logs`).
- Recovery/regression behavior is not perfectly separable under current logging quality.
- Current evidence does not support broad claims of beating all external baselines.
- No final disjoint, promotion-grade validation yet against full external baseline set under matched budget/cost.

## E) Promotion Criteria (Output-Only -> Tracked/Promoted Policy)

1. Switched-case logging is sufficient for most cases, including:
   - candidate pool,
   - discovery/frontier tree,
   - node expansion order,
   - runtime-cap status,
   - parser/canonicalizer trace,
   - verifier scores,
   - selector/gate features.
2. Manual review of switched regressions shows no unacceptable systematic failure mode.
3. Gate beats `external_l1_max` on held-out artifacts with paired/cluster uncertainty not strongly negative.
4. Gate shows non-negative net gain overall and by major artifact family, or provides clear documented exception rationale.
5. Gate is validated on disjoint cases not used to tune thresholds.
6. Gate is compared against strong external baselines under matched budget/cost:
   - `external_l1_max`
   - `external_s1_budget_forcing`
   - `external_tale_prompt_budgeting`
   - PAL/frontier variants at matched budget/cost.
7. If existing logs are insufficient for diagnosis/promotion, run targeted Cohere failure-collection with strict schema before promotion.

## F) Cohere API Decision

- Cohere API collection is not needed immediately.
- Cohere collection becomes justified only if existing logs cannot support sufficient diagnosis/promotion, or if fresh disjoint failure cases with complete schema are required.
- Any future Cohere collection must be targeted, capped, disjoint, and preserve full logs/discovery-tree provenance.

## G) Immediate Next Steps (Ranked)

1. Improve and verify log sufficiency for incremental switch cases.
2. Standardize runtime-cap and full discovery-tree fields in future records.
3. Continue manual switched-case audit where ambiguity remains.
4. Prepare a targeted Cohere failure-collection design only if log sufficiency remains inadequate.
5. Do not claim external-baseline superiority yet.

## Current Decision Snapshot

- Default recommendation: keep safe gate as conservative freeze candidate, keep near-neighbor as ablation.
- Tracked-source promotion: defer (remain output-only until criteria above are satisfied).

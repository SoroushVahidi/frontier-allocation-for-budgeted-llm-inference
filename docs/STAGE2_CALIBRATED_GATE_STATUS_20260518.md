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
| Incremental switch log-sufficiency repair | `outputs/incremental_switch_log_sufficiency_repair_20260518T161301Z/` | Cases checked `17`; previously insufficient `13`; recovered to sufficient `11/13`; final sufficiency `yes/partial/no = 13/2/2`; added recoveries `2/2` fully reviewable; added regressions `0/2` fully reviewable due to runtime-cap gaps. | Completed |

## B.1) Incremental Switch Log-Sufficiency Repair

- Output: `outputs/incremental_switch_log_sufficiency_repair_20260518T161301Z/`
- Incremental switched cases checked: `17`
- Previously insufficient: `13`
- Recovered from insufficient to sufficient: `11/13`
- Final sufficiency split: `yes=13`, `partial=2`, `no=2`
- Added recoveries: `2/2` fully reviewable
- Added regressions: `0/2` fully reviewable
- Unresolved regression caveat: remaining unresolved regressions are tied to frontier runtime-cap failures (`Global logical API call cap reached`), with missing frontier answer/trace and missing promotion-grade expansion/selection logging.

Decision impact:
- This strengthens the non-promotion decision for the near-neighbor gate.
- Keep safe gate as the only conservative output-only candidate.
- Keep near-neighbor as ablation/diagnostic only; do not promote.
- Cohere API is still not immediately required, but future targeted collection (if needed) must preserve runtime-cap and frontier-trace completeness.

## C) Current Recommended Gate Roles

- Safe gate: `conservative_combo f=0.85 b=0.40 m=0.50`
  - Role: conservative output-only candidate / safe baseline prototype.
- Near-neighbor gate: `conservative_combo f=0.80 b=0.45 m=0.50`
  - Role: ablation/diagnostic candidate only; not promotable from current logs.
- Promotion status: not promoted as final tracked project policy.

## D) Why It Is Not Promoted Yet

- Safe gate holdout gain is neutral (`+0.00pp`).
- Near-neighbor gain is modest (`+0.33pp` holdout) and not broad enough for promotion.
- Incremental review showed substantial log insufficiency (`13/17` switched cases tagged `insufficient_logs`).
- Log-sufficiency repair recovered most neutral switches, but the two incremental near-neighbor regressions remain unresolved and not fully reviewable due to runtime-cap-related missing frontier logs.
- Recovery/regression behavior is not perfectly separable under current logging quality.
- Current evidence does not support broad claims of beating all external baselines.
- No final disjoint, promotion-grade validation yet against full external baseline set under matched budget/cost.

## E) Promotion Criteria (Output-Only -> Tracked/Promoted Policy)

1. Switched-case logging is sufficient for most cases, including:
   - candidate pool,
   - discovery/frontier tree,
   - node expansion order,
   - prune/selection reasons,
   - runtime-cap status,
   - frontier answer/trace (or explicit serialized empty/failure state when runtime-capped),
   - parser/canonicalizer trace,
   - verifier scores,
   - selector/gate features.
2. Manual review of switched regressions shows no unacceptable systematic failure mode.
   - Runtime-cap regressions cannot be treated as acceptable for promotion unless logs are complete enough to diagnose cause and counterfactual gate behavior.
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
- Cohere collection becomes justified only if existing logs cannot support sufficient diagnosis/promotion (including unresolved runtime-cap regression gaps), or if fresh disjoint failure cases with complete schema are required for promotion/final external-baseline comparison.
- Any future Cohere collection must be targeted, capped, disjoint, and preserve full logs/discovery-tree provenance.

## F.1) Promotion-Review Logging Schema

- New helper module: `scripts/failure_case_logging_schema.py`
- Purpose:
  - Build a normalized promotion-review record for each attempt, including runtime-cap/failure attempts.
  - Validate log sufficiency for promotion-grade review.
  - Return:
    - `enough_for_promotion_review` (`yes`/`partial`/`no`)
    - `missing_required_fields`
    - `missing_critical_fields`
    - `notes`
    - `runtime_failure_reviewable` (`yes`/`no`)

Runtime-cap requirement:
- Runtime-cap/failure rows must serialize explicit empty/unavailable states instead of silently missing fields, including:
  - frontier/candidate answer (`explicit empty` marker when absent),
  - frontier/candidate trace (`explicit empty` marker when absent),
  - node expansion order (`explicit unavailable` marker when absent),
  - prune/selection reasons (`explicit unavailable` marker when absent),
  - explicit status/error plus cost/call-count context.

Schema boundary:
- `exact_match` and `gold_answer` are retained only as `offline_eval_only` metadata.
- They are not required for promotion log sufficiency and must never be used as runtime prompt/model features.

Integration guidance:
- This helper is intentionally minimal and reusable; it is not wired into every writer yet.
- Future Cohere/failure-collection/frontier writers that emit `per_example_records.jsonl`
  should call:
  - `build_promotion_review_record(...)` when constructing per-attempt rows,
  - `validate_promotion_review_record(...)` before final write/report aggregation.
- If unresolved runtime-cap reviewability remains after current artifacts, a targeted
  collection (still not immediate) must use this schema and preserve full per-attempt logs.

## G) Immediate Next Steps (Ranked)

1. Improve and verify log sufficiency for incremental switch cases.
2. Standardize runtime-cap and full discovery-tree fields in future records.
3. Continue manual switched-case audit where ambiguity remains.
4. Prepare a targeted Cohere failure-collection design only if log sufficiency remains inadequate.
5. Do not claim external-baseline superiority yet.

## Current Decision Snapshot

- Default recommendation: keep safe gate as conservative freeze candidate, keep near-neighbor as ablation.
- Tracked-source promotion: defer (remain output-only until criteria above are satisfied).

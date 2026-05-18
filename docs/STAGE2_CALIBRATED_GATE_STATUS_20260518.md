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
- First wired writer (minimal integration, backward-compatible):
  - `scripts/run_cohere_real_model_cost_normalized_validation.py`
  - New per-row fields:
    - `promotion_review_record`
    - `promotion_review_validation`
  - Runtime-cap/failure rows now serialize explicit empty/unavailable markers through the helper path.
- Real Cohere pilot check:
  - `outputs/cohere_promotion_review_logging_pilot_20260518T164702Z/`
  - Confirmed real API rows emit both promotion-review fields.
  - First pilot success rows were `partial` because generation-time prompt/verifier/score/selection-gap fields were left implicit.
  - Schema/writer now require explicit generation-time markers (`__not_scored_yet__`, `__unavailable_not_recorded__`, prompt hash/pointer) so pre-offline-scoring rows can validate as promotion-reviewable (`yes`) when otherwise complete.
- This helper remains intentionally minimal/reusable and is not yet wired into every writer.
- Future Cohere/failure-collection/frontier writers that emit `per_example_records.jsonl` should call:
  - `build_promotion_review_record(...)` when constructing per-attempt rows.
  - `validate_promotion_review_record(...)` before final write/report aggregation.
- For promotion-grade audits, verify `promotion_review_validation.enough_for_promotion_review`.
- If unresolved runtime-cap reviewability remains after current artifacts, a targeted
  collection (still not immediate) must use this schema and preserve full per-attempt logs.

## F.2) Cohere Promotion-Review Logging Pilot 2

- Output: `outputs/cohere_promotion_review_logging_pilot2_20260518T170030Z/`
- Per-example records rows: `4`
- Promotion-review sufficiency: `enough_for_promotion_review` `yes=4/4`, `partial=0/4`, `no=0/4`
- Runtime-failure reviewability: `yes=4/4`, `no=0/4`
- Explicit marker coverage on success-path rows:
  - `prompt_hash` present `4/4`
  - `raw_proba_ready=__not_scored_yet__` `4/4`
  - `verifier_scores_pointer=__not_scored_yet__` `4/4`
  - `prune_or_selection_reasons` explicit unavailable/not_applicable when absent
- Silent missing required marker fields: `0`
- Prompt/feature leakage checks (`gold` / `exact_match`): `0`
- Outcome: success-path promotion-review logging readiness is confirmed for the main Cohere writer.
- Caveat: no runtime-failure rows occurred in this pilot, so runtime-failure-path readiness remains synthetic-tested only.
- Decision impact: future targeted failure collection can use the same main Cohere writer + schema path.

## F.3) Seed-Flip Manual Audit: openai_gsm8k_144

- Output: `outputs/seed_flip_manual_audit_openai_gsm8k_144_20260518T205529Z/`
- Source artifact: `outputs/targeted_cohere_merged_seed11_seed23_analysis_1779133255/` (160 rows, 40 examples, seeds 11/23, budget 6)
- Methods compared: `direct_reserve_semantic_frontier_v2` (frontier) vs `external_l1_max`

### Correctness Matrix (openai_gsm8k_144, gold = 20)

| Method | Seed 11 | Answer | Seed 23 | Answer |
|---|---|---|---|---|
| frontier | ✓ correct | 20 | ✗ wrong | 9 |
| external_l1_max | ✗ wrong | 5 | ✓ correct | 20 |

No parse extraction failures on any row. Wrong answers are clearly arithmetically wrong (5 = cloth pack unit cost; 9 = cost per client — both mid-reasoning intermediate values).

### Root Cause

Two independent stochastic events, not systematic method superiority:

- **External seed=11 failure:** Stochastic truncation + parser artifact. Model returned `action: continue` mid-reasoning (1 API call only); parser extracted `5` from `"$5 per cloth pack"` in the partial text. `gold_in_tree=0`.
- **External seed=23:** Clean 3-step completion; model correctly computed $92 − $72 = $20. No issue.
- **Frontier seed=11:** Both direct-reserve attempts independently returned 20 (confidence = 1.0, 2/2 agreement). Correct, stable.
- **Frontier seed=23 failure:** Stochastic selection artifact. Direct-reserve attempt[0] captured intermediate value 9 (cost per client); attempt[1] correctly returned 20. Support split 1:1; tiebreak selected 9. Frontier ran, returned candidate 10 (also wrong). Override rejected (`single_weak_frontier_branch`). `gold_in_tree=1`; failure tag: `correct answer present but not selected`.

### Sampled Pattern Across 40 Examples

| Metric | Value |
|---|---|
| External flip rate (different across seeds) | 14/40 = **35%** |
| Frontier flip rate (different across seeds) | 5/40 = **12.5%** |
| Frontier stably correct (both seeds) | 27/40 = **67.5%** |
| External stably correct (both seeds) | 22/40 = **55%** |
| Frontier wins seed=11, external fails | 7 |
| External wins seed=23, frontier fails | 4 |

Pattern: Most external flips follow "absent from explored tree" on seed=11 → correct on seed=23. Frontier failures are predominantly selection artifacts ("correct answer present but not selected"), not reasoning failures.

### Interpretation

- Seed reversal is driven by high external seed variance (35% flip rate), not a genuine external-baseline superiority signal.
- Frontier stability is substantially better than external on this diagnostic artifact, but 40 examples and 2 seeds are insufficient for gate-design or promotion claims (±~8pp CI at 95%).
- Artifact remains **diagnostic only**. No gate promotion evidence.

### Decision

- No further Cohere API is needed immediately from this audit.
- The 6–8 seed robustness run (referenced in `TARGETED_COHERE_FAILURE_COLLECTION_PLAN_20260518.md`) remains optional/future and should not be launched until there is a clear decision that larger seed-robustness evidence is needed.
- Recommendation: **C** — treat artifact as diagnostic, update docs, do not run more API now.

## G) Immediate Next Steps (Ranked)

1. Improve and verify log sufficiency for incremental switch cases.
2. Standardize runtime-cap and full discovery-tree fields in future records.
3. Continue manual switched-case audit where ambiguity remains.
4. Prepare a targeted Cohere failure-collection design only if log sufficiency remains inadequate.
5. Do not claim external-baseline superiority yet.

## Current Decision Snapshot

- Default recommendation: keep safe gate as conservative freeze candidate, keep near-neighbor as ablation.
- Tracked-source promotion: defer (remain output-only until criteria above are satisfied).

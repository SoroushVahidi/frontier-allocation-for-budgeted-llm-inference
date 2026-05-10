# Cohere Diverse-Anchor Failure-Recovery Diagnostic (30-case attempt) — Invalidated

## Executive status

This run **does not answer the primary recovery question**. Cohere credentials worked and a live Cohere-only run completed, but post-run validation found that the existing runner did not load the selected failure cases. The runner loads `openai/gsm8k` through a shuffled pilot subset and assigns `example_id` by shuffled position; the failure artifacts also use IDs like `openai_gsm8k_337`, but those IDs did not resolve to the same questions/gold answers in this harness. Therefore the raw exact/gold-in-pool/diversity numbers below are **invalid for the selected failure set** and must not be interpreted as recovery evidence.

## Methods

1. Old/pre-diverse-anchor method requested/resolved for the paired comparison: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_hybrid`.
2. New diverse-anchor method: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor`.

The old method was chosen as the direct parent of the diverse-anchor implementation because the new method is registered as the guarded K1/frontier4 frontier-tiebreak direct-hybrid line plus diverse prompt anchors.

## Selected 30 failure cases and why

Selected from `docs/project_handoff_20260510/exhaustive_failure_audit/full_latest_method_failures.csv` joined to `docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv`. Criteria: latest fully tracked failures, gold known in the subpattern artifact, gold-absent/low-diversity preference, stratified 10/10/10 across money/cost/revenue, multi-step arithmetic, and ratio/proportion/percentage; L1-correct contrast cases were prioritized within each domain.

Selected IDs: openai_gsm8k_337, openai_gsm8k_245, openai_gsm8k_17, openai_gsm8k_22, openai_gsm8k_73, openai_gsm8k_168, openai_gsm8k_190, openai_gsm8k_213, openai_gsm8k_239, openai_gsm8k_264, openai_gsm8k_217, openai_gsm8k_6, openai_gsm8k_36, openai_gsm8k_162, openai_gsm8k_180, openai_gsm8k_184, openai_gsm8k_197, openai_gsm8k_324, openai_gsm8k_367, openai_gsm8k_433, openai_gsm8k_358, openai_gsm8k_51, openai_gsm8k_70, openai_gsm8k_166, openai_gsm8k_262, openai_gsm8k_347, openai_gsm8k_450, openai_gsm8k_458, openai_gsm8k_508, openai_gsm8k_551.

## Budget and API use

- Pre-run estimated maximum logical Cohere calls: 30 cases × 2 methods × budget 4 = 240, below the 300-call cap.
- Actual controller logical Cohere calls used: 180 / 300.
- Cohere readiness check: passed.
- Hugging Face dataset access: worked, but the harness used a shuffled pilot loader with unstable ID semantics for these artifacts.
- No OpenAI, Gemini, Anthropic, or other paid APIs were used.

## Required answers (validity-aware)

1. Old method used: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_hybrid`.
2. Diverse-anchor method used: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor`.
3. Selected cases: listed above; selected for latest tracked gold-absent/low-diversity failure recovery and stratified by dominant failure domain.
4. Logical Cohere calls: 180 / 300 controller calls.
5. Old failures recovered: **not validly measurable from this run**. Raw invalidated runner classification showed 5 old-wrong/new-correct cases, but those were different shuffled GSM8K examples, not the selected failure artifacts.
6. Recovery rate: **not validly measurable**. Raw invalidated rate would be 5/30 = 0.167, but must not be used.
7. Gold-in-pool improvement: **not validly measurable**. Raw invalidated counts were old 26/30 vs new 22/30.
8. Candidate answer-group count improvement: **not validly measurable**. Raw invalidated means were old 1.733 vs new 2.800.
9. Answer-group entropy improvement: **not validly measurable**. Raw invalidated means were old 0.490 vs new 0.880.
10. Frontier collapse decrease: **not validly measurable**. Raw invalidated counts were old 11/30 vs new 4/30.
11. Useful/correct anchors: **not validly measurable for selected failures**. In the invalidated raw runner data, anchor correct counts were {'direct_l1_anchor': 19, 'equation_first_anchor': 10, 'unit_ledger_money_anchor': 11} and support totals were {'direct_l1_anchor': 62, 'equation_first_anchor': 56, 'unit_ledger_money_anchor': 62}.
12. Improved cases: **none reported as valid**. Raw invalidated IDs: ['openai_gsm8k_190', 'openai_gsm8k_162', 'openai_gsm8k_433', 'openai_gsm8k_347', 'openai_gsm8k_508'].
13. Still-failed cases: **none reported as valid**. Raw invalidated IDs: ['openai_gsm8k_168', 'openai_gsm8k_264', 'openai_gsm8k_197', 'openai_gsm8k_70', 'openai_gsm8k_166', 'openai_gsm8k_551'].
14. Regressions: **none reported as valid**. Raw invalidated IDs: ['openai_gsm8k_217', 'openai_gsm8k_6', 'openai_gsm8k_36', 'openai_gsm8k_450', 'openai_gsm8k_458'].
15. Larger 50/100-case failure-recovery run: **not justified until the loader/allowlist contract is fixed and dry-run validation proves the artifact IDs map to the intended questions/gold answers before any API calls**.
16. Matched random/held-out evaluation afterward: **not justified until this targeted failure-recovery harness is repaired and a valid small run completes**.

## Exact blocker

For every selected case checked post-run, the selected artifact gold differed from the runner-loaded gold. Example: `openai_gsm8k_6` was selected with artifact gold `310`, but the runner loaded a different GSM8K question with gold `32`. This means the existing `allowed-example-ids-file` path is insufficient for exact failure-artifact replay when IDs are generated after shuffling.

## Implementation/fix plan

1. Build an exact-case JSONL from the source artifacts that includes `example_id`, full question text, and canonical gold answer for each failure.
2. Add an exact-case runner mode or dataset loader that consumes that JSONL directly, without shuffling or reassigned IDs.
3. Require allowlist rows to include expected question/gold and fail before API calls if the loaded example does not match. This PR adds a guard for expected question/gold in `scripts/run_cohere_real_model_cost_normalized_validation.py`; the next run should include those fields.
4. Re-estimate calls. With budget 4 and the observed call pattern, a valid 30-case paired run should fit under 300 logical controller calls, but it must be preceded by a no-API exact-case validation.
5. Only after the 30-case exact failure-recovery run succeeds should a 50/100-case run or matched held-out evaluation be considered.

## Interpretation caveat

Because the intended test set is intentionally selected from previous failures, a valid run could show failure recovery but could not prove overall accuracy or superiority over external baselines. This attempted run is additionally invalidated by case-ID mismatch, so it should be treated only as a provenance record and harness-blocker report.

# Canonical Project State and Next Steps (2026-04-29)

Purpose: stop repeated work and make the current repository state easy to understand for future agents, Codex runs, and paper/research decisions.

This is the canonical high-level project ledger. If future experiments change these conclusions, update this file and link the new evidence.

## 1. Current top-level conclusion

The project currently has strong evidence that `external_l1_max` is the strongest real-model baseline in the Cohere GSM8K diagnostic setting we have repeatedly tested.

No internal method has yet clearly defeated `external_l1_max` in a meaningful broad real-model comparison. Several internal variants had small or diagnostic positive signals, but the larger follow-ups either reversed or remained inconclusive.

The best current algorithmic direction is **not another broad sweep of unchanged methods**. The best direction is a targeted selector improvement for DR-v2: **answer-grouped outcome-verifier reranking / commit-time verifier reranking**.

## 2. What we should not repeat

Do not repeat these tasks unless a method implementation changes:

1. Do not rerun unchanged `direct_reserve_semantic_frontier_v2` vs `external_l1_max` on Cohere GSM8K budget 4 seed 11. The 100-case result already exists and is unfavorable to DR-v2.
2. Do not rerun unchanged `direct_reserve_semantic_frontier_v2_selection_fix_v1` vs `external_l1_max` on the same setting. It was slightly worse than original DR-v2.
3. Do not rerun unchanged `strict_gate1_cap_k6` vs `external_l1_max` on the same 100-case setting. It lost badly.
4. Do not treat the 10-example DR-v2 win as stable evidence. It was rejected by the 100-case follow-up.
5. Do not include `direct_reserve_semantic_frontier_v2_thresholded_ordered` in live Cohere comparisons until it is actually registered in the runtime path.
6. Do not implement another simple support-count-only selector fix. `selection_fix_v1` already tested that style and did not improve.
7. Do not run a broad API experiment before writing the exact method hypothesis and expected failure mode it targets.

## 3. Method result ledger

### `external_l1_max`

Role: strongest real-model external baseline.

Known behavior:

- Cheap, direct, and strong on GSM8K Cohere diagnostics.
- In recent 100-case runs, it is more accurate and cheaper than tested internal variants.

Representative results:

- Vs `direct_reserve_semantic_frontier_v2`: 0.72 vs 0.56 on 100-case Cohere GSM8K budget 4 seed 11.
- Vs `direct_reserve_semantic_frontier_v2_selection_fix_v1`: 0.72 vs 0.55 on the same completed run.
- Vs `strict_f3`: 0.72 vs 0.56 in that completed four-method run.
- Vs `strict_gate1_cap_k6`: 0.75 vs 0.48 in the targeted 100-case diagnostic.

Status: active baseline; use as the primary external comparator.

---

### `strict_f3`

Role: older manuscript/internal representative; not the newest or most promising real-model candidate.

Known results:

- Loses to `external_l1_max` in Cohere diagnostics.
- Completed four-method 100-case DR-v2 run: strict_f3 accuracy 0.56 vs L1 0.72.

Main failure modes:

- Mixed: correct answer absent from tree and correct answer present but not selected.
- Older casebooks have incomplete trace instrumentation.

Status: keep as reference/internal baseline, not primary improvement target.

---

### `strict_gate1_cap_k6`

Role: strict-gate/cap method; had a partial small positive signal but failed clean validation.

Completed targeted 100-case result:

- Setting: Cohere, GSM8K, budget 4, seed 11.
- `strict_gate1_cap_k6`: 0.48.
- `external_l1_max`: 0.75.
- Delta: -0.27.
- Paired W/T/L: 1 / 71 / 28.
- Tokens/cost/latency: 92,503 tokens, $0.471117, 4.1036s mean latency.
- L1 tokens/cost/latency: 49,606 tokens, $0.277338, 3.2539s mean latency.

Main failure modes:

- 26/28 losses: correct answer absent from explored tree.
- 2/28 losses: correct answer present but not selected.

Status: not a good selector-fix target. If revisited, target generation/coverage/seeding first.

---

### `direct_reserve_semantic_frontier_v2` / DR-v2

Role: most important newer internal candidate.

Small positive signal:

- 10-example Cohere GSM8K budget 4 seed 11 preflight: DR-v2 0.70 vs L1 0.60.

Follow-up larger result:

- Completed 100-case Cohere GSM8K budget 4 seed 11: DR-v2 0.56 vs L1 0.72.
- Delta: -0.16.
- Paired W/T/L: 9 / 66 / 25.
- DR-v2 tokens/cost/latency: 112,162 tokens, $0.590502, 9.2057s mean latency.
- L1 tokens/cost/latency: 48,892 tokens, $0.272604, 3.6775s mean latency.

Main failure modes:

- Trace-complete 20-case audit found 3 L1-correct / DR-v2-wrong cases.
- All 3 were `selection_failure_present_not_selected`.
- Absent from frontier: 0/3.
- Present but not selected: 3/3.

Status: best current algorithm-improvement target because the correct candidate can be present, but final selector fails.

Next action: implement answer-grouped outcome-verifier reranking as a DR-v2 final selector.

---

### `direct_reserve_semantic_frontier_v2_selection_fix_v1`

Role: first simple support-count final selection fix for DR-v2.

Results:

- 20-case targeted run: tied original DR-v2 at 0.60 and lost to L1 at 0.70.
- Completed 100-case run: 0.55 vs original DR-v2 0.56 and L1 0.72.
- Paired W/T/L vs L1: 9 / 65 / 26.
- Tokens/cost/latency: 112,306 tokens, $0.594198, 8.1336s mean latency.

Status: tested and not helpful. Do not repeat simple support-only override.

---

### `direct_reserve_semantic_frontier_v2_thresholded_ordered`

Role: diagnostic-only method.

Status:

- Not live-runnable in current Cohere runner path.
- Must remain excluded from live comparisons until implemented in `build_frontier_strategies(...)` / runtime registry.

---

### `near_direct_reserve_frontier_gate_v1` and `calibrated_near_direct_frontier_gate_v1`

Role: offline/diagnostic gate variants.

Results:

- Near-direct version showed a small offline reported-surface improvement over L1 in one sweep.
- Calibrated clean version tied L1 rather than beating it.

Status: low priority; not a clean real-model improvement path.

---

### Direct-reserve v1/v2 semantic-diversity diagnostics

Role: diagnostic family showing direct-reserve ideas can help selected loss cohorts.

Important note:

- Some selected/duplicated diagnostic cohorts show direct-reserve methods near or above L1.
- These are not broad real-model wins and usually come with higher action/cost.

Status: evidence supports keeping the direct-reserve family, but not claiming broad superiority.

## 4. Selector/verifier status

The repository already contains several selector/verifier/scorer ideas, but most are not integrated as the live DR-v2 final selector.

### Already present

- `experiments/verifiers.py`
  - `CandidateVerifier`
  - `LLMVerifyProxyVerifier`
  - `SimulatedScorerVerifier`
- `experiments/scoring.py`
  - heuristic branch scorers
  - learned branch scorers
  - Bradley-Terry branch scorer
  - tie-aware BT scorer
  - Rao-Kupper/Davidson-style tie models
  - near-tie two-stage scorer
- Outcome-verifier diagnostics
  - `scripts/run_outcome_verifier_selector_diagnostic.py`
  - `scripts/run_cobbe_style_outcome_verifier_diagnostic.py`
- PRM proxy branch scoring
  - `adaptive_prm_partial`
  - `adaptive_prm_partial_early_reject`
  - `verifier_guided_search_prm`
  - `verifier_guided_search_prm_early_reject`

### Missing / needed

A live DR-v2 final-answer-group selector that uses an outcome verifier/reranker at commit time.

Recommended method name:

- `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`

Method idea:

- Generate candidates with DR-v2.
- Normalize final answers.
- Group candidates by normalized final answer.
- Score candidate traces with an outcome verifier.
- Aggregate scores within answer groups using log-sum-exp plus support bonus.
- Pick the answer group with the highest aggregate score.

## 5. Published-paper linkage

Paper-backed or paper-inspired components:

- Cobbe-style outcome verifier diagnostics: based on Cobbe et al., *Training Verifiers to Solve Math Word Problems*.
- PRM proxy scoring: inspired by process reward model work such as *Let's Verify Step by Step* and Math-Shepherd, but current implementation is only proxy-level.
- Bradley-Terry / Davidson / Rao-Kupper scoring: based on classical pairwise ranking / tie-aware preference models.

Internal/proxy components:

- `strict_f3`, `strict_gate1_cap_k6`, DR-v2, DR-v2 selection fix, and direct-reserve gates are project-specific algorithms or heuristics.

## 6. Immediate next work plan

### Step 1: implement selector module

Implement:

- `experiments/answer_grouped_outcome_verifier.py`
- tests in `tests/test_answer_grouped_outcome_verifier.py`
- method documentation in `docs/ANSWER_GROUPED_OUTCOME_VERIFIER_RERANK_V1.md`

This implementation should include mock verifier tests first and must not require a large API run.

### Step 2: integrate as live runnable DR-v2 variant

Register:

- `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`

It should use the same generation/search behavior as DR-v2 and only change final answer selection.

### Step 3: run small smoke test

Use mock or very small API run only to prove the method is wired.

### Step 4: run real 100-case comparison

Methods:

- `external_l1_max`
- `direct_reserve_semantic_frontier_v2`
- `direct_reserve_semantic_frontier_v2_selection_fix_v1`
- `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`

Setting:

- Cohere
- GSM8K
- budget 4
- seed 11
- 100 scored examples per method

Required outputs:

- candidate verifier scores
- answer group scores
- selector decisions
- paired summary vs baselines
- present-not-selected recovery cases
- verifier regression cases
- run manifest
- diagnosis notes

## 7. Repository maintenance rule

Any future agent should update this file whenever:

- a new method is added;
- a method is promoted from diagnostic-only to live-runnable;
- a 100-case or larger validation completes;
- a method's failure mode changes;
- a selector/verifier idea is implemented or rejected.

Do not leave method status only in scattered run reports.

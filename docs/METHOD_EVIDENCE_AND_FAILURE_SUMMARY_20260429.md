# Method Evidence and Failure Summary (2026-04-29)

Purpose: preserve what we have already learned so future agents do not repeat the same experiments, confuse small-sample signals with stable evidence, or test the wrong algorithm version.

This document summarizes the current evidence around our internal methods versus `external_l1_max`, especially real Cohere GSM8K diagnostics and newer DR-v2 / strict-gate variants.

## 1. High-level conclusion

As of this audit, no internal method has clearly beaten `external_l1_max` in a meaningful broad real-model comparison.

There are small or diagnostic positive signals, but the clean larger follow-ups do not preserve them:

- `direct_reserve_semantic_frontier_v2` beat `external_l1_max` on one 10-example Cohere preflight, but lost on a completed 100-case validation in the same GSM8K budget-4 seed-11 setting.
- `strict_gate1_cap_k6` had a partial small positive snapshot, but lost badly on a completed 100-case Cohere validation.
- `near_direct_reserve_frontier_gate_v1` and `direct_reserve_frontier_gate_v2` showed offline/reported-surface gains, but those were diagnostic and artifact-sensitive.

The strongest current algorithm-development direction is not more broad measurement. It is to improve the newer DR-v2 final selection / commit-time reranking, because DR-v2 loss traces show that correct candidates can be present but not selected.

## 2. Method-by-method status

### `external_l1_max`

Role: strongest real-model external baseline in current Cohere GSM8K diagnostics.

Observed behavior:

- Consistently strong accuracy with low action/token/cost usage.
- In recent 100-case tests, it is both more accurate and cheaper than internal variants.
- Often solves cases with a simple direct route where internal controllers spend more budget but still fail.

Known representative results:

- Against `strict_f3` in broad Cohere run: `external_l1_max` accuracy 0.5367 vs `strict_f3` 0.4500, paired delta around -0.0899 from strict to L1.
- Against DR-v2 in 100-case GSM8K budget-4 seed-11 run: 0.72 vs DR-v2 0.56.
- Against `strict_gate1_cap_k6` in 100-case GSM8K budget-4 seed-11 run: 0.75 vs strict_gate1 0.48.

Takeaway: use this as the baseline to beat; do not assume internal controllers beat it unless a completed paired run proves it.

---

### `strict_f3`

Role: older manuscript-facing/internal representative, but not the strongest real-model candidate.

Observed wins:

- Can beat weaker internal variants in some matched-surface contexts.
- In some tiny Cohere smoke runs it ties `external_l1_max`, but this is not a stable win.

Observed losses:

- Loses to `external_l1_max` in Cohere diagnostics.
- In a 30-matched diagnostic, strict_f3 vs `external_l1_max` had negative delta around -0.2667 with negative confidence interval.
- In a larger Cohere run, strict_f3 had lower aggregate accuracy than `external_l1_max` and higher cost/tokens.

Failure modes:

- Older strict_f3 loss casebooks show a mix of:
  - correct answer absent from explored tree;
  - correct answer present but not selected.
- The older 10-case deep dive had many absent-from-tree cases and several present-not-selected cases.

Takeaway: do not use strict_f3 as the only proxy for the newest algorithm. It is useful as a reference but not the current best development target.

---

### `strict_gate1_cap_k6`

Role: operational strict-gate/cap variant; had a small partial positive signal but failed larger validation.

Small positive signal:

- Partial local Cohere snapshot reported `strict_gate1_cap_k6` around 0.75 vs `external_l1_max` around 0.70.
- This was not a clean, completed, final paired 100-case validation.

Completed larger test:

- Timestamp: `20260429T_STRICT_GATE1_CAP_K6_VS_L1_100CASE_DIAG`.
- Dataset/provider/budget/seed: Cohere, `openai/gsm8k`, budget 4, seed 11.
- Target: 100 scored examples per method.
- Result:
  - `strict_gate1_cap_k6`: 0.48
  - `external_l1_max`: 0.75
  - delta strict_gate1 - L1: -0.27
  - paired wins/ties/losses: 1 / 71 / 28
  - strict_gate1 tokens/cost/latency: 92,503 tokens, $0.471117, 4.1036s mean latency
  - external_l1 tokens/cost/latency: 49,606 tokens, $0.277338, 3.2539s mean latency

Failure modes from the 100-case diagnosis:

- 28 strict_gate1 loss cases to L1.
- correct answer absent from explored tree: 26 / 28 losses.
- correct answer present but not selected: 2 / 28 losses.
- stable branch-path-to-correct instrumentation was not fully available.

Takeaway:

- The small positive signal did not hold.
- For strict_gate1, the main problem is coverage/recall: the correct answer usually never enters the explored tree.
- Fixing strict_gate1 likely requires better candidate generation/seeding/coverage before selector tuning.

---

### `direct_reserve_semantic_frontier_v2` (DR-v2)

Role: most important newer internal candidate and the strongest historically documented internal method against L1 in small-sample evidence.

Small positive signal:

- In `BEST_INTERNAL_VARIANTS_COHERE_PREFLIGHT_20260429`, DR-v2 beat `external_l1_max` on a 10-example Cohere GSM8K budget-4 seed-11 preflight:
  - DR-v2: 0.70
  - `external_l1_max`: 0.60
  - delta: +0.10
  - paired W/T/L: 3 / 5 / 2.

Follow-up larger evidence:

- 20-case run:
  - DR-v2: 0.60
  - `external_l1_max`: 0.70
  - delta: -0.10.
- Completed 100-case run:
  - DR-v2: 0.56
  - `external_l1_max`: 0.72
  - delta: -0.16
  - paired W/T/L: 9 / 66 / 25
  - DR-v2 tokens/cost/latency: 112,162 tokens, $0.590502, 9.2057s mean latency
  - L1 tokens/cost/latency: 48,892 tokens, $0.272604, 3.6775s mean latency.

Failure modes:

- Trace-complete DR-v2 loss audit on 20 matched cases found 3 L1-correct / DR-v2-wrong cases.
- All 3 were classified as `selection_failure_present_not_selected`:
  - absent from frontier: 0 / 3
  - present but not selected: 3 / 3
  - extraction/canonicalization failure: 0 / 3
  - commit/over-exploration failure: 0 / 3
  - trace-missing/unclassifiable: 0 / 3.

Takeaway:

- DR-v2 is not currently better than L1 at 100 cases.
- But DR-v2 is still the best development target because its losses look more fixable than strict_gate1: the correct answer can already be present but final selection fails.
- Next work should focus on commit-time verification, reranking, answer-group support calibration, and selector logic rather than simply expanding more branches.

---

### `direct_reserve_semantic_frontier_v2_selection_fix_v1`

Role: first simple DR-v2 selection fix.

Motivation:

- Implemented because DR-v2 trace audit identified `selection_failure_present_not_selected`.
- Intended to change final selection when frontier answer-group support is strictly higher than direct-reserve support.

Results:

- 20-case targeted run:
  - DR-v2 original: 0.60
  - selection-fix: 0.60
  - `external_l1_max`: 0.70
  - selection-fix applied in 2 / 20 cases but gave no net exact-match gain.
- Completed 100-case run:
  - selection-fix: 0.55
  - DR-v2 original: 0.56
  - `external_l1_max`: 0.72
  - delta selection-fix - L1: -0.17
  - paired W/T/L vs L1: 9 / 65 / 26
  - tokens/cost/latency: 112,306 tokens, $0.594198, 8.1336s mean latency.

Takeaway:

- The first support-only selection fix did not work.
- The evidence still points to selector/reranker failure, but the fix must be stronger than a simple support-count override.
- Next version should likely use a verifier/reranker over candidate answer groups, not just raw support.

---

### `direct_reserve_semantic_frontier_v1` / `direct_reserve_frontier_gate_v2` / related direct-reserve diagnostics

Role: diagnostic family that showed that reserve-style behavior can help on selected loss cohorts.

Positive diagnostic evidence:

- Semantic-diversity loss-full analysis showed `direct_reserve_semantic_frontier_v1` reaching 0.7407 vs `external_l1_max` 0.6667 on a small selected cohort.
- DR-v2 long diagnostic showed strong numbers for `direct_reserve_semantic_frontier_v2` on a duplicated/selected-slot diagnostic sample.
- `direct_reserve_frontier_gate_v2` offline rule reached 0.7333 vs L1 0.7000 on reported surface.

Caveats:

- These are selected/cohort/offline/diagnostic settings, not broad clean real-model wins.
- Several positive cases are artifact-sensitive or duplicated-slot results.
- Cost/action usage is much higher than L1.

Failure/taxonomy signals:

- `bad_seeding_absent_answer_group` remains a meaningful contributor in broader diagnostics.
- `correct_answer_group_present_but_underweighted` also appears, but at lower frequency than bad seeding in some expanded-pool reports.
- Many rows are `unknown_unclassified` or `trace_sparse_or_truncated`, so deeper instrumentation is needed.

Takeaway:

- Direct-reserve is the right family to keep developing.
- It gives evidence that preserving a direct candidate can rescue some failures.
- But it must become cheaper and must use better final verification/reranking.

---

### `near_direct_reserve_frontier_gate_v1` and `calibrated_near_direct_frontier_gate_v1`

Role: offline/diagnostic gate variants.

Evidence:

- `near_direct_reserve_frontier_gate_v1` reported accuracy 0.7333 vs `external_l1_max` 0.7000 in one offline sweep.
- Calibrated version reported/clean accuracy 0.7000, tying L1 rather than beating it.
- The status doc explicitly says improvement over L1 clean is 0 and that a fresh real-model pilot is not justified.

Takeaway:

- Do not prioritize these unless new evidence appears.
- The apparent near-direct improvement is not clean enough.

---

### `direct_reserve_semantic_frontier_v2_thresholded_ordered`

Role: diagnostic-only / not currently live-runnable.

Status:

- Do not include in live full comparisons.
- It is not runtime-present in the current live `build_frontier_strategies(...)` path.
- Prior validation incorrectly made it appear runnable by mixing diagnostic and runtime registries.
- Zero-scored/diagnostic-only behavior has been diagnosed.

Takeaway:

- Exclude until it is actually implemented in the live runner path and validated as runtime-runnable.

## 3. Cross-method failure-mode map

| Method/family | Main loss mode vs external baselines | Evidence strength | Best next fix |
|---|---|---|---|
| `strict_f3` | mixed absent-from-tree and present-not-selected | older casebooks and diagnostics | not main development target |
| `strict_gate1_cap_k6` | mostly absent from tree / coverage failure | strong 100-case diagnostic: 26/28 losses absent | improve candidate generation/seeding/coverage |
| DR-v2 | present but not selected in trace-complete audit | targeted trace-complete audit: 3/3 losses present-not-selected | improve final selector/reranker/verifier |
| DR-v2 selection-fix v1 | selector fix too weak; no gain | 20-case and 100-case runs | replace simple support override with stronger verifier/reranker |
| direct-reserve v1/v2 diagnostics | mixed; direct reserve helps selected cohorts but costly | small/cohort diagnostics | reduce actions/cost and add commit verification |
| near-direct/calibrated gate | offline reported-surface only | diagnostic/artifact-sensitive | low priority |

## 4. What not to repeat

Do not repeat these mistakes:

1. Do not treat `strict_f3` as the newest/best internal method.
2. Do not infer broad win from the 10-example DR-v2 preflight.
3. Do not re-test DR-v2 vs L1 at GSM8K budget-4 seed-11 without changing the algorithm; the 100-case result already rejected the small positive signal.
4. Do not re-test `strict_gate1_cap_k6` vs L1 at the same 100-case setting without changing coverage/seeding; it lost by -0.27.
5. Do not include `direct_reserve_semantic_frontier_v2_thresholded_ordered` in live comparisons until runtime support exists.
6. Do not try another simple support-only selection fix; `selection_fix_v1` already failed to improve.
7. Do not run broad API sweeps before deciding what exact algorithmic hypothesis is being tested.

## 5. Recommended next algorithmic direction

The most evidence-aligned next direction is a newer DR-v2 variant focused on final selection:

Suggested method name:

- `direct_reserve_semantic_frontier_v2_commit_verifier_v1`
- or `direct_reserve_semantic_frontier_v2_verifier_rerank_v1`

Hypothesis:

DR-v2 often discovers a correct/gold-equivalent candidate but fails to select it. A lightweight commit-time verifier/reranker over candidate answer groups can recover present-not-selected losses without needing much more exploration.

Required features for next run:

- preserve all candidate answer groups;
- log selected answer, gold answer, candidate ranks, answer-group support, branch source, and final verifier score;
- compare direct-reserve incumbent against top frontier candidates;
- override only when verifier/support evidence is strong;
- record whether the gold answer is present in the candidate pool;
- record branch/action path to first gold-equivalent candidate when available;
- record per-branch/action token and cost where possible.

## 6. Minimal next experiment after implementing selector/reranker

Run only after a real DR-v2 selector/reranker change exists.

Recommended test:

- provider: Cohere
- dataset: `openai/gsm8k`
- budget: 4
- seed: 11
- target: 100 scored examples per method
- methods:
  - `external_l1_max`
  - `direct_reserve_semantic_frontier_v2`
  - new DR-v2 verifier/reranker variant
  - optionally `strict_f3` as a reference

Success criterion:

- new DR-v2 variant should improve over original DR-v2 on paired losses without materially increasing cost;
- ideally close the gap to L1 or beat L1 on non-tie cases;
- must produce a loss-diagnosis package with gold-in-tree and present-not-selected counts.

## 7. One-sentence memory

The current best path is not to expand strict_gate1 more; it is to improve DR-v2 final selection, because strict_gate1 mostly fails by not finding the answer, while DR-v2's trace-complete losses show the answer is often present but not selected.

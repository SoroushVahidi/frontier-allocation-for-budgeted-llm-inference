# Canonical Selector Registry (2026-04-29)

Purpose: organize all final-answer selector / reranker ideas so future work does not repeat old selector experiments or confuse implemented methods with planned paper-backed ideas.

This document is specifically about **which final answer to choose after candidate reasoning traces/answers exist**. It is not mainly about candidate generation, routing, or budget allocation.

Update this file whenever a selector is implemented, tested, rejected, promoted to live-runnable, or superseded.

## 1. Current selector problem

Recent diagnostics show two different failure profiles:

- `strict_gate1_cap_k6`: most losses to `external_l1_max` are **coverage failures**; the correct answer is usually absent from the explored tree.
- `direct_reserve_semantic_frontier_v2` (DR-v2): trace-complete loss audit suggests the correct answer can be **present but not selected**.

Therefore, the highest-value selector work is focused on DR-v2 final answer selection: preserve candidate generation, but improve the final selector/reranker.

## 2. Selector status summary

| Selector / method | Paper-backed? | Implemented? | Live-runnable? | Tested? | Current status | Next action |
|---|---:|---:|---:|---:|---|---|
| Original DR-v2 final selector | project-specific | yes | yes | yes | loses to `external_l1_max` in 100-case run; present-not-selected failures observed | do not retest unchanged |
| DR-v2 `selection_fix_v1` | no, internal support-count heuristic | yes | yes | yes | did not improve; 0.55 vs DR-v2 0.56 and L1 0.72 | do not repeat simple support-only fix |
| Cobbe-style outcome verifier diagnostic | yes | diagnostic only | no | diagnostic only | offline/paper-inspired diagnostic exists | use as basis for live DR-v2 selector |
| `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1` | Cobbe-inspired | planned / being implemented | pending | not yet validated | first recommended selector implementation | implement module + mock verifier + live registration, then 100-case validation |
| PRM-style step-level verifier selector | yes: *Let's Verify Step by Step*, PRM800K | no | no | no | second recommended selector family | implement after outcome-verifier reranker unless strong reason to skip |
| Math-Shepherd-style process verifier | yes | no | no | no | related later process-supervision direction | future comparison after PRM-style selector |
| Self-consistency / support-count voting | paper-related/general | partially via support heuristics | partly | yes indirectly | support-only version was insufficient | only use as feature, not sole selector |
| Bradley-Terry / tie-aware branch scorers | yes, classical ranking/tie models | yes for branch scoring | yes in branch contexts | yes in branch contexts | branch selector, not final answer-group selector | do not treat as final-answer verifier unless adapted |
| LLM-as-judge final answer verifier | generic/prompted verifier | partially scaffolded/proxy | no dedicated live selector yet | not validated | possible v1 backend for outcome verifier | use carefully; call it prompted approximation, not exact Cobbe |

## 3. Already tried final-answer selector ideas

### 3.1 Original DR-v2 selector

Method ID:

- `direct_reserve_semantic_frontier_v2`

What it does:

- Uses direct-reserve / semantic frontier candidate generation and an internal final-selection rule.

Important results:

- Small n=10 Cohere GSM8K budget-4 seed-11 preflight: DR-v2 0.70 vs `external_l1_max` 0.60.
- Completed 100-case Cohere GSM8K budget-4 seed-11 validation: DR-v2 0.56 vs `external_l1_max` 0.72.
- Paired W/T/L vs L1: 9 / 66 / 25.
- More expensive than L1: 112,162 tokens / $0.590502 vs L1 48,892 tokens / $0.272604.

Failure mode:

- In trace-complete targeted audit, DR-v2 losses were mostly `selection_failure_present_not_selected`.

Decision:

- Do not rerun unchanged DR-v2 in this same setting. Improve selector first.

### 3.2 DR-v2 selection fix v1

Method ID:

- `direct_reserve_semantic_frontier_v2_selection_fix_v1`

What it does:

- Simple support-count/final-selection adjustment designed after present-not-selected diagnosis.

Important results:

- 20-case targeted run: tied original DR-v2 at 0.60 and lost to L1 at 0.70.
- Completed 100-case run: 0.55 vs original DR-v2 0.56 and L1 0.72.
- Paired W/T/L vs L1: 9 / 65 / 26.

Failure mode:

- Support-count override was too weak/simple and did not recover enough present-not-selected cases.

Decision:

- Do not repeat another plain support-only selector. Support count may be one feature inside a stronger verifier/reranker, but should not be the whole method.

### 3.3 Existing Cobbe-style diagnostics

Relevant files:

- `docs/COBBE_STYLE_OUTCOME_VERIFIER_DIAGNOSTIC.md`
- `scripts/run_cobbe_style_outcome_verifier_diagnostic.py`
- `docs/OUTCOME_VERIFIER_SELECTOR_DIAGNOSTIC.md`
- `scripts/run_outcome_verifier_selector_diagnostic.py`

What exists:

- Offline/diagnostic outcome-verifier-style selector analysis over existing candidates.
- Produces candidate solution rows, verifier/answer-bucket scores, selector summaries, and oracle-gap reports.

What does not exist yet:

- A validated live DR-v2 final-answer selector using answer-grouped outcome-verifier reranking.

Decision:

- This is the first paper-backed selector direction to operationalize.

## 4. Listed but not yet tested selector ideas

### 4.1 Answer-grouped outcome-verifier reranking

Proposed method ID:

- `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`

Paper basis:

- Cobbe et al., *Training Verifiers to Solve Math Word Problems*.

Repository reference:

- `docs/COBBE_STYLE_OUTCOME_VERIFIER_REFERENCE_20260429.md`

Core idea:

1. collect DR-v2 candidate traces and final answers;
2. normalize final answers;
3. group candidates by normalized answer;
4. score each candidate trace with an outcome verifier;
5. aggregate verifier scores inside answer groups;
6. select the best answer group.

Implementation status:

- Planned / being reimplemented after a conflicted branch.
- Should start with a deterministic/mock verifier and prompt builder.
- Live Cohere validation not yet done.

Why it is next:

- It directly targets DR-v2's current failure mode: correct answer present but not selected.

Success criteria:

- Improves over original DR-v2 and `selection_fix_v1`.
- Recovers present-not-selected cases without too many verifier regressions.
- Ideally narrows or reverses the gap to `external_l1_max`, but first goal is selector improvement, not broad dominance.

### 4.2 PRM-style step-level verifier reranking

Proposed method ID:

- `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1`

Paper basis:

- Lightman et al., *Let's Verify Step by Step*.
- PRM800K.
- Related: Math-Shepherd.

Repository reference:

- `docs/PRM_STEP_LEVEL_VERIFIER_SELECTOR_REFERENCE_20260429.md`

Core idea:

1. split candidate traces into reasoning steps;
2. score each step with a process verifier;
3. aggregate step scores into a trace score;
4. group traces by normalized final answer;
5. select by process-verifier answer-group score.

Implementation status:

- Proposed only.
- Existing PRM proxy branch-scoring infrastructure is not the same as a final-answer step-verifier selector.

Why it is second:

- Stronger and more diagnostic than outcome verification, but heavier and more expensive.
- Should come after outcome-verifier reranker unless outcome verifier clearly fails.

### 4.3 Math-Shepherd-style process verifier

Proposed method family:

- future `math_shepherd_step_selector` or `dr_v2_math_shepherd_process_rerank_v1`.

Paper basis:

- *Math-Shepherd: Verify and Reinforce LLMs Step-by-Step without Human Annotations*.

Implementation status:

- Not implemented.
- Not tested.

Why not first:

- Similar family to PRM but focuses on automatically constructed process labels; more complicated than a first selector fix.

### 4.4 LLM-as-judge final-answer verifier

Possible method family:

- `dr_v2_prompted_outcome_verifier_rerank_v1` if separated from the Cobbe-inspired version.

Status:

- Prompting can be the backend for v1 outcome verifier.
- Must be documented as a prompted approximation, not the exact trained Cobbe method.

Risks:

- bias toward long explanations;
- plausible-but-wrong reasoning;
- JSON instability;
- high token/cost overhead.

### 4.5 Bradley-Terry / tie-aware final-answer selector adaptation

Existing related code:

- `LearnedBTBranchScorer`
- `TieAwareBTBranchScorer`
- `RegimeGatedHybridBTBranchScorer`
- `TwoStageNearTieBTBranchScorer`

Status:

- Implemented as branch scorers/rankers, not as final answer-group selectors.

Possible future work:

- Adapt pairwise ranking to compare answer groups or traces at final commit time.

Priority:

- Lower than Cobbe-style outcome verifier and PRM step-verifier because it is less directly tied to correctness verification.

## 5. What a selector experiment must report

Every future selector experiment should report:

- overall accuracy;
- paired wins/ties/losses vs original DR-v2;
- paired wins/ties/losses vs `external_l1_max`;
- number of cases where correct answer was present anywhere in candidate pool;
- number of original present-not-selected failures;
- number recovered by new selector;
- number of regressions caused by new selector;
- verifier calls;
- verifier token/cost/latency overhead;
- whether support count helped or hurt;
- failure taxonomy after reranking.

## 6. Canonical selector test order

Do selector work in this order:

1. **Outcome-verifier rerank v1**
   - method: `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`
   - paper basis: Cobbe-style outcome verification
   - status: first to implement/test.

2. **PRM step-verifier rerank v1**
   - method: `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1`
   - paper basis: *Let's Verify Step by Step* / PRM800K
   - status: second to implement/test.

3. **Math-Shepherd-style process verifier**
   - status: later process-supervision variant.

4. **Pairwise/BT final-answer selector adaptation**
   - status: possible later ranking-model adaptation.

## 7. Do-not-repeat selector rules

- Do not retest original DR-v2 selector without a selector change.
- Do not retest `selection_fix_v1` as if it were new; it failed.
- Do not treat support count alone as a strong selector.
- Do not call prompted LLM verifier the exact Cobbe method; call it Cobbe-inspired.
- Do not call existing PRM partial branch scorers a final-answer PRM selector.
- Do not run 100-case API validation until module tests and method registration checks pass.

## 8. Immediate next action

Implement or reimplement cleanly:

- `experiments/answer_grouped_outcome_verifier.py`
- `tests/test_answer_grouped_outcome_verifier.py`
- live method registration if safe:
  - `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`

Then run a no-API registry validation before any Cohere chunks.

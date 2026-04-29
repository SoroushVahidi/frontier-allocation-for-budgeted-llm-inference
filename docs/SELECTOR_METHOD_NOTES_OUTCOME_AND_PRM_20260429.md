# Selector Method Notes: Outcome-Verifier Rerank and PRM Step-Verifier Rerank (2026-04-29)

## Purpose

This note records the two next paper-backed selector directions for DR-v2 final-answer selection. It is documentation only. It does not promote either selector to canonical claim-bearing status unless the corresponding method is implemented, registered as live-runnable, and validated on completed real-model experiments.

Current motivating failure mode:

- `direct_reserve_semantic_frontier_v2` (DR-v2) can discover the correct answer but fail to select it as final.
- Therefore, the next algorithmic priority is final-answer selection / reranking, not another unchanged broad API sweep.

Do not confuse these selector methods with candidate generation, budget allocation, or diagnostic-only methods such as `direct_reserve_semantic_frontier_v2_thresholded_ordered`.

---

## Method 1: Answer-Grouped Outcome-Verifier Rerank V1

### Proposed method ID

`direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`

### Paper basis

- Cobbe-style outcome verification: score complete candidate solutions and select/rerank by predicted correctness.
- Self-consistency-style answer grouping: normalize final answers and aggregate support across multiple traces producing the same answer.
- Verifier-weighted voting: combine answer-group support with candidate-level verifier scores rather than using raw majority vote or a single top trace.

### Core idea

Given candidate traces and final answers from DR-v2:

1. Extract candidate final answers.
2. Normalize/canonicalize answers.
3. Group candidates by normalized answer.
4. Score each full candidate solution with an outcome verifier.
5. Aggregate verifier-weighted scores within each answer group.
6. Select the highest-scoring answer group.
7. Surface the highest-scoring representative trace inside that group.

### Candidate-level scoring sketch

Let candidate `i` have:

- verifier probability `v_i`;
- optional source prior `source_prior_i`, default `0.5`;
- optional normalized cost/action penalty `cost_norm_i`, default `0`;
- consistency/error flags from verifier output.

A useful candidate score is:

```text
score_i = logit(clip(v_i)) + beta * logit(clip(source_prior_i)) - gamma * cost_norm_i
```

Additional conservative caps:

- if the verifier flags a major arithmetic/logical error, cap `v_i` at a low value;
- if the trace contradicts the final answer, cap `v_i` around uncertainty;
- if JSON parsing fails, use a conservative default such as `0.5` and log the parse failure.

### Answer-group scoring sketch

Let `G(a)` be all candidates with normalized final answer `a`.

Recommended group score:

```text
S(a) = tau * logsumexp(score_i / tau for i in capped_unique_source_candidates_in_G(a))
       + support_bonus * log(1 + |G(a)|)
```

Implementation details:

- cap duplicate support from the same source / branch family;
- keep support count as a feature, not the whole selector;
- choose the answer group first, then choose the representative trace within that group.

### Why this is first

This directly targets DR-v2's known present-not-selected failure mode. It is cheaper and simpler than full step-level process verification. It should be implemented and tested before PRM-style reranking.

### Required instrumentation

Every run of this selector should log:

- original DR-v2 selected answer;
- new selected answer;
- all normalized answer groups;
- candidate scores;
- group scores;
- verifier probabilities and flags;
- verifier parse failures;
- gold answer presence in candidate pool;
- recovered present-not-selected cases;
- regressions where original DR-v2 was correct but reranker changed to wrong;
- verifier calls/tokens/cost/latency.

### Validation requirement

Minimum meaningful validation:

- provider: Cohere;
- dataset: `openai/gsm8k`;
- budget: 4;
- seed: 11;
- target: 100 scored examples per method;
- compare against `external_l1_max`, original `direct_reserve_semantic_frontier_v2`, and `direct_reserve_semantic_frontier_v2_selection_fix_v1`.

Do not treat 10-case or incomplete chunk results as sufficient evidence.

---

## Method 2: PRM-Style Step-Verifier Rerank V1

### Proposed method ID

`direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1`

### Paper basis

- Lightman et al., *Let's Verify Step by Step* / PRM800K.
- Math-Shepherd-style automatic process supervision.
- Rewarding Progress / process advantage verifier ideas.
- Self-consistency-style answer grouping as the outer aggregation layer.

### Core idea

Instead of scoring only the complete candidate solution, score each reasoning step conditioned on the problem and previous reasoning prefix. Aggregate step scores into a trace score, then aggregate trace scores over normalized answer groups.

Pipeline:

1. Extract candidate final answers.
2. Normalize answers.
3. Split each trace into reasoning steps.
4. Score each step using a process/verifier prompt.
5. Aggregate step scores into a trace score.
6. Group traces by normalized final answer.
7. Aggregate trace scores per answer group.
8. Select the best answer group and representative trace.

### Step scoring abstraction

For trace `i` and step `t`:

```text
p_i_t = P(step t is valid/useful | problem, previous steps, current step)
```

A progress-aware API verifier can return both:

- `validity_score`: whether the step is mathematically/logically valid;
- `progress_score`: whether the step moves the solution toward a correct answer.

This is closer to process reward / process advantage verification than a simple global trace judgment.

### Step segmentation guidance

Use a robust heuristic before any API scoring:

1. split on numbered steps when available;
2. otherwise split on line breaks;
3. otherwise split on markers such as `First`, `Next`, `Therefore`, `Thus`, `Hence`, `So`;
4. keep algebra transformation blocks coherent;
5. merge fragments that are too short to be meaningful.

A step should represent one inferential move. Too-coarse steps hide errors; too-fine steps increase cost and noise.

### Trace-score formulas

For step scores `p_i_t`:

Mean score:

```text
mean_i = average_t p_i_t
```

Minimum score:

```text
min_i = min_t p_i_t
```

Recommended lightweight hybrid:

```text
q_i = lambda * mean_i + (1 - lambda) * min_i
```

with `lambda` around `0.6` to `0.8`.

If progress scores `g_i_t` are available:

```text
u_i = 0.7 * q_i + 0.3 * average_t g_i_t
```

If an outcome-verifier score `v_i` is also available, a later hybrid can use:

```text
u_i = beta * v_i + (1 - beta) * q_i
```

### Answer-group aggregation

Let `G(a)` be all traces with normalized answer `a`.

Start with:

```text
S(a) = sum_{i in G(a)} u_i
```

Alternative conservative variant:

```text
S(a) = max_{i in G(a)} u_i + gamma * sum_{other i in G(a)} u_i
```

This combines process-verifier trace quality with self-consistency-style answer support.

### Why this is second

PRM-style scoring is more diagnostically powerful than outcome-only scoring, but it is also more expensive and more implementation-sensitive. It should follow the outcome-verifier reranker unless there is strong evidence that the outcome verifier cannot distinguish polished wrong traces.

### Cost-control strategy

Do not score every step of every trace blindly.

Recommended staged approach:

1. Use answer normalization and cheap group/support features first.
2. Shortlist top answer groups or top candidate traces.
3. Step-score only shortlisted candidates.
4. Stop early if a trace falls below a conservative threshold.
5. Cache repeated prefixes where possible.
6. Consider one final outcome-verifier pass only for finalists.

### Required instrumentation

Every PRM-style run should log:

- step segmentation output;
- step-level validity/progress scores;
- trace-level score components;
- answer-group scores;
- disagreement between majority vote, outcome-verifier choice, and PRM-style choice;
- cost/token/latency overhead;
- regressions caused by noisy step scoring;
- whether low min-step scores correspond to actual fatal errors.

---

## Canonical implementation order

1. Implement/test/live-register `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`.
2. Run a completed 100-case Cohere diagnostic against original DR-v2 and `external_l1_max`.
3. Only then implement/test `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1` if outcome-level verification does not recover enough present-not-selected losses.

---

## Do-not-repeat rules

- Do not rerun original DR-v2 without a selector change.
- Do not rerun `selection_fix_v1` as if it were new.
- Do not implement another pure support-count selector.
- Do not claim prompted verifier equals the exact trained Cobbe verifier; call it Cobbe-inspired or outcome-verifier-inspired.
- Do not call existing branch-level PRM/BT scorers a final-answer selector unless adapted to answer groups.
- Do not claim improvement over `external_l1_max` unless completed paired evidence supports it.

---

## Recommended report template for either selector

A selector result report should include:

- exact command(s);
- provider/model/dataset/budget/seed;
- method list;
- scored rows per method;
- accuracy table;
- paired W/T/L versus original DR-v2;
- paired W/T/L versus `external_l1_max`;
- present-not-selected recovery table;
- regression table;
- verifier call/token/cost/latency table;
- final failure taxonomy;
- claim-safety status: canonical, diagnostic, or not claim-safe.

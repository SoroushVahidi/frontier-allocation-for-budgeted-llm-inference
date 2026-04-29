# Selector Method Notes: Pairwise / Bradley-Terry Answer-Group Rerank (2026-04-29)

## Purpose

This note records the third paper-backed selector direction for DR-v2 final-answer selection: pairwise comparison and Bradley-Terry-style answer-group reranking.

This is documentation only. It does not promote the method to canonical or claim-bearing status unless it is implemented, registered as live-runnable, and validated on completed real-model experiments.

Current selector sequence:

1. `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`
2. `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1`
3. `direct_reserve_semantic_frontier_v2_pairwise_bt_answer_group_rerank_v1`

Pairwise / BT reranking should come after the outcome-verifier and PRM-style selectors because it is less directly tied to mathematical correctness verification, but it may help when absolute verifier scores are poorly calibrated.

---

## Proposed method ID

`direct_reserve_semantic_frontier_v2_pairwise_bt_answer_group_rerank_v1`

Optional shorter internal alias:

`dr_v2_pairwise_bt_rerank_v1`

---

## Paper / method basis

This method is based on:

- Bradley-Terry pairwise preference aggregation;
- Elo-style online ranking;
- Plackett-Luce/listwise ranking as a possible later extension;
- pairwise reward models;
- LLM-as-judge pairwise comparison;
- RankGPT/listwise or pairwise reranking prompts;
- tournament / knockout reranking to reduce comparison cost;
- self-consistency-style answer grouping as the outer aggregation layer.

Main motivation:

Absolute verifier scores can be unstable or poorly calibrated, while pairwise judgments may be easier for an LLM judge: given two candidate solutions, choose which is more likely correct.

---

## Core idea

Given DR-v2 candidate traces and final answers:

1. Extract final answers.
2. Normalize/canonicalize final answers.
3. Group candidates by normalized answer.
4. Pick one or a few representative traces per answer group.
5. Compare answer groups pairwise using an LLM judge or pairwise reward model.
6. Aggregate noisy pairwise wins with Bradley-Terry, Elo, or soft win-rate.
7. Select the best answer group.
8. Surface the strongest representative trace from that group.

Important: compare **answer groups**, not all raw traces, to avoid unnecessary cost and vote-splitting.

---

## Bradley-Terry formulation

Each answer group `a` receives a latent strength `theta_a`.

For two answer groups `a` and `b`:

```text
P(a beats b) = exp(theta_a) / (exp(theta_a) + exp(theta_b))
             = sigmoid(theta_a - theta_b)
```

Given observed pairwise outcomes, fit `theta` by maximizing the Bradley-Terry likelihood.

If `n_ab` is the number of times group `a` beats group `b`:

```text
L(theta) = sum_{a != b} n_ab * log(sigmoid(theta_a - theta_b))
```

Then select:

```text
selected_answer_group = argmax_a theta_a
```

For judge confidence or soft probabilities, use weighted BT:

```text
L(theta) = sum_{a != b} w_ab * n_ab * log(sigmoid(theta_a - theta_b))
```

where `w_ab` is confidence or match weight.

---

## Simpler alternatives

### Soft win-rate

If the judge returns `p_ab = P(a beats b)`, use:

```text
W(a) = sum_{b != a} p_ab
```

Select the answer group with largest `W(a)`.

This is easier to debug than fitting BT and is a reasonable first baseline.

### Elo-style online update

Initialize all groups with equal rating. For each match `a` vs `b`:

```text
E_a = 1 / (1 + 10^((R_b - R_a) / 400))
R_a <- R_a + K * (S_a - E_a)
```

where `S_a` is 1, 0, or a soft probability in [0, 1].

Elo is useful for tournament schedules and early stopping, but BT is cleaner for a completed batch of comparisons.

### Support + BT hybrid

To combine answer support with pairwise ranking:

```text
S(a) = alpha * log(1 + |G(a)|) + (1 - alpha) * theta_a
```

This is useful when pairwise comparison coverage is sparse or noisy.

---

## Pairwise judging prompt requirements

For each comparison, provide:

- original problem;
- candidate answer group A final answer;
- representative trace(s) for group A;
- candidate answer group B final answer;
- representative trace(s) for group B;
- instruction to judge mathematical correctness, not style;
- instruction not to prefer longer or more polished traces unless they are more correct;
- instruction to return structured JSON.

Recommended JSON fields:

```json
{
  "winner": "A" | "B" | "tie" | "both_wrong" | "uncertain",
  "confidence": 0.0,
  "a_correct_probability": 0.0,
  "b_correct_probability": 0.0,
  "short_reason": "...",
  "first_error_if_any": "..."
}
```

Randomize A/B order or run swapped comparisons to reduce position bias.

---

## Representative selection

Do not compare every trace against every trace.

For each answer group, choose one or two representatives by:

- highest existing DR-v2/source score if available;
- shortest coherent trace;
- direct-path trace if available;
- highest cheap verifier score if available;
- non-duplicate branch family.

If a comparison is close, optionally rerun with alternate representatives.

---

## Cost-control schedule

A full round-robin among `K` answer groups costs `O(K^2)` comparisons. This can be too expensive.

Recommended staged schedule:

1. Normalize answers and form groups.
2. Compute cheap group priors:

```text
q(a) = log(1 + |G(a)|) + lambda * max_i cheap_score_i
```

3. Keep top 3-4 answer groups.
4. Run pairwise comparisons only among shortlisted groups.
5. Use soft win-rate or BT to rank groups.
6. Stop early if one group has a large win-rate/Elo/BT margin.

Tournament options:

- single elimination: cheapest but risky;
- double elimination: more robust;
- Swiss-style: good tradeoff when there are many groups;
- top-two final rematch with swapped A/B order: useful for position-bias mitigation.

---

## Known failure modes

### Position bias

LLM judges may prefer candidate A or B depending on prompt order.

Mitigation:

- randomize order;
- run both orders for close matches;
- average swapped outputs.

### Non-transitivity / cycles

Pairwise outcomes may form cycles such as `a > b`, `b > c`, `c > a`.

Mitigation:

- fit BT rather than relying only on raw tournament order;
- report cycle count or inconsistency diagnostics;
- use additional comparisons among top groups if the ranking is unstable.

### Verbosity / polish bias

Judges may prefer longer or more fluent traces.

Mitigation:

- explicitly instruct correctness over style;
- compare normalized/extracted solution skeletons when possible;
- truncate traces to comparable length.

### Shared wrong reasoning

If many traces share the same wrong shortcut, group support and pairwise comparison may still amplify the wrong answer.

Mitigation:

- use branch-family caps;
- compare multiple representatives;
- combine with outcome or step verifier signals.

### Sparse comparison graph

BT and PL ranking are unstable if the comparison graph is disconnected or too sparse.

Mitigation:

- ensure top groups are connected by comparisons;
- use priors/support as fallback;
- log when ranking confidence is low.

---

## Instrumentation requirements

Any implementation of `direct_reserve_semantic_frontier_v2_pairwise_bt_answer_group_rerank_v1` should log:

- all normalized answer groups;
- group sizes;
- representative trace IDs;
- cheap group priors;
- pairwise comparison schedule;
- randomized A/B ordering;
- raw judge JSON;
- parsed winner/confidence/probabilities;
- comparison matrix;
- BT/Elo/soft-win scores;
- selected answer group;
- selected representative trace;
- original DR-v2 selected answer;
- whether the gold answer was present in the candidate pool;
- whether a present-not-selected failure was recovered;
- regressions versus original DR-v2;
- verifier/judge calls, tokens, cost, latency;
- cycle / inconsistency diagnostics if available.

---

## Validation requirement

Do not run broad expensive validation until module tests and method-registration checks pass.

Minimum local tests:

- answer grouping;
- representative selection;
- deterministic mock pairwise judge;
- soft win-rate aggregation;
- BT fitting or approximation;
- position-bias swap handling;
- cycle handling;
- support + BT hybrid scoring;
- prompt safety: no gold/reference answer leakage;
- recovery of a mock present-not-selected case.

Minimum real-model diagnostic after implementation:

- provider: Cohere;
- dataset: `openai/gsm8k`;
- budget: 4;
- seed: 11;
- target: 100 scored examples per method;
- methods:
  - `external_l1_max`;
  - `direct_reserve_semantic_frontier_v2`;
  - `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1` if available;
  - `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1` if available;
  - `direct_reserve_semantic_frontier_v2_pairwise_bt_answer_group_rerank_v1`.

Report accuracy, paired wins/ties/losses, recovery/regression counts, and cost overhead.

---

## When to use this selector

Use pairwise / BT reranking if:

- outcome-verifier scores are poorly calibrated;
- the verifier often gives similar absolute scores to different answers;
- there are only a few answer groups after normalization;
- pairwise judgments appear more stable than pointwise scores;
- cost can be controlled with group-level tournament pruning.

Do not use it first if the simpler outcome-verifier answer-group reranker is not yet implemented or tested.

---

## Claim-safety rule

This method should be treated as proposed/diagnostic until a completed real-model run shows improvement. Do not claim it beats `external_l1_max` or solves DR-v2 selection failures without completed paired evidence.

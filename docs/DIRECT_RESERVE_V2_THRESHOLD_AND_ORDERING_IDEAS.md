# Direct-reserve v2: thresholding and branch-ordering ideas

This note records the current design ideas for reducing the cost of the real-LLM diagnostic controller while trying to preserve the accuracy gains of `direct_reserve_semantic_frontier_v1`.

## Motivation

Real-Cohere diagnostics suggest that the original `strict_f3` frontier controller is weaker than `external_l1_max`, while `direct_reserve_semantic_frontier_v1` is much stronger but expensive. The main bottleneck is therefore not only accuracy; it is cost efficiency. The next variant should keep the direct-reserve benefit while reducing unnecessary branch expansion.

The core tension is:

> Full early coverage protects against missing the correct reasoning region, but assessing all branches/families to depth 2 or 3 is expensive. Reducing coverage saves cost, but can miss a needed region.

The intended solution is **uncertainty-adaptive semantic coverage**: spend broad/deep frontier budget only when the direct incumbent is uncertain or when shallow challenger families look genuinely useful.

## Two-threshold control

The controller should use two different thresholds.

### 1. Continuation threshold

This decides whether a branch or semantic family deserves more compute after the shallow scan.

A family should be continued only if its continuation value exceeds a threshold:

```text
continuation_value = quality + novelty + challenge_value - redundancy - cost
```

Possible ingredients:

- parseability of the branch answer;
- non-empty candidate answer;
- use of relevant quantities from the question;
- operation type consistent with the question;
- semantic novelty relative to other families;
- answer-distinctness relative to the direct incumbent;
- shallow support from multiple branches;
- verifier-lite or self-evaluation score, if available;
- estimated cost of continuing the family.

Important safeguard:

> Do not threshold all challenger families away unless the direct incumbent is strong. If the incumbent is uncertain, keep at least one answer-distinct or strategy-distinct challenger alive.

### 2. Commit threshold

This decides whether the controller should stop and return an answer.

A final answer should be accepted only if its quality clears a commit threshold:

```text
answer_quality >= commit_threshold
```

Possible ingredients:

- parseable final answer;
- answer stability across direct samples, if available;
- high answer support;
- low answer entropy;
- large top-2 support gap;
- weak or redundant challengers;
- lightweight verifier/consistency check, if available.

The commit threshold should be adaptive:

- with high remaining budget, require stronger evidence before early commit;
- near budget exhaustion, accept weaker evidence;
- if the direct incumbent is strong and challengers are weak, commit early;
- if answer groups disagree, spend one more challenger action if budget remains.

## Depth-aware branch ordering

Branch order should depend on the depth/stage of the search. The same ordering rule should not be used for all layers.

### Stage 0: direct incumbent

Start with a direct or L1-style incumbent answer. This protects coherent direct reasoning, which appears important in real Cohere diagnostics.

Log:

- `incumbent_raw`;
- `incumbent_canonical`;
- `incumbent_parseable`;
- `incumbent_confidence_proxy`;
- `direct_actions_used`;
- token/cost/latency proxy if available.

### Layer 1: semantic setup diversity

At the first branch layer, ordering should prioritize semantic novelty rather than local score alone.

Goal:

> Seed distinct reasoning regions, not many paraphrases of the same region.

Possible setup families:

- equation/setup;
- direct arithmetic;
- working backward;
- ratio/rate reasoning;
- constraint checking;
- estimation then verification;
- science-choice elimination or planning-specific families when applicable.

Ordering principle:

```text
prefer non-redundant setup families before redundant variants
```

### Layers 2--3: uncertainty-adjusted maturation

After shallow setup generation, the controller should not automatically mature every root branch. It should rank semantic families by continuation value and mature only the most useful families.

A practical rule:

```text
if incumbent is strong:
    mature 0--1 challenger families
elif incumbent is moderate/uncertain:
    mature top 1--2 challenger families
else:
    mature top 2--3 challenger families
```

This replaces fixed full depth-2/depth-3 coverage with adaptive coverage.

Family ranking should consider:

- branch/family quality;
- semantic distinctness;
- challenge value against the incumbent;
- answer support;
- answer entropy or disagreement;
- redundancy;
- remaining budget.

### After layer 3: exploitative ordering

After enough maturation, the controller should shift from exploration to exploitation.

Ordering should prioritize:

1. the best supported answer group;
2. the strongest challenger to the incumbent;
3. the branch with highest verifier/proxy/process score, if available;
4. the branch most likely to break a tie between top answer groups.

Late-stage diversity should have lower weight. Do not keep opening new reasoning regions late unless the answer distribution remains unstable.

## Candidate v2 policy

A simple candidate controller is:

```text
1. Generate direct incumbent.
2. If incumbent quality >= high_commit_threshold:
       return incumbent.
3. Generate shallow challenger setups.
4. Cluster setups into semantic families.
5. Rank families by continuation_value.
6. Mature only the top k families, where k depends on incumbent uncertainty.
7. After limited challenge, compare:
       direct incumbent,
       top frontier challenger,
       best answer-distinct challenger.
8. Replace incumbent only if challenger evidence exceeds replacement_threshold.
9. Otherwise return incumbent.
```

The value of `k` should be uncertainty-adaptive:

- `k = 0` or `1` when incumbent is strong;
- `k = 1` or `2` when incumbent is moderate;
- `k = 2` or `3` when incumbent is weak or direct samples disagree.

## Replacement rule

The incumbent should be difficult to replace. A challenger can replace it only when at least one condition holds:

- incumbent is empty/unparseable and challenger is parseable;
- challenger has strictly higher answer support and parseability;
- challenger is supported by at least two distinct semantic families;
- lightweight verifier/reranker selects the challenger;
- challenger resolves a clear inconsistency in the incumbent.

Otherwise, keep the incumbent.

## What to log

For every v2 run, log:

- `route_decision`: `stop_with_incumbent`, `one_more_direct_continuation`, or `limited_frontier_challenge`;
- `route_reason`;
- `incumbent_parseable`;
- `incumbent_confidence_proxy`;
- `frontier_opened`;
- `direct_actions_used`;
- `frontier_actions_used`;
- `semantic_family_count`;
- `family_redundancy_ratio`;
- `families_matured_count`;
- `continuation_threshold`;
- `commit_threshold`;
- `replacement_threshold`;
- `top_challenger_answer`;
- `top_challenger_support`;
- `final_source`: `incumbent`, `challenger`, or `fallback`;
- `incumbent_replacement_reason`;
- `actions_used`;
- token/cost/latency proxy;
- correctness and failure taxonomy post hoc.

## Evaluation questions

The next evaluation should answer:

1. Does v2 preserve most of v1 accuracy?
2. Does v2 reduce actions/cost vs v1?
3. Does v2 still beat `strict_f3`?
4. Does v2 approach or beat `external_l1_max`?
5. Is v2 Pareto-better than v1?
6. Is v2 Pareto-better than `strict_f3`?
7. Is v2 Pareto-better than `external_l1_max`?
8. Does thresholding prune useful branches too aggressively?
9. Which route decisions dominate?
10. Where do regressions occur relative to v1?

## Claim boundary

This is a diagnostic design note. These ideas should not change manuscript claims unless validated by larger, independently selected real-provider runs and duplicate-aware analysis.

The expected manuscript-safe framing, if validated, is:

> Real-provider diagnostics suggest that direct-incumbent protection is useful, but fixed broad frontier coverage is costly. Uncertainty-adaptive semantic coverage is a promising way to reduce unnecessary expansion while preserving most of the accuracy gain.

# Latest status after recent passes (2026-04-18)

## Purpose

This note records the shortest current repository-facing update after the most recent bounded method, observability, objective, comparison, and broad-method confirmation passes.

It is intended to answer:
- what the newest experiments changed,
- what they did **not** change,
- what the current bottleneck now looks like,
- and what should happen next.

## Short current answer

The shortest honest update is:

- the repository moved beyond the earlier local target/oracle-refinement phase,
- a **broad diversity/aggregation family** is now the leading serious method family,
- that family held up in stricter simulator confirmation and survived bounded real-model confirmation as a plausible contender,
- but the current evidence is still not paper-grade because real-model scale remains too small and the exact best broad variant is not yet fully settled.

In practical terms:

> the repo is now in a **method hardening and realism-confirmation phase**, not a broad method-search phase.

## What the recent passes changed

### 1. Earlier local target/control refinements
Status:
- integrated and evaluated.

What happened:
- discounted multistep, compute-response curves, rank-instability supervision, and instability-to-decision coupling did **not** produce a broad successor to the multistep line.

Interpretation:
- local nearby refinements were useful diagnostics,
- but not the final broad method answer.

### 2. Branch observability and semantic diagnosis
Status:
- implemented and then used in fresh real runs.

What happened:
- the repository can now preserve branch text, reasoning text, recoverable answers, provenance, and semantic-diagnosis metadata on fresh runs,
- enabling real casebooks of method failures rather than only proxy-level diagnosis.

Interpretation:
- semantic failure analysis is now a first-class repository capability.

### 3. Oracle mismatch and completion-aware studies
Status:
- implemented and evaluated.

What happened:
- continuation value remained a strong core signal,
- completion-aware signals were real and useful,
- but bounded completion-aware correction alone was not enough to become the broad best method.

Interpretation:
- completion-aware logic matters,
- but only as part of a stronger broader controller story.

### 4. Intermediate-result failure fix
Status:
- implemented and evaluated.

What happened:
- targeted robustness improved on the intended failure slice,
- but this remained a local fix rather than a global replacement.

Interpretation:
- semantic incompleteness is real,
- but local correction alone is not enough for broad dominance.

### 5. Self-consistency advantage casebook
Status:
- implemented and analyzed.

What happened:
- self-consistency’s broad advantage was explained mainly by:
  - broader search/diversity,
  - answer aggregation,
  - reduced premature commitment.

Interpretation:
- the broad competitor problem was not mainly a local oracle tweak problem;
- it was a diversity/aggregation problem.

### 6. Bounded selective self-consistency hybrid
Status:
- implemented and evaluated.

What happened:
- local SC-inspired rescue improved hard-state proxy behavior,
- but did not materially close the broad gap to self-consistency.

Interpretation:
- local hard-case rescue was directionally useful,
- but still too weak.

### 7. Global broad diversity/aggregation family
Status:
- implemented and evaluated.

What happened:
- a broader diversity-aware allocation family with answer-support aggregation was introduced as a main-policy family,
- and this was the first repo pass where a branch-allocation method behaved like a serious broad competitor.

Interpretation:
- the repo’s central method direction changed here.

### 8. Stricter simulator confirmation of the broad family
Status:
- implemented and evaluated.

What happened:
- `broad_diversity_aggregation_strong_v1` became the main tracked candidate,
- and the family held up under stricter simulator confirmation,
- with broad improvement distributed across datasets rather than concentrated in one place.

Interpretation:
- this family is not a light-run fluke in simulator mode.

### 9. Bounded real-model confirmation
Status:
- implemented with real provider-backed runs.

What happened:
- the broad diversity/aggregation family survived contact with real models as a serious contender,
- but the real-model slice remained very small,
- and exact variant leadership became unstable (`v1` topped the tiny bounded real slice while `strong_v1` remained the main simulator-backed candidate).

Interpretation:
- the family still looks promising under realism,
- but real-model evidence is still too small for paper-grade confidence.

## What these results collectively now mean

The current repository-backed interpretation is:

- the project’s broad method answer is no longer likely to come from another local target/oracle tweak,
- the leading direction is now the **broad diversity/aggregation family**,
- the main tracked candidate is currently `broad_diversity_aggregation_strong_v1`, with `broad_diversity_aggregation_v1` as the main ablation/context sibling,
- and the next high-value work is realism confirmation and family hardening, not new-family search.

## Updated bottleneck statement

A stronger current bottleneck statement is:

> **The repository is currently bottlenecked by reliable diversity realization, ranking/aggregation quality after diversity exists, and real-model confirmation scale.**

More concretely:
- diversity still often fails to materialize enough,
- ranking can still be wrong even when diversity exists,
- aggregation can still concentrate on the wrong answer cluster,
- and real-model confirmation remains too small to support final paper-grade claims.

## What should happen next

### Best immediate next step
Do **not** open a new method family.

Instead:
- keep the broad diversity/aggregation family as the main line,
- freeze the current candidate pair (`strong_v1` main tracked candidate, `v1` ablation/context sibling) unless larger real runs reverse the choice,
- and run larger but still cost-controlled **real-model confirmation** to determine:
  - whether the family truly holds up,
  - which exact broad variant is best,
  - and what still breaks under real generation noise.

### Current recommended stance
The current bounded evidence supports this stance:

> **treat broad diversity-aware allocation with answer-support aggregation as the current main method family, and prioritize stronger Cohere/Gemini realism confirmation plus diversity-realization hardening over new-family search.**

### What should not be the default next move
Do **not** make the next main step:
- another local target-weighting tweak,
- another generic defer-policy sweep,
- another bounded hard-case rescue without broader family implications,
- another unrelated controller family,
- or another simulator-only campaign that postpones realism confirmation.

These may still matter later, but they are no longer the highest-leverage default move.

## Best single-sentence summary

> The repository has now moved into a stronger method-confirmation phase: a broad diversity/aggregation family is the leading serious method direction, it held up in stricter simulator confirmation and survived bounded real-model contact, and the current bottleneck is no longer “find another family,” but “make diversity reliably materialize and confirm the family at larger real-model scale.”

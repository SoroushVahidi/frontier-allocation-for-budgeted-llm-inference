# Research and execution log (2026-04-18)

## Purpose

This note records the main research, implementation, validation, and recovery steps that have already happened in the current project so they do not need to be rediscovered.

It is intentionally compact and should be updated when a new bounded pass materially changes the project interpretation.

## Current project phase

The project is no longer in the “find a topic” phase.
It is in the “decide among strong current ideas” phase.

## High-level progression

### Phase 1: project reframing
- Moved from the old binary revise-routing story to fixed-budget next-step branch allocation.
- Established frontier allocation / branch-priority framing as the canonical story.

### Phase 2: stronger supervision infrastructure
- Built brute-force / near-brute-force label generation.
- Added exact-vs-approx audits and target-fidelity regime analysis.
- Added hard-region mining and exact-promotion tooling.

### Phase 3: hard-case method refinement
- Improved hard-case feature representation.
- Developed tie-aware and defer-aware controller variants.
- Evaluated near-tie routing and specialist pointwise fallback variants.

### Phase 4: target-design research push
- Consolidated literature takeaways around selective marginal allocation, value-style targets, uncertainty-aware compare/defer, and structured ambiguity.
- Recorded these directions in dedicated research-takeaway notes.

### Phase 5: branch-level value + uncertainty execution
- Added bounded branch-value + uncertainty + derived compare/defer pass.
- Added stricter bounded validation with ablations.
- Identified canonical replay blocker due to missing regime artifacts.
- Rebuilt upstream artifacts and canonical targets root.
- Re-ran strict validation on rebuilt canonical root.

## Main research conclusions already recorded

### 1. The bottleneck is semantic, not infrastructural
The current bottleneck is supervision target quality and selective ambiguity handling, not lack of experiments or code.

### 2. Hard ambiguous pairs are important and real
Near-ties and disagreement cases are not well represented by forced binary winner labels alone.

### 3. Value-style supervision is a serious candidate direction
Branch-level value plus uncertainty and derived compare/defer decisions now form one of the strongest next target-design directions.

### 4. Defer is useful, but not the final answer
The repo should not treat abstention as “never decide.” It should treat defer as an intermediate control action on the way to a better final decision.

## Important implementation milestones already completed

### Implemented and worth keeping
- frontier-allocation framing
- anti-collapse design
- pairwise branch comparison baseline line
- brute-force / near-brute-force labels
- exact-vs-approx audits
- hard-case feature improvements
- tie-aware post-hoc deferral
- penalized marginal target direction
- branch-level value + uncertainty + derived compare/defer line

### Implemented but mixed / bounded
- ternary selective abstention
- ambiguity calibration + fallback
- near-tie routing policies
- learned two-stage deferral
- Cohere bounded comparison passes

### Implemented and currently weak / not the right fix
- deferred-only specialist training
- model-class changes alone as the main fix

## Important validation / recovery outcomes already completed

### Branch-value + uncertainty bounded strict validation
- showed strong accepted-accuracy gains over brittle pairwise and value-only forced baselines on stronger bounded proxy regimes
- but was still only a mixed bounded line due to hard-slice caveats and missing canonical replay in the checkout

### Canonical recovery + rebuild
- diagnosed the exact missing upstream artifact chain
- rebuilt a manifest-backed canonical targets root
- enabled real strict replay on a rebuilt canonical root

### Canonical replay result
- replay now succeeds
- method shows strong accepted accuracy when it acts
- but defer rate is very high
- near-tie accepted accuracy remains poor

## Main current status after those steps

The branch-value + uncertainty line is now:

> **a serious continuation line, but currently over-deferring and still weak on near-ties.**

That is stronger than “interesting bounded idea,” but weaker than “new canonical winner.”

## Important things already decided

- We should not keep searching for many new ideas before deciding the strong current ones.
- We should first properly evaluate the serious target-design lines already on the table.
- Canonical replay and robustness matter more now than more brainstorming.

## Main things not yet decided

- whether the branch-value + uncertainty line remains strong as rebuilt support size grows,
- whether high defer is mainly a small-support effect or a structural rule weakness,
- whether direct signed pairwise gap supervision adds value beyond branch-level value targets,
- how best to redesign mixed-fidelity supervision,
- whether partial-order / unresolved supervision should become a primary training object.

## Exact current next-step logic

1. continue deciding the current branch-value + uncertainty line,
2. continue deciding penalized marginal target refinement,
3. improve mixed-fidelity supervision design,
4. only after that, promote or reject secondary ideas such as direct signed pairwise gap or partial-order primary supervision.

## Safe summary

A safe summary is:

> The repository already contains the main serious ideas needed for progress. The right next work is to decide and refine the strongest implemented target-design lines, not to repeatedly rediscover new ideas that have not yet displaced them.

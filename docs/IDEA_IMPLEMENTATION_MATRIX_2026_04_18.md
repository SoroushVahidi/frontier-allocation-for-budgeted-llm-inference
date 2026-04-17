# Idea implementation matrix (2026-04-18)

## Purpose

This note records the main method and target-design ideas that have been proposed for the current project, and classifies them as:
- implemented,
- partly implemented,
- not yet implemented,
- promising,
- mixed,
- weak,
- or currently blocked.

The goal is to avoid repeating the same idea-discovery work and to make it obvious what has already been tried.

## Main rule

The repository is no longer short on ideas.

The main discipline now should be:
1. identify whether an idea is already implemented,
2. identify whether it has been properly evaluated,
3. identify whether it is blocked by artifacts or by method weakness,
4. and only then decide whether it deserves more work.

## High-level project lesson

The current bottleneck is not lack of experiments or infrastructure.

The current bottleneck is:

> **supervision target quality / selective ambiguity handling for next-step branch allocation.**

## Idea matrix

### 1. Fixed-budget frontier allocation / next-step branch allocation framing
- **Status:** implemented
- **Strength:** strong / useful
- **Interpretation:** canonical project identity
- **Priority:** keep as the default framing

### 2. Anti-collapse controller design
- **Status:** implemented
- **Strength:** strong / useful
- **Interpretation:** core mechanism and evaluation layer
- **Priority:** keep

### 3. Pairwise branch comparison as main learned object
- **Status:** implemented
- **Strength:** strong / useful
- **Interpretation:** current strong baseline/default learned object, but not necessarily final target semantics
- **Priority:** keep as anchor baseline

### 4. Stronger model class alone (GBDT/tabular upgrades)
- **Status:** implemented
- **Strength:** mixed / bounded
- **Interpretation:** useful comparison family, but not the primary next fix
- **Priority:** low

### 5. Brute-force / near-brute-force label generation
- **Status:** implemented
- **Strength:** strong / useful
- **Interpretation:** key infrastructure for higher-fidelity supervision and audits
- **Priority:** keep

### 6. Exact-vs-approx audits and target-fidelity regime analysis
- **Status:** implemented
- **Strength:** strong / useful
- **Interpretation:** canonical diagnostic layer
- **Priority:** keep

### 7. Hard-region exact promotion
- **Status:** implemented
- **Strength:** mixed / bounded
- **Interpretation:** useful for high-value relabeling and localization, but not a full fix by itself
- **Priority:** medium support layer

### 8. Hard-case feature representation improvements
- **Status:** implemented
- **Strength:** strong / useful
- **Interpretation:** materially helps difficult slices in the current scaffold
- **Priority:** keep

### 9. Ternary / selective-abstention formulations
- **Status:** implemented
- **Strength:** mixed / bounded
- **Interpretation:** important evidence that ambiguity is real, but not a closed solution
- **Priority:** medium

### 10. Ambiguity calibration + fallback
- **Status:** implemented
- **Strength:** mixed / bounded
- **Interpretation:** useful control layer, not the core bottleneck fix
- **Priority:** medium

### 11. Dedicated near-tie routing policies
- **Status:** implemented
- **Strength:** mixed / bounded
- **Interpretation:** useful hard-case lever, but gains are not fully robust
- **Priority:** medium-low

### 12. Near-tie specialized pointwise fallback
- **Status:** implemented
- **Strength:** promising but mixed
- **Interpretation:** part of the current strongest scaffold, but not solved enough to overclaim
- **Priority:** medium-high within current scaffold

### 13. Tie-aware post-hoc deferral
- **Status:** implemented
- **Strength:** strong / useful
- **Interpretation:** current strongest ambiguity-handling scaffold
- **Priority:** keep as current default ambiguity layer

### 14. Deferred-only specialist training
- **Status:** implemented
- **Strength:** weak / not the right fix
- **Interpretation:** negative result; do not treat as main next direction
- **Priority:** very low

### 15. Learned two-stage deferral
- **Status:** implemented
- **Strength:** promising but mixed
- **Interpretation:** active but non-default line; currently not stronger than tie-aware post-hoc deferral
- **Priority:** medium-low

### 16. Penalized marginal left/right/defer targets
- **Status:** implemented
- **Strength:** promising but not closed
- **Interpretation:** one of the strongest current target-design directions; important semantic improvement, but defer calibration remains unresolved
- **Priority:** high

### 17. Cohere bounded passes / external adjudication-style helpers
- **Status:** implemented
- **Strength:** mixed / bounded
- **Interpretation:** adjunct comparison line, not canonical bottleneck solution
- **Priority:** low-medium

### 18. Branch-level value + uncertainty + derived compare/defer
- **Status:** implemented in bounded and canonical-replayable form
- **Strength:** serious continuation line, but still mixed because it currently over-defers and remains weak on near-ties
- **Interpretation:** one of the most important current method lines
- **Priority:** very high

### 19. Direct signed pairwise gap supervision (“how much A is better than B” as the main target)
- **Status:** not yet fully implemented as the main supervised object
- **Current proxy:** partly represented indirectly through branch-level value prediction and derived value gaps
- **Interpretation:** still a real open target-design idea
- **Priority:** high, but after deciding the branch-level value line properly

### 20. Fully principled mixed exact/approx supervision redesign
- **Status:** partly implemented in ingredients, not fully implemented as a unified main training design
- **Ingredients present:** provenance, exact-vs-approx audits, selective relabeling ideas
- **Interpretation:** likely very important for the true bottleneck
- **Priority:** very high

### 21. Partial-order / unresolved supervision as the main training object
- **Status:** not yet fully implemented as the main line
- **Interpretation:** strong idea for hard near-ties and structured ambiguity, but not yet closed as the main method path
- **Priority:** medium-high

### 22. Hybrid listwise / frontier-level supervision as the main object
- **Status:** not yet fully implemented as the canonical line
- **Interpretation:** conceptually strong and well aligned with the true action, but currently less immediate than resolving the strongest existing lines
- **Priority:** medium

### 23. Canonical replay of branch-value + uncertainty line
- **Status:** now implemented through rebuilt canonical root and strict replay path
- **Interpretation:** no longer blocked by missing canonical regime root construction; current issue is method behavior, not replay availability
- **Priority:** keep using for fair continuation decisions

## Current strongest scaffold

The current strongest scaffold remains:

> **pairwise default + tie-aware post-hoc deferral + specialist pointwise fallback**

## Current strongest next target-design direction

The strongest next target-design direction remains:

> **budget-conditioned branch-level value or penalized marginal continuation value with explicit uncertainty and explicit derive-compare/defer behavior.**

## Recommended current priority order

### Tier 1: highest priority
1. branch-level value + uncertainty + derived compare/defer continuation
2. penalized marginal target refinement
3. mixed-fidelity supervision redesign
4. robust canonical validation and robustness passes on the current value-target line

### Tier 2: strong next ideas after current lines are decided
5. direct signed pairwise gap supervision
6. partial-order / unresolved supervision

### Tier 3: useful but later
7. hybrid listwise / frontier-level supervision
8. broader external comparison passes

### Tier 4: low current priority
9. more broad model-class sweeps
10. more deferred-only specialist variants
11. broad controller proliferation without target-design improvement

## Safe summary

A safe repository-facing summary is:

> The repository already contains many serious ideas and experiments. The highest-value remaining work is to decide the strongest current target-design lines—especially branch-level value plus uncertainty, penalized marginal targets, and better mixed-fidelity supervision—before searching for many new ideas.

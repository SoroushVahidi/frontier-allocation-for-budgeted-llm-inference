# Targeted failure bundle report (20260420T183801Z)

## Selected mechanism family
- **Family:** `near-miss absent-from-tree (post-improvement unresolved)`
- **Mechanism label:** `near_miss_absent_from_tree_unresolved`
- **Selected cases:** 7

## Why this family is strongest and most homogeneous
- It has the largest unresolved count among clean single-mechanism families considered from the same 20-case surface.
- 6/7 selected cases reach full budget; all show high repeated same-family expansion counts (min=6).
- This isolates one controller-allocation mechanism (family monopolization under bounded budget), rather than mixing mechanism types by answer-surface label.
- Most cases are near misses numerically, which is consistent with local search progress without adequate challenger coverage.

## Candidate family comparison (same artifacts)
- `present-but-not-selected (post-improvement unresolved)`: 2 cases
- `near-miss absent-from-tree (post-improvement unresolved)`: 7 cases
- `full-budget repeated same-family monopolization (post-improvement unresolved)`: 8 cases

## Why this bundle is a better target for the next bounded fix
- The previous broad 20-case slice mixes absent-from-tree and present-but-not-selected mechanisms.
- This targeted slice removes present-but-not-selected cases and keeps one dominant mechanism only.
- A single bounded controller fix can focus on anti-monopolization plus challenger diversification under fixed budget.

## Suggested next bounded controller improvement
- Add a **family-cap with near-miss escape hatch**: when a family consumes most actions and produces near-miss numeric answers without gold match, reserve remaining actions for forced challenger families before continuing depth on incumbent family.
- Keep boundedness by limiting forced challenger actions to a small fixed quota and only triggering under explicit monotonic near-miss + monopolization conditions.

## Output bundle
- `outputs/targeted_failure_bundle_20260420T183801Z`

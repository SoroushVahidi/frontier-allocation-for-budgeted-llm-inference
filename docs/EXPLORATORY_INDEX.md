# Exploratory index

This page groups active but non-canonical lines so they are easier to find without competing with the main project interpretation.

## What counts as exploratory

Exploratory material is useful and often important, but it is **not** the default summary of the repository.

These materials usually fall into one of these categories:
- method variants that are still being tested,
- diagnostics that support a narrower question,
- targeted ambiguity / near-tie / tie-aware experiments,
- warm-start, reliability-aware, or alternative scorer lines,
- one-off status notes that are not yet canonical.

## Main exploratory method clusters

### Branch-scorer variants
- pairwise BT variants,
- reliability-aware BT variants,
- tie-aware / Rao-Kupper lines,
- external warm-start variants,
- ambiguous-pair targeted experiments.

### Ambiguity / near-tie handling
- abstention and ternary branch comparison,
- ambiguity calibration and fallback policy studies,
- dedicated near-tie routing,
- near-tie pointwise expert lines,
- stricter coupled near-tie controller refinements.

### Oracle-label and supervision-fidelity work
- brute-force label generation,
- hard-region mining and exact promotion,
- target-regime construction,
- feature-representation audits,
- supervision-fidelity comparisons.

## How to use exploratory notes

Use exploratory material when:
- you need the provenance for a specific experiment line,
- you are deciding which active variant should be promoted next,
- or you are writing a bounded method-status note.

Do **not** use exploratory notes as the first summary of the whole repository.

## Recommended reading order for exploratory work

1. [`CURRENT_PROJECT_STATUS.md`](CURRENT_PROJECT_STATUS.md)
2. [`CURRENT_BOTTLENECKS.md`](CURRENT_BOTTLENECKS.md)
3. Then whichever cluster is relevant:
   - supervision fidelity,
   - feature representation,
   - ambiguity handling,
   - near-tie expert routing,
   - external baseline integration.

## Neighbor pages

- [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
- [`README.md`](README.md)
- [`HISTORICAL_AND_ARCHIVE_POLICY.md`](HISTORICAL_AND_ARCHIVE_POLICY.md)
- [`REPO_MAP.md`](REPO_MAP.md)

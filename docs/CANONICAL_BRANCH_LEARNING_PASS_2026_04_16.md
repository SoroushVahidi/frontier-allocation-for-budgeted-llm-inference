# Canonical branch-learning pass status (2026-04-16)

This is a conservative matched learning pass using the canonical processed corpus layer.

## Corpus used

- Canonical corpus: `outputs/branch_learning_corpora/real_branch_learning_corpus_20260416_v1`
- Source build path used in this pass: merged real runs + exact-reference promotion target regimes + canonical corpus builder.

## Methods compared (matched)

- `baseline::pairwise`
- `baseline::pointwise`
- `baseline::outside_option`
- `reweighted::pairwise`
- `reweighted::pointwise`
- `reweighted::outside_option`
- `heuristic_score_only`
- `heuristic_score_minus_uncertainty`

Compared families:
- learned pairwise logistic (baseline + hard-case reweighted)
- learned pointwise ridge (baseline + hard-case reweighted)
- learned outside-option logistic helper (baseline + hard-case reweighted)
- simple deterministic heuristics (`score`, `score - uncertainty`)

## Aggregate ranking (test pairwise accuracy)

| Model | Pairwise acc | Pairwise n | Top1 acc | Near-tie acc | Near-tie n |
|---|---:|---:|---:|---:|---:|
| heuristic_score_only | 0.6667 | 9 | 0.3333 | 0.0000 | 1 |
| heuristic_score_minus_uncertainty | 0.6667 | 9 | 0.3333 | 0.0000 | 1 |
| baseline::pointwise | 0.5556 | 9 | 0.3333 | 1.0000 | 1 |
| baseline::outside_option | 0.5556 | 9 | 0.3333 | 1.0000 | 1 |
| reweighted::pointwise | 0.5556 | 9 | 0.3333 | 1.0000 | 1 |
| reweighted::outside_option | 0.5556 | 9 | 0.3333 | 1.0000 | 1 |
| reweighted::pairwise | 0.3333 | 9 | 0.0000 | 0.0000 | 1 |
| baseline::pairwise | 0.2222 | 9 | 0.0000 | 0.0000 | 1 |

## Hard-slice highlights (paper-safe interpretation)

- Near-tie test coverage exists but is very small in this run (`n=1` per model); this is not enough for strong near-tie reliability claims.
- Adjacent-rank and small-margin slices are present and are now first-class in machine-readable outputs.
- Exact-promoted slice had zero test rows in this deterministic split for this run; exact-promoted behavior is therefore unresolved in held-out test for this pass.
- Exact-vs-approx provenance remained explicit; this test split happened to be exact-only for pairwise rows in this run configuration.

## What improved vs prior state

1. Canonical processed-corpus entry point is now used end-to-end for training/evaluation.
2. Matched model comparison is reproducible from one canonical summary JSON report.
3. Hard-slice, dataset-slice, budget-slice, and branch-count slices are first-class in outputs.

## What remains unresolved

1. Hardest-slice reliability is still not solved (especially near-tie and exact-promoted held-out behavior).
2. The core bottleneck remains supervision-target fidelity / proxy-label mismatch, not pipeline wiring.
3. This pass improves readiness/diagnostics more than it proves robust learning gains.

## Recommended next method pass

- Keep canonical corpus path fixed, then run a larger matched corpus with explicit test coverage targets for near-tie and exact-promoted slices (before changing model families).
- Evaluate one targeted supervision-quality intervention (e.g., higher exact-promoted coverage or hard-case-balanced sampling) with identical split/metrics protocol.
- Continue conservative claims: readiness improved, hard-case bottleneck still open.

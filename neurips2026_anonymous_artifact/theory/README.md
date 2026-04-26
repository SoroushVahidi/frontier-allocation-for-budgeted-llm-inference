# Theory

This directory contains formal models, proof sketches, lemmas, and theoretical notes for the project.

> **Placeholder — content will be added as the research develops.**

---

## Planned Content

- **Formal model** of the budget allocation problem over a reasoning tree.
- **Baseline analysis**: uniform allocation, best-of-N, greedy depth-first search.
- **Adaptive policy**: formal description and analysis.
- **Noise model**: assumptions on the distribution of value estimation errors.
- **Main theorem(s)**: success probability bounds, regret analysis, or sample complexity.
- **Connections**: reduction to or comparison with multi-armed bandit / best-arm identification problems.

---

## File Organization (Planned)

```
theory/
├── README.md               # This file
├── model.md                # Formal problem setup and notation
├── baselines.md            # Analysis of baseline policies
├── adaptive_policy.md      # Proposed adaptive allocation policy
└── proofs/                 # Detailed proof sketches and drafts
```

---

## Notes

- Use LaTeX math in markdown where needed (rendered in most editors).
- Keep proof sketches even if incomplete — partial results are useful for tracking progress.
- Tag each result with its status: `[Conjecture]`, `[Sketch]`, or `[Proven]`.

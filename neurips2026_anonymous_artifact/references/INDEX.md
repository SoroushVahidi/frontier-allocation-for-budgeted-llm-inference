# References Index

This file is the current entry point for the repository's organized reference layer.

It complements the older `references/README.md` plan by providing a live structure that is already populated.

## Current reference files

- `references/references.bib` — working BibTeX file for the project
- `references/REFERENCE_TRACKER.md` — project-facing tracker for how each paper relates to the method
- `references/papers/` — per-paper notes for the most important comparison targets and methodological references

## Most important current groups

### Must-compare external baselines
- s1: Simple test-time scaling
- L1: Controlling How Long A Reasoning Model Thinks With Reinforcement Learning
- Token-Budget-Aware LLM Reasoning (TALE)

### Strong partial-match external baselines
- Learning How Hard to Think: Input-Adaptive Allocation of LM Computation
- BEST-Route: Adaptive LLM Routing with Test-Time Optimal Compute

### Methodology-shaping references
- Let’s Verify Step by Step
- AutoPSV
- Distilling Effective Supervision From Severe Label Noise
- The Selective Labels Problem

## Practical rule

For each important paper, the repository should ideally have:
1. a BibTeX entry in `references/references.bib`
2. one row in `references/REFERENCE_TRACKER.md`
3. one note file under `references/papers/` if the paper is a major baseline or major methodological influence

## Why this exists

The goal is not only citation management.
The goal is also to track:
- how each paper helped the project,
- whether we should compare directly against it,
- whether it is a source of ideas rather than a direct baseline,
- and what caveats matter for fair comparison.

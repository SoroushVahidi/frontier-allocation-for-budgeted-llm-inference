# AutoPSV (2024) — Automated Process-Supervised Verifier

**Paper:** https://arxiv.org/abs/2405.16802

## Summary
AutoPSV is an important methodological reference for automated process labeling and confidence-change based supervision. It is especially relevant to our oracle-label trust and local action-value interpretation.

## Why it matters to this project
- It supports the idea that local process quality can be inferred from confidence dynamics rather than only from final correctness.
- It helps justify state-local quality signals and auditing logic.
- It informs how we think about accepted versus risky supervision regions.

## How it relates to our method
- **Directness:** methodological idea source
- **Main contribution to our project:** local process quality, confidence-change interpretation, and selective trust of labels.

## What we should use from it
- local-step or local-state quality reasoning
- thresholded trust logic
- caution that not all automatically generated labels are equally reliable

## Current repo status
- Reference tracked
- BibTeX tracked
- Important methodology note for oracle-label trust and local supervision

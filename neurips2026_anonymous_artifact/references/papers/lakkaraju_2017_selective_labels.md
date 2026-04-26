# Lakkaraju et al. (2017) — The Selective Labels Problem

**Paper:** https://cs.stanford.edu/~jure/pubs/contraction-kdd17.pdf

## Summary
This paper is a key methodological reference for evaluation under selective observation. It is important because it warns that naive evaluation on observed labels can be biased when the act of making decisions changes which labels become visible.

## Why it matters to this project
- It strongly supports matched-rate or matched-intervention evaluation instead of naive comparisons.
- It helps justify why our oracle-distilled controller should be evaluated at matched ACT rates and with strong controls.
- It shaped our caution around filtered-vs-unfiltered evaluation.

## How it relates to our method
- **Directness:** methodological idea source
- **Main contribution to our project:** careful policy evaluation under selective observation and matched-rate thinking.

## What we should use from it
- matched intervention-rate comparisons
- caution against naive observed-label evaluation
- stronger control logic for selective filtering studies

## Current repo status
- Reference tracked
- BibTeX tracked
- Important methodology note for evaluation design

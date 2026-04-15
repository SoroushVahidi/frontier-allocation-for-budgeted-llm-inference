# Lightman et al. (2023) — Let’s Verify Step by Step

**Paper:** https://arxiv.org/abs/2305.20050

## Summary
This is one of the most important process-supervision references for the project. It is not a direct external baseline for our controller, but it strongly shaped how we think about step-level supervision, same-data/different-supervision comparisons, and label-efficiency considerations.

## Why it matters to this project
- It supports process supervision as a serious alternative to coarse outcome-only supervision.
- It motivates comparing supervision types on the same underlying data rather than only comparing top-line model outputs.
- It reinforces the value of focused labeling rather than uniform expensive labeling.

## How it relates to our method
- **Directness:** methodological idea source
- **Main contribution to our project:** shaped how we think about oracle labels, supervision fidelity, and evaluation of different supervision sources.

## What we should use from it
- same-state-pool supervision comparisons
- caution against relying only on aggregate top-line metrics
- active or targeted labeling logic

## Current repo status
- Reference tracked
- BibTeX tracked
- Important methodology note for supervision and evaluation design

# Learning How Hard to Think (2024) — Input-Adaptive Allocation of LM Computation

**Venue:** arXiv preprint (2024)  
**Paper:** https://arxiv.org/abs/2410.04707

## Summary
This paper is a strong conceptual predecessor for learned compute allocation under a fixed budget. It studies how to estimate the marginal value of additional computation and allocate compute adaptively rather than uniformly.

## Why it matters to this project
- It is one of the clearest conceptual precedents for learned adaptive compute allocation.
- It supports our broader framing that budgeted test-time compute can be allocated intelligently rather than spent uniformly.

## How it relates to our method
- **Directness:** partial external baseline
- **What overlaps:** learned allocation of compute under a budget
- **What differs:** the paper is more cross-query / allocation oriented and not centered on a sequential stop-vs-act frontier controller within one reasoning trace.

## What we should do with it
- Use it as a strong broader-context baseline and framing reference.
- Compare carefully if we can emulate a matched fixed-budget allocation setting.
- Do not present it as a perfectly direct stop-vs-act baseline.

## Key caveat
It is conceptually strong but less directly apples-to-apples than s1, L1, or TALE.

## Current repo status
- Reference tracked
- BibTeX tracked
- Broader adaptive-allocation baseline target

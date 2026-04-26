# L1 (2025) — Controlling How Long A Reasoning Model Thinks With Reinforcement Learning

**Venue:** arXiv preprint (2025)  
**Paper:** https://arxiv.org/abs/2503.04697  
**Project page:** https://cmu-l3.github.io/l1/  
**Code:** https://github.com/cmu-l3/l1

## Summary
L1 is one of the closest methodological baselines for hard or soft budget control of reasoning length. It studies how a reasoning model can be trained to satisfy token-length constraints while preserving performance across different budgets.

## Why it matters to this project
- It is one of the strongest direct methodological comparison targets for a fixed-budget controller paper.
- It is highly relevant to our compute-allocation framing because it explicitly treats budget adherence as part of the method.

## How it relates to our method
- **Directness:** direct / near-direct external baseline
- **What overlaps:** budget-conditioned adaptation of reasoning effort
- **What differs:** L1 uses RL-trained length control, while our framing is currently more controller-centric and can be layered onto a reasoning setup rather than only trained into the model.

## What we should do with it
- Treat it as a **must-compare** baseline once external baselines are integrated.
- Compare at matched token/compute budgets.
- Report both quality and budget adherence rather than only final accuracy.

## Key caveat
This is not as cleanly venue-published as s1 in the material we have tracked, so it is a strong baseline but slightly weaker as a reviewer-credibility anchor than s1.

## Current repo status
- Reference tracked
- BibTeX tracked
- External baseline target
- Should likely be the second major external baseline integrated into the repo

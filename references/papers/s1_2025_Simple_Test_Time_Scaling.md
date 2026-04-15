# s1 (2025) — Simple test-time scaling

**Venue:** EMNLP 2025  
**Paper:** https://aclanthology.org/2025.emnlp-main.1025.pdf  
**arXiv:** https://arxiv.org/abs/2501.19393  
**Code:** https://github.com/simplescaling/s1

## Summary
s1 is one of the closest direct baselines for explicit test-time stopping/continuation control in reasoning models. The paper is especially relevant because its budget-forcing idea makes reasoning longer or shorter at inference time through simple intervention mechanisms rather than through a completely different task formulation.

## Why it matters to this project
- It is one of the strongest direct comparison targets for our stop-vs-act / budgeted reasoning story.
- It gives us a reviewer-recognizable stopping/control baseline.
- It is much closer to our method than generic routing or best-of-n papers.

## How it relates to our method
- **Directness:** direct / near-direct external baseline
- **What overlaps:** explicit control over reasoning length under a budget
- **What differs:** s1 combines model-side training choices with budget-forcing at inference, while our current method is framed more as a budget-conditioned controller / allocation policy.

## What we should do with it
- Treat it as a **must-compare** external baseline.
- Prefer a comparison at matched budgets or matched ACT/compute rates.
- Separate any same-model inference-only comparison from comparisons that involve extra post-training.

## Key caveat
A fair comparison needs to be explicit about whether we are comparing:
1. our controller against s1-style inference control on the same base model, or
2. our full method against an s1 model that has been adapted or post-trained.

## Current repo status
- Reference tracked
- BibTeX tracked
- External baseline target
- Should be among the first real paper baselines integrated into the repo

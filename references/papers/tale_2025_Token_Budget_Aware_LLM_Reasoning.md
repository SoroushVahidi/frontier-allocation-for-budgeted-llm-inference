# TALE (2025) — Token-Budget-Aware LLM Reasoning

**Venue:** Findings of ACL 2025  
**Paper:** https://aclanthology.org/2025.findings-acl.1274.pdf  
**arXiv:** https://arxiv.org/abs/2412.18547  
**Code:** https://github.com/GeniusHTX/TALE

## Summary
TALE is a strong per-instance budget-allocation baseline. It predicts or internalizes a token budget for a problem and then uses that budget to reduce redundant reasoning while preserving answer quality.

## Why it matters to this project
- It is one of the strongest published adaptive-budget baselines for reasoning.
- It is especially useful because it makes the claim that adaptive budget assignment can improve the quality/cost tradeoff.

## How it relates to our method
- **Directness:** partial but strong external baseline
- **What overlaps:** adaptive budget allocation under compute limits
- **What differs:** TALE is closer to per-instance budget prediction than to sequential stop-vs-act frontier control.

## What we should do with it
- Treat it as a **must-compare** published adaptive-budget baseline.
- Compare on matched average token cost or matched compute budget.
- Be explicit that TALE is a partial rather than perfectly direct comparison target.

## Key caveat
It is not a sequential frontier controller, so comparisons should not overclaim exact equivalence of the decision problem.

## Current repo status
- Reference tracked
- BibTeX tracked
- External baseline target
- Should likely be the third major external baseline integrated into the repo

# BEST-Route (2025) — Adaptive LLM Routing with Test-Time Optimal Compute

**Venue:** ICML 2025  
**Paper:** https://arxiv.org/abs/2506.22716  
**Code:** https://github.com/microsoft/best-route-llm

## Summary
BEST-Route is a strong adaptive-compute baseline that allocates test-time effort through routing and sampling decisions. It is especially relevant for the broader claim that learned allocation can beat uniform compute spending.

## Why it matters to this project
- It is a high-value broader adaptive-allocation baseline.
- It helps position our work against routing-style allocation methods, not only against stopping-control methods.

## How it relates to our method
- **Directness:** partial external baseline
- **What overlaps:** learned adaptive compute allocation under cost/quality tradeoffs
- **What differs:** BEST-Route is more routing- and portfolio-oriented than a single-trace stop-vs-act controller.

## What we should do with it
- Use it as a broader adaptive-allocation comparison if our experiments can support a fair setup.
- Be explicit about multi-model / routing caveats.

## Key caveat
This is not a clean apples-to-apples baseline unless our experimental design allows comparable routing or allocation flexibility.

## Current repo status
- Reference tracked
- BibTeX tracked
- Broader adaptive-allocation baseline target

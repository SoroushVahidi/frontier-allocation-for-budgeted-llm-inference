# Related-work positioning for NeurIPS 2026

## Problem formulation
This repository studies **adaptive test-time compute allocation under fixed budgets**. The central question is how to allocate limited inference-time compute across candidate branches/actions so total task accuracy improves under a hard budget contract.

## Budget units in prior work
Prior literature uses multiple budget units that are related but not identical:

1. **Action/query budget**
   - e.g., bounded LM query/search expansions in ToT-style search.
2. **Token budget**
   - e.g., TALE and SelfBudgeter style allocation/forcing of generation length.
3. **Verifier-call budget**
   - e.g., methods that decide when to spend verification on intermediate/final states.
4. **Latency/cost budget**
   - e.g., cost-aware or latency-constrained routing and policy learning.
5. **Model-routing/cascade budget**
   - e.g., route each query to model/prompt pipelines with hard spend constraints.

## Baseline families to cover
- Uniform budget allocation / fixed-width or fixed-depth allocation.
- Training-free difficulty-proxy allocation.
- Token-budget methods (TALE, SelfBudgeter).
- s1-style budget forcing.
- Self-consistency baselines.
- ToT/GoT/search baselines under fixed query/action budgets.
- Verifier-guided or intermediate-state allocation.
- Model/prompt routing and cascades (BEST-Route/TREACLE-style adjacent family).

## Where this repository fits
The repository’s strongest and safest framing is:
- **branch/frontier-level allocation**
- with **answer-group aggregation and anti-collapse controls**
- evaluated primarily under **matched action-budget accounting**
- with real-model and token/cost analyses treated as bounded supporting evidence.

## What this repository does NOT yet prove
- Universal superiority across providers, datasets, and budget units.
- Token/cost-normalized dominance across all comparator families.
- Robust real-model dominance over `external_l1_max`.
- Superiority over all official, full-stack implementations of token/routing/search systems.

## Safest NeurIPS positioning sentence
> A frontier-allocation formulation and diagnostic evaluation under matched action budgets, with real-model/cost-aware validation as supporting evidence.

## Literature anchors (verified links, conservative metadata)
- Adaptive Test-Time Compute Allocation for Reasoning LLMs via Constrained Policy Optimization (arXiv:2604.14853).
- Adaptive Test-Time Compute Allocation via Training-Free Difficulty Proxies (OpenReview ICLR 2026 submission).
- Adaptive Test-Time Compute Allocation via Learned Heuristics over Categorical Structure (arXiv:2602.03975).
- Token-Budget-Aware LLM Reasoning / TALE (arXiv:2412.18547; also ACL Findings 2025 version).
- s1: Simple test-time scaling (arXiv:2501.19393; also EMNLP 2025 version).
- SelfBudgeter: Adaptive Token Allocation for Efficient LLM Reasoning (arXiv:2505.11274; OpenReview version exists).
- Policy-Guided Search on Tree-of-Thoughts for Efficient Problem Solving with Bounded Language Model Queries (arXiv:2601.03606).
- Graph of Thoughts (arXiv:2308.09687).
- Efficient Contextual LLM Cascades through Budget-Constrained Policy Learning (arXiv:2404.13082; NeurIPS 2024).
- Policy Guided Tree Search for Enhanced LLM Reasoning (arXiv:2502.06813; venue metadata needs verification before bibliography promotion).

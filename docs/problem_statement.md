# Problem Statement

> **Draft version — formulation is under active development.**

---

## Background

Large language models can benefit significantly from additional compute at inference time. Techniques such as chain-of-thought prompting, tree-of-thought search, best-of-N sampling, and process reward models allow models to "think longer" before committing to an answer. However, these approaches are typically evaluated with a fixed or uncontrolled compute budget, and little attention is paid to *how* compute is distributed across the reasoning process.

When reasoning is structured as a tree or DAG of intermediate states, a natural question arises: how should a fixed budget of inference compute be allocated across those states?

---

## Motivation

In practice, reasoning systems must operate under resource constraints (latency, cost, memory). Naive allocation strategies — such as uniform allocation or greedy depth-first search — may waste compute on low-value branches while neglecting high-potential ones. Better allocation could improve answer quality without requiring more total compute.

A key difficulty is that value estimates for intermediate reasoning states are often noisy: a verifier or heuristic score may be misleading. Understanding how noise affects the optimal allocation strategy, and designing allocation policies that are robust to this noise, is a central challenge.

---

## Candidate Formalization

> *This formulation is a starting point. It will be refined as the research progresses.*

**Setting:**

- Let $\mathcal{T}$ be a reasoning tree (or graph) where each node $s$ represents a partial reasoning state.
- Let $B$ denote a fixed total inference budget (e.g., total tokens, number of model calls, or compute units).
- Let $\hat{v}(s)$ be a noisy local value estimate for node $s$, drawn from some distribution over the true value $v(s)$.
- Let $\pi: \mathcal{T} \times \mathbb{R}^{|\mathcal{T}|} \to \Delta(B)$ be an allocation policy that assigns compute to nodes given the tree structure and estimated values.

**Objective:**

Maximize the probability of reaching a correct final answer:

$$\max_{\pi} \; \Pr\left[\text{correct answer reached} \mid \pi, B, \hat{v}\right]$$

subject to the total budget constraint $\sum_{s} b_s \leq B$.

---

## Possible Objectives

The main objective above may be refined or replaced depending on the setting:

- **Maximizing probability of correctness**: Find at least one correct solution within budget.
- **Maximizing expected quality**: Optimize the expected quality of the best solution found.
- **Minimizing expected budget to correctness**: Find a correct solution as efficiently as possible.
- **Robustness to noise**: Maximize correctness under worst-case or stochastic value estimation error.

---

## Possible Assumptions

These assumptions are candidates; not all may be adopted in the final formulation:

- The reasoning tree is finite and known (or partially revealed as search proceeds).
- Value estimates $\hat{v}(s)$ are independent across nodes conditional on the true values.
- Noise in $\hat{v}(s)$ is bounded or sub-Gaussian.
- The budget $B$ is given in advance (non-adaptive) or observed incrementally (adaptive/online).
- Terminal nodes have binary or real-valued correctness labels.

---

## Open Design Choices

- **Tree vs. graph**: Should the reasoning structure be a tree or allow cycles/shared states?
- **Budget unit**: Tokens? Model calls? FLOPs? A unified abstraction?
- **Value function**: What model produces $\hat{v}(s)$? A trained verifier? A self-consistency score? A heuristic?
- **Online vs. offline**: Is the allocation computed before search begins, or updated adaptively during search?
- **Reduction to bandit problems**: Can this be framed as a stochastic bandit or best-arm identification problem?
- **Benchmark alignment**: How do we evaluate allocation strategies fairly (matched-budget comparisons)?

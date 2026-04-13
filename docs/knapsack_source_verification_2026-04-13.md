# Knapsack source-verification note (2026-04-13)

This note records a conservative verification pass over the classical multiple-choice knapsack and multidimensional knapsack literature so later manuscript writing can cite these results accurately without overclaiming.

## 1. Why this note matters

The knapsack family is useful for the project because it captures the **offline resource-allocation structure** of test-time compute budgeting. However, the classical knapsack papers do not directly model adaptive noisy sequential feedback. For that reason, they are best used as an **offline shadow problem** rather than the main adaptive theorem backbone.

## 2. Sinha & Zoltners (1979) — safest use

### Safest citation role
Use this paper as the main classical source for the **multiple-choice knapsack problem (MCKP)** definition and for an **exact branch-and-bound algorithm**.

### Safe claim
This paper formulates the multiple-choice knapsack problem and gives an exact branch-and-bound approach based on LP-relaxation ideas.

### What it is safest for
- canonical MCKP definition
- exact branch-and-bound solution method
- offline choice among grouped alternatives under a scalar budget

### Do not overclaim
Do not cite it as an approximation paper or as a source of adaptive guarantees.

## 3. Pisinger (1995) — safest use

### Safest citation role
Use this paper as the main classical source for a strong **exact algorithmic template** for MCKP.

### Safe claim
This paper provides a minimal/core-based exact algorithm for MCKP, using relaxation structure and dynamic-programming style reasoning around a reduced core.

### What it is safest for
- core-based exact algorithmic structure
- reduced offline allocation around a small critical region
- strong exact offline baseline inspiration

### Do not overclaim
Do not cite it as a heuristic-only method or as giving an approximation ratio.

## 4. MKP / MMKP references — safest use

### Safest citation role
Use standard multidimensional knapsack references for:
- the move from one resource dimension to multiple resource dimensions
- hardness context
- structural algorithms and exact/heuristic baselines

### Safe claim
Classical multidimensional knapsack and multiple-choice multidimensional knapsack literature provides the appropriate offline analogue when allocation must respect multiple resource dimensions such as compute, memory, or latency.

### What it is safest for
- NP-hardness / strong hardness context
- multi-resource offline allocation analogy
- exact and heuristic multi-dimensional baseline structure

### Do not overclaim
Do not claim these papers directly address adaptive branch allocation under noisy observations. They are offline allocation references.

## 5. Safest manuscript citation mapping

The current safest mapping is:

- **Canonical MCKP definition + exact branch-and-bound** -> Sinha & Zoltners (1979)
- **Strong exact/core-based MCKP algorithmic template** -> Pisinger (1995)
- **Multidimensional knapsack structure/hardness** -> standard MKP/MMKP references

## 6. Best current use for our project

The safest way to use knapsack-style references in the manuscript is:

1. as the offline deterministic shadow problem for budgeted compute allocation
2. as support for classical exact baseline ideas in the fully known offline case
3. as support for hardness claims about multi-resource offline allocation

They should **not** currently be used as the main adaptive theorem source.

## 7. Common overclaims to avoid

### 7.1 Confusing MCKP, MKP, and MMKP
These are related but distinct variants. The manuscript should clearly distinguish:
- MCKP: one scalar budget + multiple-choice groups
- MKP: multiple resource dimensions, typically without group structure
- MMKP: multiple resource dimensions + multiple-choice structure

### 7.2 Claiming approximation results from exact papers
Sinha & Zoltners and Pisinger should be cited as exact algorithmic references, not as approximation-ratio results.

### 7.3 Claiming adaptive relevance too strongly
Knapsack-style papers support the static allocation analogy, but not the sequential noisy branch-allocation problem directly.

### 7.4 Claiming polynomial-time optimality
These problems are hard in general, and the classical papers should not be described in a way that suggests easy polynomial-time optimal offline optimization.

## 8. Current judgment for the project

At the current stage, knapsack-style problems should be treated as:
- an **offline shadow problem**
- a strong modeling analogy for static compute allocation
- a useful source of exact baseline structure and hardness context
- not the main adaptive theorem backbone of the paper

## 9. Working manuscript sentence

A safe working sentence is:

> In the fully known offline setting, budgeted allocation across reasoning branches resembles a knapsack-style resource-allocation problem, especially when branch-level compute choices are treated as grouped alternatives or when multiple resource dimensions are tracked. Our main challenge, however, is the adaptive noisy setting, which goes beyond classical offline knapsack formulations.

## 10. Status

This note should be revisited later if the manuscript includes an explicit offline oracle baseline or a formal reduction to a knapsack-style allocation problem.
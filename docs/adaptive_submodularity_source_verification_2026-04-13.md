# Adaptive submodularity source-verification note (2026-04-13)

This note records a conservative verification pass over the classical adaptive submodularity literature so later manuscript writing can cite these results accurately without overclaiming.

## 1. Why this note matters

Adaptive submodularity is potentially relevant to the project because it offers elegant greedy-style guarantees for sequential information-gathering problems under uncertainty. However, it is also easy to overstate what the literature proves and how directly it applies to adaptive test-time compute allocation for LLM reasoning.

This note records the safest current interpretation.

## 2. Golovin & Krause (2011) — safest use

### Safest citation role
Use this paper as the main classical source for the **definition of adaptive submodularity** and for the **adaptive greedy approximation guarantee** under the appropriate structural assumptions.

### Safe claim
If the objective is adaptive monotone and adaptive submodular, then adaptive greedy achieves a (1 - 1/e) approximation under a cardinality-type constraint.

### What it is safest for
- formal adaptive-submodularity definition
- adaptive monotonicity definition
- adaptive greedy approximation guarantee
- the idea that adaptive diminishing returns can make myopic allocation provably good

### Do not overclaim
Do not claim that adaptive greedy is optimal. Do not claim that all adaptive information-gathering or LLM reasoning objectives are adaptive submodular.

## 3. Nemhauser, Wolsey, and Fisher (1978) — safest use

### Safest citation role
Use this paper as the main classical source for the **non-adaptive greedy approximation theorem** for monotone submodular maximization under a cardinality constraint.

### Safe claim
For monotone submodular set functions under a cardinality constraint, greedy achieves a (1 - 1/e) approximation.

### What it is safest for
- non-adaptive baseline theorem
- classical greedy approximation benchmark
- offline reference point for contrast with adaptive settings

### Do not overclaim
Do not use this paper as a source for adaptive guarantees. It is foundational for non-adaptive submodular maximization, not adaptive submodularity.

## 4. Budgeted / knapsack adaptive-submodular line — safest use

### Safest citation role
Use later adaptive-submodular extensions for the statement that **budgeted or knapsack-style adaptive constraints can still admit constant-factor greedy-style approximation guarantees**, under the right assumptions.

### Safe claim
There exist adaptive-submodular extensions under budgeted or knapsack-style constraints where adaptive greedy or thresholded variants achieve constant-factor approximations.

### What it is safest for
- cost-sensitive adaptive allocation analogy
- token / latency / verification-cost interpretations
- support for the claim that adaptive greedy remains meaningful under costs, although not necessarily with the same 1 - 1/e guarantee as the simple cardinality setting

### Do not overclaim
Do not claim the clean Golovin–Krause cardinality guarantee automatically transfers unchanged to budgeted LLM allocation.

## 5. Safest manuscript citation mapping

The current safest mapping is:

- **Definition of adaptive submodularity and adaptive greedy theorem** -> Golovin & Krause (2011)
- **Classical non-adaptive greedy benchmark** -> Nemhauser, Wolsey, and Fisher (1978)
- **Budgeted / cost-sensitive adaptive extensions** -> later adaptive-submodular knapsack-style work

## 6. Best current use for our project

The safest way to use adaptive submodularity in the manuscript is:

1. as a structural lens for when greedy allocation could be provably good
2. as a sufficient condition, not a default truth
3. as a secondary supporting analogy unless we can formally justify adaptive submodularity for our objective

## 7. Common overclaims to avoid

### 7.1 Claiming adaptive submodularity for our objective without proof
Adaptive submodularity should be stated as an assumption or candidate structural property unless it is actually established.

### 7.2 Treating adaptive greedy as optimal
The classical result is an approximation guarantee, not an optimality theorem.

### 7.3 Confusing adaptive and non-adaptive submodularity citations
Nemhauser et al. is a non-adaptive benchmark, while Golovin & Krause is the adaptive source.

### 7.4 Claiming budgeted guarantees are identical to the cardinality case
Cost-sensitive or knapsack-style adaptive guarantees typically require separate results and may have different constants.

## 8. Current judgment for the project

At the current stage, adaptive submodularity is best treated as:
- a **secondary supporting analogy**
- a useful theorem template if the right structural assumptions can be justified
- not yet the primary theorem backbone of the project

The primary backbone remains the local-to-global allocation-error theorem direction, with metareasoning / value-of-computation and fixed-budget identification playing more central roles.

## 9. Working manuscript sentence

A safe working sentence is:

> Adaptive submodularity offers one possible structural explanation for why myopic compute allocation could work: if the expected gain from additional computation exhibits adaptive diminishing returns, then adaptive greedy policies inherit classical approximation guarantees. In our setting, however, this should be viewed as a conditional lens rather than an assumption-free characterization.

## 10. Status

This note should be revisited later if the manuscript develops an explicit adaptive-submodularity assumption or if a toy theorem is proved under that condition.
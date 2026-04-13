# Safe manuscript claims note (2026-04-13)

This note records the safest current manuscript claims so later writing stays conservative and evidence-backed.

## 1. Claims that are currently safe

### 1.1 Problem framing
It is safe to claim that the project studies adaptive test-time compute allocation for LLM reasoning under a fixed budget.

### 1.2 Empirical bottleneck
It is safe to claim that branch ranking / branch scoring is the current central bottleneck in the pilot system.

### 1.3 Learned-scorer lesson
It is safe to claim that early experiments suggest static branch-promise targets are weaker than continuation-style targets for this problem setting.

### 1.4 Classical framing
It is safe to claim that the problem has meaningful connections to:
- metareasoning / value of computation
- fixed-budget best-arm identification
- knapsack-style offline allocation
- adaptive submodularity as a conditional structural lens

### 1.5 Theory direction
It is safe to claim that a natural theorem target is to relate local marginal-value estimation error or branch misranking error to global fixed-budget allocation loss.

## 2. Claims that are not yet safe

### 2.1 Strong controller superiority claims
It is not yet safe to claim that the learned controller or learned scorer clearly outperforms the strongest heuristic baselines in a stable way.

### 2.2 Exact counterfactual supervision claims
It is not yet safe to claim that the current continuation-style labels are true counterfactual marginal values.

### 2.3 Full real-world theorem claims
It is not yet safe to claim a theorem for the full realistic LLM branch-allocation setting with all interactions, verifier effects, and possible non-monotonicity.

### 2.4 Adaptive submodularity as fact
It is not yet safe to claim that the real project objective is adaptive submodular. At most, this can be presented as a possible structural assumption or theorem lens.

### 2.5 Knapsack as the main theorem backbone
It is not yet safe to present classical knapsack as the primary theorem foundation of the adaptive noisy problem. It is safer as an offline shadow problem.

## 3. Safe wording patterns

Prefer wording like:
- "suggests"
- "indicates"
- "motivates"
- "in a stylized model"
- "under the following assumptions"
- "conditional on"
- "can be viewed as"

Avoid wording like:
- "proves" when only intuition exists
- "optimal" when only approximation or analogy exists
- "solves" when the result is only partial or stylized
- "directly extends" when the connection is only conceptual

## 4. Best current manuscript posture

The safest current posture is:
- strong on problem framing
- strong on target-alignment lessons
- strong on careful classical positioning
- moderate on current empirical wins
- moderate to cautious on theorem strength until the first formal proof is completed

## 5. Working safe summary sentence

A good safe summary sentence is:

> Early results suggest that fixed-budget adaptive reasoning is better served by continuation-style local signals than by static branch-promise estimates, motivating a theory of how local branch-scoring error affects global allocation performance.

## 6. Status

This note should be updated whenever the empirical evidence strengthens enough to upgrade a currently unsafe claim into a safe one.
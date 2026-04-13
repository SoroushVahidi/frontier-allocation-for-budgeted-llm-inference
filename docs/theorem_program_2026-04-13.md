# Theorem program note (2026-04-13)

This note records the current theorem agenda for the project so later work can turn the high-level theory direction into a concrete manuscript proof program.

## 1. Main theorem target

The current leading theorem target is:

> **Local branch-scoring error or branch misranking error implies bounded global allocation regret (or bounded performance loss) under a fixed compute budget.**

This is currently the best theorem direction because it:
- matches the empirical bottleneck (branch ranking)
- connects the learned local target to the global objective
- fits both metareasoning and learning-augmented online-allocation framing
- is more robust than trying to prove full optimality of a highly realistic controller

## 2. Simplified first theorem model

A reasonable first theorem model is:

- there are multiple branches
- each branch has a marginal continuation-value curve
- compute is allocated one unit at a time
- marginal values are nonnegative and have diminishing returns within a branch
- an oracle greedy policy always chooses the highest true current marginal value
- the learned policy chooses the branch with highest predicted current marginal value

Under this model, the theorem goal is to bound the gap between:
- oracle greedy value
- predicted-greedy value

in terms of local estimation or ranking error.

## 3. Candidate positive theorem shapes

### 3.1 Additive estimation-error theorem

If the learned marginal-value estimates are uniformly accurate up to error epsilon at each decision point, then the global value of the learned greedy allocation should differ from oracle greedy by at most O(B epsilon), where B is the total budget.

This is the cleanest first positive theorem because:
- it is easy to state
- it matches the current continuation-value interpretation
- it creates a direct local-to-global bridge

### 3.2 Pairwise misranking theorem

If the probability of misranking the best available branch against a suboptimal branch is small, and the instantaneous gap between those branches is bounded, then expected global performance loss should scale with cumulative misranking error.

This theorem may fit the learned scorer especially well because the local problem is fundamentally ranking-based.

### 3.3 Approximate greedy under structural assumptions

If the objective can be modeled as monotone adaptive-submodular or approximately adaptive-submodular, then greedy or approximate greedy policies may inherit a classical approximation factor plus an additional learned-score error term.

This is elegant but currently more speculative because the structural assumption may be hard to justify in the full reasoning setting.

## 4. Candidate supporting negative results

### 4.1 Static branch-score failure example
Construct an instance where ranking branches by static promise or current score is arbitrarily worse than ranking by marginal continuation value.

This would support the empirical v1-to-v2 lesson and motivate continuation-style local targets.

### 4.2 Interaction / non-separability warning example
Construct a small example where branch interactions break naive separable assumptions, to clarify why the first theorem should be stated in a stylized model.

### 4.3 Overthinking / non-monotonicity warning example
Construct an example where additional compute is not always helpful, showing why diminishing-returns or monotonicity assumptions must be treated carefully.

## 5. Best current theorem hierarchy for the paper

### Main positive theorem
Local error or misranking implies bounded global loss under a simplified fixed-budget branch-allocation model.

### Main negative theorem or proposition
Static branch scoring can fail badly relative to marginal continuation-value-aware allocation.

### Optional structural theorem
If the objective satisfies an adaptive-submodular-style property, greedy allocation inherits a classical approximation factor.

## 6. Recommended proof order

1. Define the stylized allocation model.
2. Define true marginal continuation value.
3. Define the oracle greedy allocator.
4. Define the learned greedy allocator.
5. Prove an additive local-to-global bound.
6. Prove or state a pairwise misranking corollary.
7. Add a small negative example for static branch scores.
8. Only after that, explore stronger structural conditions such as adaptive submodularity.

## 7. Why this order is best

This order is recommended because it gives:
- a theorem that is closely tied to the learned scorer
- a clean empirical interpretation of local ranking metrics
- a realistic chance of a complete proof
- a contribution that still looks specific to budgeted adaptive LLM reasoning rather than just generic search

## 8. Relation to classical backbones

The theorem program currently combines several classical lenses:

- **Metareasoning / value of computation** -> clarifies the local quantity that should be estimated
- **Fixed-budget best-arm identification** -> clarifies the stochastic budgeted allocation viewpoint
- **Learning-augmented online allocation** -> suggests the desired local-error to global-performance theorem form
- **Knapsack** -> gives the offline deterministic shadow problem
- **Adaptive submodularity** -> possible conditional greedy-guarantee lens

## 9. Current risk assessment

### Lowest-risk theorem
Additive local-estimation-error implies O(B epsilon) global loss under separable diminishing-returns assumptions.

### Medium-risk theorem
Pairwise misranking implies bounded expected global loss.

### Highest-risk theorem
A full adaptive-submodular or realistic full-controller theorem for the actual LLM branch-allocation setting.

## 10. Working manuscript sentence

A useful sentence is:

> Our theory focuses on a local-to-global question: if a learned scorer only approximates the marginal value of computation for each branch, how does that local prediction error propagate into global fixed-budget allocation loss?

## 11. Status

This theorem program should guide future formal work. The priority is not to chase the strongest possible theorem immediately, but to prove the cleanest theorem that most directly matches the project's actual empirical bottleneck.
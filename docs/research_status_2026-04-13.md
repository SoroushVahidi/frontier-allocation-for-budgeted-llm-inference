# Research status memo (2026-04-13)

This note records the current project status so later manuscript work can quickly recover what has already been established, what remains uncertain, and what the next research bottlenecks are.

## 1. Current project identity

The project studies **adaptive test-time compute allocation for LLM reasoning under a fixed budget**.

The current best interpretation is:
- multiple partial reasoning branches compete for limited compute
- the central local problem is branch ranking / branch-action scoring
- the central global problem is maximizing final correctness under a hard budget

## 2. Current strongest contribution path

The strongest current path to a NeurIPS-style contribution is:
- learn a continuation-style local target rather than static branch promise
- analyze how local branch-scoring error propagates into global fixed-budget allocation loss
- frame the problem using metareasoning / value of computation and fixed-budget allocation ideas

## 3. Current empirical status

### Controller mechanics
The pilot controller infrastructure exists and can act. Earlier failure modes such as zero-expand collapse have already been identified and mitigated through simple safeguards.

### Learned scorer status
- v1 taught that static branch-promise supervision is too weak
- v2 moved toward continuation-style supervision and is conceptually closer to the right local object
- the main remaining gap is between approximate continuation labels and true counterfactual marginal value of one extra compute unit

### Main empirical bottleneck
The key bottleneck is now **target quality**, not basic infrastructure.

## 4. Current theory status

### Main theorem target
Local branch misranking or local marginal-value estimation error implies bounded global allocation regret or performance loss under a fixed budget.

### Current theorem priority
The best first theorem is a stylized local-to-global theorem under simplified assumptions such as:
- branch-separable marginal values
- diminishing returns within each branch
- one-unit-at-a-time budget allocation

### Supporting negative result
A useful accompanying negative result is a failure example showing that static branch scores can be much worse than marginal continuation-value-aware allocation.

## 5. Current classical backbone status

### Primary conceptual backbone
Metareasoning / value of computation.

### Primary stochastic backbone
Fixed-budget best-arm identification.

### Offline shadow problem
Knapsack-style resource allocation.

### Conditional structural lens
Adaptive submodularity.

## 6. Current citation discipline status

The repository now includes explicit source-verification notes so later manuscript writing can distinguish:
- what is formally proved
- what is a useful definition
- what is only conceptual framing
- what overclaims should be avoided

## 7. Main current risks

1. Overclaiming target quality from approximate continuation labels.
2. Overclaiming classical results that are only analogous, not directly applicable.
3. Letting the project drift into broad related-work search instead of sharpening the actual contribution.
4. Investing in model complexity before the local target is sufficiently aligned.

## 8. Best next research priorities

1. Improve or better justify continuation-value supervision.
2. Formalize the first stylized local-to-global theorem.
3. Strengthen controller-level evaluation with the current learned target.
4. Keep building manuscript-ready notes only when they materially support the contribution.

## 9. Working summary sentence

A good one-sentence summary of the current project state is:

> The project has moved beyond pilot-controller mechanics and is now centered on a more precise scientific question: how should a system estimate the marginal value of computation for competing reasoning branches, and how do errors in that local estimate affect global fixed-budget performance?

## 10. Status

This note should be updated when either:
- the theorem target changes materially, or
- the local learning target becomes substantially better aligned with true counterfactual compute value.
# Metareasoning and value-of-computation foundations note (2026-04-13)

This note records the most useful classical metareasoning ideas for the project so later manuscript writing can connect the work to older AI theory in a precise and honest way.

## 1. Why this note matters

Recent project discussions suggest that the local branch-scoring problem is better understood as a **metareasoning** problem than as a static branch-evaluation problem. The controller is not merely judging whether a branch looks good. It is deciding whether allocating one more unit of computation to a branch is worthwhile under a fixed global budget.

That is exactly the kind of question studied in classical work on **value of computation (VOC)** and **decision-theoretic control of computation**.

## 2. Core classical idea

The key classical idea is:

> A computation should be performed if its expected improvement in object-level decision quality exceeds its computational cost.

In our project, a computation may be:
- expanding a partial branch
- verifying a branch
- keeping a branch alive rather than pruning it
- spending one more unit of test-time compute on a branch-action pair

Therefore, the strongest current interpretation of the learned scorer is:

> The learned scorer estimates the **marginal value of computation** for a partial reasoning branch.

## 3. How VOC maps to the project

### Classical metareasoning object
A metareasoner asks: *which internal computation should be performed next?*

### Project version
Our controller asks: *which branch should receive the next unit of compute, and in what form?*

This yields the following mapping:

- object-level task -> produce a correct final answer
- internal computation -> expand / verify / continue a branch
- computation cost -> one unit of budget, latency, tokens, or verifier cost
- value of computation -> expected gain in final success probability from that extra compute

Under this view, the local learning target should not be a static branch score. It should approximate:

> expected marginal improvement from allocating one more unit of compute to this branch-action pair under the remaining budget

## 4. Why this helps manuscript framing

This metareasoning lens strengthens the paper in several ways.

### 4.1 Better local target language
Instead of saying the model predicts whether a branch is promising, the paper can say the controller estimates **marginal value of computation** or **marginal continuation value**.

### 4.2 Better problem definition
The paper can be framed as a modern instance of **rational metareasoning under transformer-based reasoning**, rather than only as heuristic tree search.

### 4.3 Better explanation of why v1 failed
A static promise-style target is naturally weaker than a VOC-style target because it ignores the question of whether one more unit of compute is worth spending on that branch now.

### 4.4 Better explanation of why v2 is directionally better
A continuation-style target is more aligned with the classical VOC question because it is closer to the marginal benefit of another compute step.

## 5. Connection to the theorem target

The current leading theorem target remains:

> local branch misranking or marginal continuation-value estimation error implies bounded global allocation regret

The metareasoning perspective improves this theorem target by clarifying what the local quantity should be:
- not static branch quality
- not raw verifier confidence alone
- but an estimate of the **marginal value of one more computation**

This is likely the cleanest bridge between classical AI theory and the current branch-allocation theorem direction.

## 6. Bounded optimality relevance

Classical bounded-optimality ideas are also useful here. They suggest that the correct oracle is not unrestricted perfect reasoning, but the best policy achievable under the same resource constraints.

For this project, that means a useful oracle concept is:

> the best adaptive compute-allocation policy under the same fixed budget

This is better than comparing to an unrealistic unconstrained oracle.

## 7. Important caution: metareasoning itself has a cost

A critical classical lesson is that metareasoning is not free. The controller itself consumes computation.

This matters for the project because:
- a more accurate scorer may require more overhead
- a richer controller may reduce budget available for object-level reasoning
- the best policy may be a cheap approximation rather than an expensive but accurate controller

This should be acknowledged explicitly in later manuscript writing.

## 8. Updated project interpretation

The strongest current interpretation of the project is:

> We study fixed-budget adaptive test-time compute allocation for LLM reasoning as a metareasoning problem. At each step, the system must decide which branch-action pair has the highest marginal value of computation, using imperfect local signals and operating under a hard global budget.

## 9. Relationship to other classical backbones

This note does not replace the other classical problem families. Instead, it clarifies their roles.

- **Metareasoning / VOC**: best conceptual and local-target backbone
- **Fixed-budget best-arm identification**: best stochastic online allocation backbone
- **Multiple-choice knapsack / MMKP**: best offline deterministic shadow problem
- **Adaptive submodularity**: possible structural lens for greedy-style guarantees

## 10. Working manuscript sentence

A useful manuscript sentence is:

> Our problem can be interpreted as rational metareasoning for LLM inference: under a fixed compute budget, the controller must repeatedly decide which internal computation has the highest marginal value of computation for improving the chance of a correct final answer.

## 11. Status

At the current stage, metareasoning / VOC should be treated as a first-class foundation of the project, not merely a side analogy. The empirical progression from static promise targets toward continuation-style targets is consistent with this interpretation.
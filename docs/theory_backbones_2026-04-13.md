# Theory backbones note (2026-04-13)

This note records the current theoretical framing for the project so later manuscript writing stays aligned with the strongest cross-over between theoretical computer science and modern LLM reasoning.

## 1. Core problem

The project studies **adaptive test-time compute allocation for LLM reasoning under a fixed budget**. The system maintains multiple partial reasoning branches and repeatedly decides which branch should receive the next unit of compute, such as an expansion, verification, or continued exploration step. The global objective is to maximize the probability of reaching a correct final answer under a hard compute budget.

## 2. Closest classical problem families

### 2.1 Fixed-budget best-arm identification

This is currently the strongest **stochastic online backbone** for the project. Each branch can be viewed as an arm whose quality is only partially revealed through additional computation. The controller has a fixed budget, receives noisy local evidence, and must allocate exploration effort so as to identify and refine the most promising branch.

Why it is useful:
- captures fixed-budget sequential allocation
- captures noisy local signals
- naturally supports misranking / identification-error style guarantees
- matches the repeated decision of where to invest one more unit of compute

### 2.2 Rational metareasoning / value of computation

This is currently the strongest **conceptual AI-theory backbone**. The key metareasoning question is: *what is the value of one more unit of computation on a partial reasoning state?* This maps almost directly onto our local branch-scoring problem.

Why it is useful:
- gives the right conceptual language for the learned scorer
- supports marginal continuation value rather than static branch quality
- frames the controller as a decision-theoretic compute allocator rather than only a search heuristic

### 2.3 Multiple-choice knapsack / multidimensional multiple-choice knapsack

This is best viewed as the **offline deterministic shadow problem**. If each branch had a known response curve for how much value additional compute yields, then global budget allocation across branches would resemble a knapsack-style allocation problem with branch-level choices.

Why it is useful:
- clarifies the combinatorial allocation structure
- supports offline oracle and upper-bound interpretations
- positions the adaptive problem as a noisy sequential generalization of a classic resource-allocation problem

Why it is not the main backbone:
- by itself it does not model noisy sequential feedback well
- it is better as an offline limit case than as the main theorem language

### 2.4 Adaptive submodularity

This is a promising **greedy-guarantee lens** if the utility of allocating compute satisfies an adaptive diminishing-returns property. It may allow elegant approximation-style guarantees for greedy allocation.

Why it is useful:
- potentially gives a clean greedy theorem
- connects the problem to adaptive information gathering
- naturally matches the idea that extra compute may have diminishing marginal benefit

Why it is risky:
- it is not yet clear that reasoning-branch utility in our setting satisfies adaptive submodularity
- it should be treated as a candidate structural assumption, not yet as a confirmed project foundation

## 3. Current theorem target

The current leading theorem target is:

> **Local branch misranking or marginal continuation-value estimation error implies bounded global allocation regret under a fixed compute budget.**

This is the most promising theorem direction because:
- it directly connects the learned scorer to the global system objective
- it fits the current empirical bottleneck, which is branch ranking
- it aligns with the learned-scorer pipeline already being developed
- it is more robust and manuscript-friendly than relying only on a pure greedy-optimality statement

A likely simplified first theorem model would assume:
- branch-separable marginal value curves
- diminishing returns within each branch
- one-unit-at-a-time budget allocation
- greedy choice based on predicted marginal continuation value

Then the theorem would show that if the scorer approximates or preserves the ranking of true marginal branch values well enough, the resulting adaptive allocator stays close to an oracle allocator.

## 4. Paper-shape implication

### Primary classical backbone
Fixed-budget best-arm identification.

### Secondary conceptual backbone
Rational metareasoning / value of computation.

### Offline interpretation
Multiple-choice knapsack / multidimensional MCKP.

### Possible structural theorem lens
Adaptive submodularity.

### Likely supporting negative result
A negative result or failure example showing that **naive static branch scores** can fail badly under a fixed budget, motivating continuation-value-aware allocation.

## 5. Current lessons from empirical development

The current repository development has already produced an important conceptual lesson:
- a naive branch-promise target is too weak
- a continuation-style target is more aligned with the real local object
- the main difficulty is not simply "is this branch good?"
- the real question is "what is the marginal value of giving this branch one more unit of compute?"

This empirical direction is consistent with the current theorem target and should remain central in manuscript framing.

## 6. Open cautions

Several issues remain important and should be acknowledged honestly.

### 6.1 Real branch interactions break full separability
The real reasoning process may involve answer aggregation, shared information, correlated failures, and verifier-induced coupling across branches. So simple additive branch-value models are only approximations.

### 6.2 Adaptive submodularity may not hold exactly
The marginal utility of extra reasoning may be noisy, non-monotone, or even exhibit overthinking. So adaptive submodularity should be treated as a candidate structural assumption, not a guaranteed property of the real problem.

### 6.3 Current continuation-value targets remain approximate
The present pilot pipeline uses approximation-based continuation targets rather than true counterfactual re-rollouts from saved decision states. This is a reasonable intermediate step, but not yet the final theoretical object.

## 7. Working manuscript positioning sentence

A useful working sentence for the manuscript is:

> We study adaptive test-time compute allocation for LLM reasoning under a fixed budget. The problem can be viewed as an adaptive, noisy hybrid of fixed-budget best-arm identification, rational metareasoning, and knapsack-style resource allocation: the system must repeatedly decide which partial reasoning branch should receive the next unit of computation, based on imperfect local signals about future value.

## 8. Status

At the current stage, the strongest manuscript direction is:
- theory centered on local-to-global allocation guarantees
- empirics centered on branch-scoring targets
- framing centered on fixed-budget adaptive allocation rather than generic heuristic tree search

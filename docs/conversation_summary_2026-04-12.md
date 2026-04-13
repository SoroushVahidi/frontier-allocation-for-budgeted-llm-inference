# Conversation summary (2026-04-12)

This document records the main conclusions and decisions from the early project discussion that led to the current research direction.

## 1. Initial goal

The project goal is to develop a NeurIPS-style research paper at the intersection of **theoretical computer science** and **AI**, centered on **adaptive test-time compute allocation for LLM reasoning**.

The desired project should:
- have a clear theoretical core,
- remain strongly relevant to modern LLM reasoning,
- and be strong enough to support a publishable paper rather than only an engineering system.

## 2. Topic search and narrowing

We first explored broad NeurIPS-relevant directions and narrowed the search to three promising clusters:

1. **Adaptive test-time compute allocation for LLM reasoning under a fixed budget**
2. **When extra reasoning hurts / adaptive stopping under non-monotone reasoning curves**
3. **Benchmark reliability under compute variation**

After literature-oriented searches, the first topic was selected as the strongest overall direction.

### Current selected direction

**Adaptive test-time compute allocation for LLM reasoning under a fixed budget**

More specifically, the project is now centered on:

> **Adaptive allocation over reasoning trees with noisy node-value estimates**

This is the version judged to have the best combination of:
- theory potential,
- AI relevance,
- NeurIPS fit,
- and room for novelty beyond current search heuristics.

## 3. Working problem idea

The most promising formulation discussed so far is:

- reasoning proceeds over a tree of partial reasoning states,
- compute is limited by a finite budget,
- each node has some unknown downstream utility or success probability,
- the allocator only observes noisy local signals (heuristics, verifier scores, confidence, etc.),
- and the goal is to decide where to spend compute in order to maximize the chance of finding a correct final answer.

A representative working statement is:

> Given a fixed inference budget, allocate compute across partially explored reasoning states to maximize the chance of reaching a correct final solution when local value estimates are noisy.

## 4. Main open questions identified

The following research questions were identified as central:

1. What is the right formal problem statement?
2. What is the simplest realistic model of a reasoning tree?
3. What information does the allocator actually observe?
4. Under what assumptions can adaptive allocation beat fixed baselines?
5. What guarantees should be targeted (approximation, regret, competitive ratio, etc.)?
6. How should noise in node-value estimates be modeled?
7. How should correlated node values / redundant branches be handled?
8. What is the marginal value of one extra unit of compute?
9. Can greedy allocation be near-optimal?
10. When does greedy fail badly?
11. Should expansion, verification, and stopping be treated separately or jointly?
12. What is the strongest baseline family we must beat?
13. What is the fairest budget definition for experiments?
14. Which benchmarks are appropriate for our claim?
15. Does the method generalize beyond math?
16. How sensitive is the method to weak verifiers or poor confidence signals?
17. Can beam search, Best-of-N, verifier-guided search, and our method be unified in one framework?
18. Is there an impossibility result or lower bound we can prove?
19. What is the right empirical proxy for a reasoning tree in actual LLM experiments?
20. How much of the paper should be theory versus empirical?

## 5. Literature conclusions so far

From the literature searches performed during the discussion, the main conclusions were:

### What appears already partially solved
- Budgeted reasoning formulations already exist in recent work.
- Reasoning-tree proxies such as CoT prefixes, beam states, verifier-ranked nodes, and sampled partial traces are accepted in recent papers.
- Adaptive methods often beat fixed baselines empirically.
- Noise and redundancy problems are known empirically.
- Math benchmarks such as GSM8K, MATH, AIME, and related datasets are standard.

### What still appears weak or unsolved
- No strong LLM-specific theory yet for **adaptive allocation over noisy reasoning trees**.
- Very limited theory for **noisy and correlated node-value estimates**.
- Weak formal treatment of the **marginal value of one extra unit of compute**.
- No clean unified framework subsuming beam search, Best-of-N, verifier-guided search, and adaptive allocation.
- Robustness to weak verifiers appears mostly empirical rather than theorem-backed.

## 6. Main baselines identified

The project currently uses the following four baselines as the main neighboring methods:

1. **ReST-MCTS\***  
   *ReST-MCTS*: LLM Self-Training via Process Reward Guided Tree Search

2. **Tree-PLV**  
   *Advancing Process Verification for Large Language Models via Tree-Based Preference Learning*

3. **PGTS**  
   *Policy Guided Tree Search for Enhanced LLM Reasoning*

4. **Scaling Automated Process Verifiers for LLM Reasoning**  
   (sometimes informally referred to as “Rewarding Progress”)

These four baselines were chosen because together they cover:
- process-reward guided tree search,
- state-level process verification,
- learned search control,
- and fixed-budget guided search with strong process verifiers.

## 7. Dataset set selected for the repository

The working core dataset set is:
- GSM8K
- MATH
- GPQA Diamond
- AIME
- OlympiadBench
- NaturalPlan

Extended / optional coverage:
- LiveCodeBench

The recommended initial subset for first experiments is:
- GSM8K
- MATH
- GPQA Diamond

This subset was considered a strong starting point because it combines:
- standard multi-step reasoning,
- harder symbolic reasoning,
- and difficult science reasoning.

## 8. Current novelty boundary

The current working novelty boundary is:

> Existing methods use process rewards, step-level verification, or learned tree-search control, but they still do not provide a clean theory of marginal inference-time budget allocation over noisy reasoning trees with strong guarantees.

Or more explicitly:

> Existing LLM reasoning methods adapt search heuristically using verifiers, rewards, or learned policies, but they do not yet provide a clean theory of marginal inference-time budget allocation over noisy reasoning trees. The intended project aims to formalize this problem, analyze when adaptive allocation improves over fixed baselines, and validate the resulting policies under matched budgets.

## 9. Suggested paper shape

A promising paper shape discussed in the conversation is:

- a formal budgeted allocation problem over reasoning trees,
- a simple but nontrivial adaptive allocation policy,
- a positive theoretical result (for example near-optimality under assumptions),
- a negative result or failure case (for example where greedy fails),
- and matched-budget experiments on a focused benchmark suite.

The balance should lean clearly theoretical, but with enough experiments to establish relevance to actual LLM reasoning.

## 10. Immediate next steps identified in discussion

The following next steps were suggested:

1. Freeze the formal setup.
2. Decide the precise compute unit (expansion, verifier call, sampled continuation, or similar).
3. Define the observation model for noisy node-value signals.
4. Choose the theorem target.
5. Specify the baseline family and matched-budget protocol.
6. Build the minimal benchmark suite for first experiments.

## 11. Repository usage note

This file is intended as an internal project memory note. It should help future contributors (or future versions of the project) recover:
- why this topic was chosen,
- what has already been searched,
- what the current novelty claim is,
- and which open questions remain central.

## 12. Status

As of this note, the project is still in the **problem formulation / literature consolidation** stage, but the direction has been narrowed enough that formal modeling work can begin.

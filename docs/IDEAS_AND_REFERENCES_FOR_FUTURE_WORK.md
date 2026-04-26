# Ideas and references for future work

This anonymous note collects literature directions that may inform future diagnostic variants. It is not a claim that these ideas are implemented or validated here.

## Math, verifiers, and candidate reranking

| Reference | Relevance | Repository implication | Small implementable feature? |
|---|---|---|---|
| Cobbe et al., "Training Verifiers to Solve Math Word Problems" | Shows that verifier-guided selection can outperform naive generation on math word problems. | Supports treating candidate selection as a first-class bottleneck for direct-reserve methods. | Add verifier-style features for candidate plausibility and final-answer consistency. |
| Wang et al., "Self-Consistency Improves Chain of Thought Reasoning" | Establishes answer aggregation across diverse reasoning paths. | Motivates support-count and agreement baselines for candidate pools. | Compare learned rerankers against support-count on more disjoint slices. |
| Lightman et al., "Let's Verify Step by Step" | Demonstrates value of process supervision and step-level verification. | Suggests future branch/candidate features beyond final answer agreement. | Add step-local consistency or arithmetic-check flags to scorer features. |
| Math-Shepherd | Provides process-level supervision signals for mathematical reasoning. | Suggests richer verifier features when branch traces are available. | Add optional process-score columns for trace-level candidate datasets. |
| Learning to Rank Chain-of-Thought / EORM-style reranking | Frames answer selection as ranking over generated reasoning candidates. | Directly matches the learned candidate scorer setup. | Add ranking metrics and calibration plots for pairwise scorer outputs. |
| Bradley-Terry and pairwise ranking models | Pairwise preferences are natural when multiple candidates compete within one problem. | Supports the pairwise logistic scorer as a diagnostic candidate. | Extend pairwise features with answer-equivalence and prompt-family agreement. |

## Non-math, GPQA, and multiple choice

| Reference | Relevance | Repository implication | Small implementable feature? |
|---|---|---|---|
| Rein et al., GPQA | GPQA stresses expert-level knowledge and option selection. | Current math-shaped selectors may not transfer without option-aware checks. | Add option extraction confidence and explanation-option consistency features. |
| MCQ self-consistency / option-invariance work | Multiple-choice answers can be sensitive to option order and phrasing. | Agreement should account for option labels and option text, not just raw final strings. | Add option-text canonicalization and option-flip diagnostics. |
| Ranked Voting based Self-Consistency | Voting/ranking can be more robust than simple plurality on candidate answers. | Could improve support-count baselines when candidates include rankings or eliminations. | Add ranked/elimination signal extraction for MCQ traces. |
| Weaver / weak verifiers for generation-verification gap | Weak verifiers can still improve selection when aggregated carefully. | Motivates lightweight domain rerankers before large reruns. | Add confidence-gated weak-verifier features for GPQA candidate pools. |
| Confidence-gated verification / weak verifier aggregation | Verification should abstain or defer under low confidence. | Helps prevent direct-reserve selectors from degrading easy/control cases. | Add learned override margins and fallback-to-base gates. |

## Planning and Natural Plan

| Reference | Relevance | Repository implication | Small implementable feature? |
|---|---|---|---|
| Natural Plan benchmark | Tests planning, constraints, and structured validity rather than numeric answers. | Current answer-support features are insufficient for plan validity. | Add parseable-plan and hard-constraint-satisfied counters. |
| PlanGenLLMs survey | Summarizes LLM planning methods and failure modes. | Suggests separating generation quality from plan validation quality. | Add plan-validity audit fields to non-math candidate tables. |
| LLM-based formalized planning | Formalization can turn natural language plans into checkable constraints. | Supports domain-specific reranking over generic answer agreement. | Add optional parser hooks for plan steps and entities. |
| Constraint satisfaction planning with LLM coding and verification | Verifiers can catch ordering, feasibility, and constraint violations. | Useful for Natural Plan rerankers and oracle-gap analysis. | Add hard-constraint violation counts and transition feasibility flags. |
| Plan validity and constraint-checking literature | Provides tools for checking whether generated plans satisfy required constraints. | Encourages reporting candidate-pool oracle accuracy separately from selector accuracy. | Add plan validity subset metrics for gold-present and present-misselected cases. |

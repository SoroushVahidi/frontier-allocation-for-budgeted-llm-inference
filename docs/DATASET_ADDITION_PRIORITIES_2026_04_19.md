# Dataset addition priorities (2026-04-19)

## Purpose

This note records the current dataset-expansion recommendation for the repository after reviewing recent external benchmark suggestions.

The goal is not to build a generic benchmark list.
The goal is to identify which additional datasets are most useful for the repository's current project:

> fixed-budget adaptive test-time compute allocation for LLM reasoning, especially branch allocation, continue-vs-commit decisions, useful diversity, answer aggregation, and verification under limited budget.

## Current repository context

The current repository already includes or has recently emphasized hard reasoning settings such as GSM8K, MATH-500, AIME 2024, OlympiadBench, and GPQA Diamond.

The dataset question is therefore not "what benchmarks exist?"
It is:

> **what additional datasets most increase diagnostic value for adaptive reasoning-budget allocation, without overinvesting in already-saturated or weakly matched benchmarks?**

## Recommended additions in priority order

### 1. LiveCodeBench

Best next addition overall.

Why:
- contamination-aware and time-segmented,
- naturally supports continue-vs-commit and repair decisions,
- strong execution / verification structure,
- branch diversity is meaningful,
- and automated checking is unusually strong.

Why this fits the repo especially well:
- branch allocation can be studied not only across candidate solutions but across repair / verification opportunities,
- verification is concrete rather than fuzzy,
- and adaptive budget can matter in a more operational way than on simple one-shot exact-answer tasks.

## 2. Humanity's Last Exam (HLE)

Best broad frontier-difficulty addition.

Why:
- built for post-saturation evaluation,
- broad subject coverage,
- very high difficulty / headroom,
- and still discriminative for strong frontier models.

Why this fits the repo:
- useful for testing whether more branching / more budget is worth paying for on genuinely difficult problems,
- and useful for assessing whether current branch-allocation policies transfer beyond math-only settings.

Recommended first slice:
- start with text-only and exact-answer / automatically gradable subsets before broader multimodal expansion.

## 3. AIME 2025

Best clean drop-in next math addition.

Why:
- very easy to integrate conceptually after AIME 2024,
- exact integer-answer format remains ideal for aggregation and commit decisions,
- and useful for transfer testing rather than only in-distribution gains.

Why this fits the repo:
- low integration ambiguity,
- direct compatibility with existing math-evaluation logic,
- and a good test of whether current branch-allocation heuristics generalize to newer contest distributions.

## 4. HMMT

Best next competition-math transfer benchmark after AIME 2025.

Why:
- useful for testing whether policies learned on one contest style overfit,
- and already appearing in recent reasoning / test-time-scaling evaluations.

Why this fits the repo:
- supports the question "does our adaptive compute policy generalize across hard math distributions?"

## 5. BRUMO

Best next uncontaminated competition-math extension after HMMT.

Why:
- useful as another fresh high-end math stress test,
- and relevant for transfer and uncontaminated evaluation.

Why this fits the repo:
- helps test whether the method depends too much on the structure of one competition family.

## Optional broader-coverage additions

### MMLU-Pro

Recommended as a secondary breadth / control benchmark, not as the next core adaptive-budget dataset.

Why:
- broader and harder than original MMLU,
- still discriminative,
- useful for non-math breadth.

Why it is not top priority:
- weaker answer-aggregation structure than exact-answer math or code-execution settings,
- and less naturally matched to branch diversity / verification than LiveCodeBench or newer hard math sets.

### HLE multimodal slices

Useful later if multimodality becomes part of the project scope.

Why not first-wave:
- risks mixing reasoning-budget questions with modality-handling questions,
- which may complicate current repo conclusions.

## Lower-priority additions for now

### More GPQA-like multiple-choice additions

Lower priority than LiveCodeBench or fresh competition math.

Reason:
- the repository already has GPQA Diamond as a hard-science anchor,
- and marginal information gain now appears lower than adding code-repair / execution or fresher uncontaminated math distributions.

### Original MMLU or easier older coding benchmarks

Do not prioritize.

Reason:
- lower discriminative value,
- higher saturation risk,
- and weaker direct match to the repository's current adaptive-budget research question.

## Recommended practical addition order

If the goal is disciplined incremental expansion, use this order:

1. AIME 2025
2. LiveCodeBench
3. HMMT
4. BRUMO
5. Humanity's Last Exam (text-only / exact-answer-first slice)
6. MMLU-Pro as a breadth control set

This order balances:
- ease of integration,
- verification clarity,
- transfer-testing value,
- and breadth beyond the current mostly-math emphasis.

## Suggested repository policy

### First-wave additions
- AIME 2025
- LiveCodeBench

### Second-wave additions
- HMMT
- BRUMO

### Third-wave additions
- HLE (text-only / exact-answer-first)
- MMLU-Pro

## Best concise summary

A safe current dataset-expansion summary is:

> The best next dataset additions are LiveCodeBench, Humanity's Last Exam, AIME 2025, HMMT, and BRUMO, with MMLU-Pro as a breadth/control benchmark rather than a core adaptive-budget benchmark. The strongest immediate additions for practical repository value are AIME 2025 and LiveCodeBench, because they balance integration ease, verification quality, and diagnostic value for continue-vs-commit and branch-allocation research.

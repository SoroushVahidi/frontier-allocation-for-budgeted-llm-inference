# PRM Step-Level Verifier Selector Reference (2026-04-29)

Purpose: document the next paper-backed selector family after Cobbe-style outcome verification, so future agents know what it is, what paper it comes from, what repository/data artifacts exist, and whether it has been implemented/tested here.

This document is about **process reward model / step-level verifier selectors**, primarily based on Lightman et al., *Let's Verify Step by Step*, and the released PRM800K dataset.

## 1. Short definition

A **PRM-style step-level verifier selector** scores the reasoning process step by step, rather than only judging the completed solution outcome. Given several candidate reasoning traces for the same problem, it verifies each step, aggregates step scores into a trace score, groups traces by normalized final answer, and selects the answer group with the strongest process-verifier evidence.

Repository-safe definition:

> PRM-style selector = split each candidate reasoning trace into steps, score the correctness/usefulness of each step with a process verifier, aggregate step scores into a trace score, then use those trace scores to rerank or vote among final-answer groups.

This is distinct from Cobbe-style outcome verification:

- Cobbe-style outcome verifier: scores a **whole completed solution** by predicted final correctness.
- PRM-style verifier: scores **intermediate reasoning steps** and aggregates those process scores.

## 2. Main paper record

| Field | Value |
|---|---|
| Main method | Process reward model / step-level verifier |
| Main paper | *Let's Verify Step by Step* |
| Authors | Hunter Lightman, Vineet Kosaraju, Yura Burda, Harri Edwards, Bowen Baker, Teddy Lee, Jan Leike, John Schulman, Ilya Sutskever, Karl Cobbe |
| Year | 2023 |
| Status | arXiv preprint |
| arXiv | https://arxiv.org/abs/2305.20050 |
| PDF | https://cdn.openai.com/improving-mathematical-reasoning-with-process-supervision/Lets_Verify_Step_by_Step.pdf |
| Repository / dataset | https://github.com/openai/prm800k |
| Hugging Face paper page | https://huggingface.co/papers/2305.20050 |

Related paper:

| Field | Value |
|---|---|
| Related method | Math-Shepherd / automatically constructed process supervision |
| Paper | *Math-Shepherd: Verify and Reinforce LLMs Step-by-Step without Human Annotations* |
| arXiv | https://arxiv.org/abs/2312.08935 |
| PDF | https://arxiv.org/pdf/2312.08935.pdf |

## 3. Dataset/artifact record: PRM800K

PRM800K is the released process-supervision dataset accompanying *Let's Verify Step by Step*.

Important details from the research brief:

- Dataset/repository: https://github.com/openai/prm800k
- License: MIT, according to the retrieved brief.
- About 800,000 step-level correctness labels for model-generated solutions to MATH problems.
- Data format: newline-delimited JSON, one labeled solution sample per line.
- Labels are nested inside the solution steps.
- Step labels use ratings in {-1, 0, +1}: incorrect, neutral/no-progress, or correct/useful.
- Labels are human annotated.
- The repo includes grading code using normalization and SymPy-style equality checks.
- The repo uses a nonstandard MATH split: training expands with many original test problems and evaluates on a held-out subset.
- Public scored evaluation samples are released.
- The retrieved sources did not verify a public pretrained PRM checkpoint.

## 4. Exact method behavior

### Inputs

A process verifier receives:

- problem statement;
- candidate reasoning trace split into ordered steps;
- optionally, the prefix up to each step;
- no gold answer at inference time.

### Outputs

For each step, the verifier should output something like:

- probability step is correct/useful;
- probability step is incorrect;
- neutral/no-progress score;
- relevance/usefulness score;
- optional short diagnostic reason.

Then a selector aggregates these step scores into a trace score and uses trace scores to choose a final answer.

### Training target

The target is not final-answer correctness alone. The target is the correctness/usefulness of intermediate reasoning steps.

This is why PRM-style selectors are the natural next method after Cobbe-style outcome verification: they may detect traces that reach a plausible final answer through weak or invalid reasoning, and they provide finer-grained diagnostics.

## 5. Recommended selection rule for this repository

This rule is an implementation recommendation, not necessarily a verbatim formula from the paper.

Given candidate trace i with T steps, compute:

```text
s_trace_i = (sum_t w_t * log(p_t + eps)) / (sum_t w_t) - lambda * log(1 + T)
```

Where:

- p_t = verifier probability that step t is correct/useful;
- w_t = 1 for substantive steps and 0 for neutral boilerplate;
- eps = small numerical constant;
- lambda = small length penalty.

Then group traces by normalized final answer a:

```text
S(a) = logsumexp(s_trace_i for i with final_answer_norm == a)
       + beta * log(1 + support_count(a))
```

Select the answer group with highest S(a), and return the best trace inside that group.

Practical defaults:

- do not use min-step score as the primary score because it is brittle;
- do not use final-step-only score because it discards process information;
- use mean log step probability over substantive steps;
- keep support bonus capped/small so many weak traces do not beat one strong trace;
- avoid penalizing concise correct reasoning.

## 6. Minimal implementation versions

### v1: prompted LLM-as-step-verifier

Fastest repository implementation:

1. split each candidate trace into steps;
2. call a verifier model once per full trace, asking it to label all steps in JSON;
3. aggregate step scores into a trace score;
4. group by normalized final answer;
5. select by process-weighted answer-group score.

This is **PRM-inspired**, not a faithful trained PRM.

### v2: PRM-style selector using public data/artifacts

If no public checkpoint is available, use PRM800K format and either:

- train a lightweight verifier/head;
- distill a prompted step-verifier into a smaller model;
- or use PRM800K-style labels for evaluation/calibration.

### v3: faithful trained PRM

Train/fine-tune a step-level verifier on PRM800K and/or our own generated traces with step labels, then use it for test-time reranking.

## 7. Prompted step-verifier template for v1

System prompt:

```text
You are a strict mathematical reasoning verifier.
Judge a candidate solution trace step by step.
Do NOT use any gold answer or outside reference answer.
Evaluate only whether each step is valid and useful given:
(1) the problem,
(2) earlier accepted steps,
(3) basic mathematics.
Be robust to harmless formatting differences.
Return JSON only.
```

User prompt:

```text
Problem:
{problem}

Candidate reasoning steps:
1. {step_1}
2. {step_2}
...
N. {step_N}

Instructions:
For each step, output:
- step_index
- label: "correct", "neutral", or "incorrect"
- prob_correct: number in [0,1]
- prob_incorrect: number in [0,1]
- relevance: number in [0,1]
- arithmetic_risk: number in [0,1]
- note: <= 20 words

Then output:
- trace_score: a single number in [0,1] reflecting overall trace quality
- dominant_failure: one of ["none", "arithmetic", "logic", "irrelevant", "format", "missing-justification", "contradiction"]
- short_reason: <= 30 words

Rules:
- Neutral means not wrong, but not clearly advancing the solution.
- Incorrect means mathematically wrong, inconsistent with prior steps, or unjustified in a way that threatens correctness.
- Do not penalize concise correct reasoning.
- Do not reward extra length.
- Do not infer the gold answer.
- Output JSON only and no markdown.
```

## 8. Proposed repository method name

Recommended method name:

- `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1`

Shorter acceptable name:

- `dr_v2_prm_step_rerank_v1`

Status as of this document:

- proposed;
- not implemented;
- not tested;
- should come **after** the Cobbe-inspired outcome-verifier reranker unless there is a specific reason to skip outcome verification.

## 9. Relationship to current repository methods

Existing repository pieces that are relevant:

- `experiments/prm_partial_scorer.py` exists as PRM-style/proxy infrastructure.
- PRM proxy variants already exist in some frontier-controller paths:
  - `adaptive_prm_partial`
  - `adaptive_prm_partial_early_reject`
  - `verifier_guided_search_prm`
  - `verifier_guided_search_prm_early_reject`
- These are **not** the same as a DR-v2 final-answer process-verifier reranker.

Missing piece:

> A live DR-v2 final-answer selector that scores candidate traces step-by-step, groups by normalized answer, and selects by process-verifier aggregate score.

## 10. Required logs for our implementation

Any implementation should save:

- `candidate_traces.jsonl`
- `step_verifications.jsonl`
- `trace_scores.csv`
- `answer_group_process_scores.csv`
- `process_selector_decisions.csv`
- `present_not_selected_recoveries.jsonl`
- `process_verifier_regressions.jsonl`
- `failure_taxonomy.csv`
- `run_manifest.json`

Each verified trace should include:

- problem id;
- candidate id;
- final raw answer;
- normalized final answer;
- split steps;
- per-step label/probabilities;
- trace score;
- dominant failure;
- verifier token/cost/latency;
- selected/not selected;
- gold-answer fields only in post-hoc evaluation, never in verifier input.

## 11. Evaluation protocol

First run only after implementation exists.

Suggested 100-example validation:

- dataset: `openai/gsm8k`;
- provider: Cohere;
- budget: 4;
- seed: 11;
- methods:
  - `external_l1_max`;
  - original `direct_reserve_semantic_frontier_v2`;
  - Cobbe-inspired outcome-verifier reranker, if implemented;
  - PRM-style step-level verifier reranker.

Report:

- accuracy;
- paired wins/ties/losses;
- correct-present-but-not-selected recovery count;
- regressions;
- verifier tokens/cost/latency;
- number of verifier calls;
- step-level failure taxonomy.

## 12. Failure controls

- Do not reward long traces.
- Do not penalize concise correct reasoning.
- Score only substantive steps when aggregating.
- Use relevance to avoid locally valid but irrelevant steps.
- Never include the gold answer in verifier prompts.
- Score the entire trace in one verifier call to control cost and consistency.
- Consider optional symbolic arithmetic checks for numeric transformations.
- Keep a capped support bonus so many weak traces do not dominate one strong trace.

## 13. Documentation status table

| Field | Current value |
|---|---|
| Method family | PRM-style step-level verifier selector |
| Primary paper | *Let's Verify Step by Step* |
| Paper-backed? | yes |
| Exact paper implementation? | no |
| Repo status | proposed / not implemented |
| Tested in repo? | no |
| Existing related proxy infrastructure | yes, PRM partial branch scoring exists |
| Next implementation target | `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1` |
| Should run before Cobbe outcome reranker? | no, usually after outcome reranker |

## 14. One-line project action item

After implementing and testing the Cobbe-inspired outcome-verifier reranker, implement `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1` as a PRM-inspired step-level verifier selector and compare whether step-level process scoring recovers present-not-selected failures better than outcome-only scoring.

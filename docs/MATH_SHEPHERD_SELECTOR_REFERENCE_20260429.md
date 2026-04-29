# Math-Shepherd Selector Reference (2026-04-29)

Purpose: document Math-Shepherd as a paper-backed selector/verifier family for future DR-v2 final-answer reranking work. This file records what the method is, which artifacts exist, how it differs from Cobbe-style outcome verification and PRM800K-style process verification, and how it could be implemented in this repository.

Status in this repository as of 2026-04-29:

- Paper-backed: yes.
- Implemented: no.
- Tested: no.
- Priority: after Cobbe-inspired outcome-verifier reranking and after/alongside PRM-style step verifier work.

## 1. Short definition

**Math-Shepherd-style selector** = score every semantic reasoning step in each candidate trace with a process-oriented reward model or prompted approximation, aggregate step scores into a trace score, group traces by normalized final answer, and select the answer group with the strongest process-quality evidence.

It is useful when final-answer selection needs step-level evidence rather than only final-answer agreement.

## 2. Paper record

| Field | Value |
|---|---|
| Title | *Math-Shepherd: Verify and Reinforce LLMs Step-by-step without Human Annotations* |
| Authors | Peiyi Wang, Lei Li, Zhihong Shao, Runxin Xu, Damai Dai, Yifei Li, Deli Chen, Yu Wu, Zhifang Sui |
| Year | 2024 |
| Venue | ACL 2024 long paper, *Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 9426--9439 |
| arXiv | https://arxiv.org/abs/2312.08935 |
| arXiv PDF | https://arxiv.org/pdf/2312.08935.pdf |
| ACL Anthology | https://aclanthology.org/2024.acl-long.510/ |
| ACL PDF | https://aclanthology.org/2024.acl-long.510.pdf |
| Hugging Face paper page | https://huggingface.co/papers/2312.08935 |
| PRM checkpoint surfaced | https://huggingface.co/peiyi9979/math-shepherd-mistral-7b-prm |
| RL model surfaced | https://huggingface.co/peiyi9979/math-shepherd-mistral-7b-rl |
| Dataset surfaced | https://huggingface.co/datasets/peiyi9979/Math-Shepherd |
| Processed TRL dataset surfaced | https://huggingface.co/datasets/trl-lib/math_shepherd |
| ModelScope dataset surfaced | https://modelscope.cn/datasets/AI-ModelScope/Math-Shepherd |
| Official GitHub/project page | not verified from retrieved sources |

## 3. What Math-Shepherd does

Math-Shepherd trains a process-oriented reward model for mathematical reasoning. Instead of only checking whether the final answer is correct, it assigns reward/verification signals to individual reasoning steps.

The paper emphasizes automatically constructed process-wise supervision, rather than relying on human step labels like PRM800K.

The surfaced public model card indicates a PRM interface where reasoning steps are tagged and the model assigns probabilities to `+` / `-` step labels at tagged step boundaries.

## 4. Difference from related selector families

| Family | Difference |
|---|---|
| Cobbe-style outcome verifier | Scores whole completed solution correctness. Math-Shepherd scores intermediate steps/process. |
| PRM800K / *Let's Verify Step by Step* | Both are process-verifier families. PRM800K uses human step labels; Math-Shepherd emphasizes automatically constructed process supervision. |
| Simple self-consistency | Self-consistency counts final answers. Math-Shepherd weights traces by process quality. |
| LLM-as-judge final-answer verifier | Generic prompted judge can approximate scoring, but Math-Shepherd is math-specific step-level PRM-style scoring. |
| Bradley-Terry / pairwise ranking | Pairwise rankers compare candidates. Math-Shepherd gives independent per-step/trace scores that can be aggregated by answer group. |

## 5. Selector recipe for this repository

Given a problem and multiple candidate traces:

1. Split each trace into semantic reasoning steps.
2. Treat the final answer line as a final tagged step.
3. Score each step with a Math-Shepherd-style PRM or JSON prompted judge.
4. Aggregate step scores into a trace score.
5. Normalize final answers.
6. Group traces by normalized final answer.
7. Score answer groups by combining best-trace quality, top-k trace quality, and smoothed support count.
8. Select the best answer group and representative trace.

## 6. Recommended scoring formula

For candidate trace t with m steps, compute per-step probability p_i that step i is good/correct/useful.

Recommended trace score:

```text
s_trace(t) = (1 / m) * sum_i log(clip(p_i, eps, 1-eps))
             + gamma * log(clip(p_m, eps, 1-eps))
```

Defaults:

- eps = 1e-4.
- gamma = 0.3.
- p_m is the final/terminal step score.

Rationale:

- Mean log-score avoids automatically favoring long traces.
- Extra terminal-step weight helps catch traces with plausible early steps but wrong final jump.

Answer group score:

```text
s_ans(a) = lambda * max_{t in G_a} s_trace(t)
           + (1 - lambda) * TopKMean_{t in G_a}(s_trace(t))
           + mu * log((|G_a| + beta) / (N + beta * |A|))
```

Suggested defaults:

- lambda = 0.6.
- K = min(3, |G_a|).
- mu = 0.15.
- beta = 1.

This is a process-weighted answer-group selector: it combines best trace quality, top-k within-answer support, and smoothed self-consistency.

## 7. Minimal v1 implementation

A minimal repository implementation can be prompt-based, even before using the released Mistral PRM checkpoint.

Possible method name:

- `direct_reserve_semantic_frontier_v2_math_shepherd_prompt_step_rerank_v1`

Behavior:

1. use DR-v2 candidate generation;
2. split candidate traces into semantic steps;
3. call a JSON-only step-verifier prompt once per trace;
4. compute trace score from step probabilities;
5. group by normalized answer;
6. select by process-weighted answer-group score.

This should be documented as **Math-Shepherd-inspired**, not the exact released PRM implementation.

## 8. More faithful implementation

Possible method name:

- `direct_reserve_semantic_frontier_v2_math_shepherd_prm_rerank_v1`

Behavior:

1. load `peiyi9979/math-shepherd-mistral-7b-prm` or equivalent released checkpoint;
2. format problem + trace with the model's expected step tag format;
3. extract per-step probabilities for `+` and `-` at tagged step boundaries;
4. compute trace and answer-group scores;
5. select the best answer group.

Caveats:

- Requires local/remote model inference infrastructure.
- More expensive than a prompt-only or outcome-only verifier.
- Must verify dependency, hardware, and licensing/access constraints before adding to live runs.

## 9. Prompt template for v1

System prompt:

```text
You are a strict math process verifier. Evaluate each reasoning step for local mathematical correctness and relevance to solving the given problem. Return JSON only.
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

Final answer:
{final_answer}

Instructions:
For each step, assign a score between 0.0 and 1.0.
A high score means the step is both mathematically correct and useful for reaching the final answer.
A low score means arithmetic error, invalid inference, contradiction, or irrelevant detour.
Score the final answer as the last step using the same rule.
Do not reward verbosity, repetition, or restatement.
Do not use outside knowledge beyond the problem statement and trace.
Do not use or infer any hidden gold answer.

Return JSON only with this schema:
{
  "step_scores": [
    {
      "step_id": 1,
      "score": 0.0,
      "label": "good|bad|uncertain",
      "error_type": "none|arithmetic|logic|irrelevance|missing_justification|answer_mismatch"
    }
  ],
  "trace_score_hint": 0.0,
  "final_answer_supported": true,
  "brevity_penalty": 0.0
}
```

## 10. Required logs if implemented

Save:

- `math_shepherd_candidate_traces.jsonl`
- `math_shepherd_step_scores.jsonl`
- `math_shepherd_trace_scores.csv`
- `math_shepherd_answer_group_scores.csv`
- `math_shepherd_selector_decisions.csv`
- `math_shepherd_recovery_cases.jsonl`
- `math_shepherd_regression_cases.jsonl`
- `math_shepherd_failure_taxonomy.csv`
- `run_manifest.json`

Each trace record should include:

- problem id;
- candidate id;
- raw trace;
- split steps;
- raw final answer;
- normalized final answer;
- per-step scores;
- aggregate trace score;
- answer group score;
- selected/not selected;
- verifier tokens/cost/latency;
- evaluation-only gold/correctness fields, never passed into verifier prompt.

## 11. Failure modes and guardrails

| Failure mode | Guardrail |
|---|---|
| arithmetic mistakes missed | optional symbolic/numeric checker for arithmetic transformations |
| locally correct but irrelevant steps | include relevance/usefulness in step score |
| long-trace bias | use mean log score, step cap, deduplicate repeated steps |
| concise-solution penalty | avoid strong length penalty; only discount no-derivation traces |
| gold-answer leakage | never pass gold/reference answer to verifier |
| verifier overconfidence | log calibration, compare regressions, use uncertainty buckets |
| cost explosion | one verifier call per trace, cap steps, prefilter candidate count |

## 12. Evaluation protocol

Compare, after implementation:

- original DR-v2 selector;
- Cobbe-inspired outcome-verifier reranker;
- PRM step-verifier reranker;
- Math-Shepherd-style selector;
- `external_l1_max`.

Initial setting:

- dataset: `openai/gsm8k`;
- provider: Cohere;
- budget: 4;
- seed: 11;
- 100 scored examples per method.

Report:

- accuracy;
- paired wins/ties/losses;
- correct-present-but-not-selected recovery count;
- regressions;
- verifier tokens/cost/latency;
- step-level failure taxonomy;
- whether answer grouping improved or harmed selection.

## 13. Repository status table

| Field | Current value |
|---|---|
| Method family | Math-Shepherd-style process verifier selector |
| Paper-backed? | yes |
| Exact paper implementation? | no |
| Repo implementation status | not implemented |
| Tested in repo? | no |
| Proposed prompt method | `direct_reserve_semantic_frontier_v2_math_shepherd_prompt_step_rerank_v1` |
| Proposed PRM method | `direct_reserve_semantic_frontier_v2_math_shepherd_prm_rerank_v1` |
| Priority | after Cobbe-style outcome verifier and PRM-style step verifier |

## 14. One-line action item

After outcome-verifier reranking and PRM step-verifier reranking are implemented/tested, implement a Math-Shepherd-inspired selector that scores semantic reasoning steps, aggregates them into trace scores, groups by normalized final answer, and compares whether process-quality scoring recovers DR-v2 present-not-selected failures better than outcome-only reranking.

# Cobbe-Style Outcome Verifier Reference (2026-04-29)

Purpose: preserve the exact paper-backed meaning of **Cobbe-style outcome verification** and distinguish it from our repository's existing diagnostics, proxies, and future DR-v2 selector work.

This file should be updated whenever the repository implements, tests, or rejects a Cobbe-style selector variant.

## 1. Short definition

**Cobbe-style outcome verification** refers to the method from Cobbe et al., *Training Verifiers to Solve Math Word Problems*: generate many full candidate solution traces, score each completed solution with a verifier trained to predict whether the whole solution is correct, and select by verifier score rather than generator likelihood alone.

A repository-safe definition:

> Cobbe-style outcome verification = sample many complete reasoning traces, train or approximate a verifier that predicts whole-solution correctness from the problem and trace, then select by verifier score or by voting over the top verifier-ranked traces.

A more precise implementation definition:

> An outcome-supervised solution verifier is trained on model-generated math solutions labeled only by final-answer correctness. At test time, it is used for best-of-N reranking and optionally verifier-ranked voting over normalized final answers.

## 2. Paper record

| Field | Value |
|---|---|
| Title | *Training Verifiers to Solve Math Word Problems* |
| Authors | Karl Cobbe, Vineet Kosaraju, Mohammad Bavarian, Mark Chen, Heewoo Jun, Łukasz Kaiser, Matthias Plappert, Jerry Tworek, Jacob Hilton, Reiichiro Nakano, Christopher Hesse, John Schulman |
| Year | 2021 |
| Status | arXiv preprint; no separate venue verified from the retrieved sources |
| arXiv | https://arxiv.org/abs/2110.14168 |
| PDF | https://arxiv.org/pdf/2110.14168.pdf |
| Hugging Face paper page | https://huggingface.co/papers/2110.14168 |
| Official dataset repository | https://github.com/openai/grade-school-math |
| Hugging Face dataset | https://huggingface.co/datasets/openai/gsm8k |

## 3. Dataset/artifact record

Cobbe et al. introduced **GSM8K**, a dataset of grade-school math word problems with natural-language solutions.

Important dataset details from the retrieved research brief:

- About 8.5K high-quality grade-school math word problems.
- Split: roughly 7.5K train and 1K test.
- Problems usually require elementary arithmetic and around 2--8 reasoning steps.
- Official repository exposes raw data files under `grade_school_math/data/train.jsonl` and `grade_school_math/data/test.jsonl`.
- The answer format places the final numeric answer after `####`.
- The official repository also includes a Socratic variant, example model solutions, calculator-assisted sampling code, and illustrative training/sampling scripts.
- The retrieved sources did **not** verify public paper-scale verifier checkpoints or production-scale verifier training code.

## 4. Exact method behavior

### Training data construction

The paper's verifier training pipeline is:

1. finetune a generator on GSM8K;
2. sample many candidate completions from that generator for each training problem;
3. extract/normalize each candidate's final answer;
4. label each candidate solution as correct or incorrect by final-answer correctness;
5. train a verifier to predict whether the whole candidate solution is correct.

The supervision is **outcome supervision**: labels come from final-answer correctness, not from human-labeled intermediate steps.

### Verifier input/output

Input:

- problem statement;
- one completed candidate solution trace;
- candidate final answer as part of the trace.

Output:

- scalar score/probability that the candidate solution is correct.

### Token-level vs solution-level note

The stronger verifier described in the brief is token-level in the sense that it makes scalar predictions after solution tokens, but it remains outcome-supervised: the label comes from whole-solution final correctness, not step-level correctness labels.

The paper also uses an auxiliary language-modeling objective with the verifier objective.

## 5. Test-time selection rules

### Best-of-N verifier reranking

1. Generate N full candidate solutions.
2. Score each candidate solution with the verifier.
3. Select the candidate with the highest verifier score.

The brief reports N=100 as a practical default in the paper setting.

### Verifier-ranked voting

1. Generate N candidate solutions.
2. Rank candidates by verifier score.
3. Let only the top-k verifier-ranked candidates vote by normalized final answer.
4. Return the final answer with most votes among the top-k.

The brief reports that with 100 samples, top 3--5 verifier-ranked voting can work well, and with much larger sample sets, a larger top-k such as around 30 can be useful.

This is the paper-backed connection between outcome verification and answer grouping/self-consistency.

## 6. Distinction from related methods

| Method family | Difference from Cobbe-style outcome verifier |
|---|---|
| Process reward models / *Let's Verify Step by Step* | Step/process supervision; stronger but heavier. Cobbe-style verifier is outcome-supervised on completed solutions. |
| Math-Shepherd | Step-level/process-supervision style, often automatic process labels; heavier than outcome reranking. |
| Simple self-consistency / majority vote | Votes over generated final answers without a learned/verifier score. Cobbe uses verifier score first, and optionally voting only among top verifier-ranked samples. |
| LLM-as-judge prompting | Practical approximation for v1, but not the exact paper method; Cobbe trains a verifier. |
| Bradley-Terry / pairwise selectors | Pairwise preference/ranking models; Cobbe scores each candidate independently for correctness. |

## 7. Repository status: what already exists

Existing paper-inspired/offline pieces:

- `docs/COBBE_STYLE_OUTCOME_VERIFIER_DIAGNOSTIC.md`
- `scripts/run_cobbe_style_outcome_verifier_diagnostic.py`
- `docs/OUTCOME_VERIFIER_SELECTOR_DIAGNOSTIC.md`
- `scripts/run_outcome_verifier_selector_diagnostic.py`

These are **diagnostic/offline** adaptations. They are useful because they produce candidate solution rows, verifier feature audits, branch-level verifier scores, answer bucket scores, selector summaries, per-case decisions, and oracle-gap reports.

Existing generic/proxy infrastructure:

- `experiments/verifiers.py`
  - `CandidateVerifier`
  - `LLMVerifyProxyVerifier`
  - `SimulatedScorerVerifier`
- `experiments/scoring.py`
  - heuristic branch scorers;
  - learned branch scorers;
  - Bradley-Terry / tie-aware branch scorers.

Important limitation:

> The repository does **not yet** have a validated live DR-v2 final-answer-group selector that faithfully implements answer-grouped outcome-verifier reranking in the Cohere real-model runner.

## 8. Implementation status table

| Component | Paper-backed? | Exists in repo? | Tested? | Status |
|---|---:|---:|---:|---|
| Cobbe-style offline outcome verifier diagnostic | yes | yes | yes, diagnostic only | implemented but not live selector |
| Candidate/branch verifier interface | partly | yes | limited | infrastructure/proxy |
| LLM-as-verifier prompt approximation | paper-inspired approximation | planned/partially scaffolded | not validated as DR-v2 selector | next implementation path |
| Trained Cobbe-style outcome verifier | yes | no | no | future work |
| Best-of-N verifier reranking | yes | diagnostic only | not live DR-v2 validated | needs integration |
| Verifier-ranked answer voting / answer grouping | yes | diagnostic/planned | not live DR-v2 validated | next implementation path |
| DR-v2 outcome-verifier rerank variant | yes, inspired by Cobbe + answer grouping | proposed as `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1` | no | immediate next method |

## 9. Recommended repository implementation path

### v1: prompted outcome verifier / answer-grouped reranker

Implement as:

- `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`

Behavior:

1. use DR-v2 candidate generation/search;
2. collect candidate final answers and traces;
3. normalize final answers;
4. group candidates by normalized final answer;
5. score candidate traces with a lightweight LLM-as-verifier prompt;
6. aggregate scores within answer groups;
7. pick the answer group with the best aggregate score;
8. log all candidate, group, verifier, and final-decision information.

This is not the exact Cobbe trained verifier method, so it must be documented as:

> Cobbe-inspired prompted outcome-verifier reranking.

### v2: trained outcome verifier

To be closer to Cobbe et al.:

1. sample candidate traces from our generator/search methods;
2. label each candidate by final-answer correctness against gold;
3. train an outcome verifier on problem + candidate trace;
4. use verifier scores for best-of-N reranking and top-k verifier-ranked voting.

## 10. Required logs for future experiments

For every outcome-verifier selector experiment, save:

- all raw candidate traces;
- raw final answer;
- normalized final answer;
- source/branch metadata;
- verifier score/probability;
- selected answer group;
- support count per answer group;
- whether correct answer was present anywhere in the candidate pool;
- whether original selector missed a present correct answer;
- whether new selector recovered it;
- verifier-call count;
- verifier prompt/completion tokens;
- verifier estimated cost;
- latency;
- paired wins/ties/losses against original DR-v2, selection-fix v1, and `external_l1_max`.

## 11. Evaluation protocol for our repository

First validation should compare:

- `external_l1_max`;
- `direct_reserve_semantic_frontier_v2`;
- `direct_reserve_semantic_frontier_v2_selection_fix_v1`;
- `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`.

Suggested setting:

- provider: Cohere;
- dataset: `openai/gsm8k`;
- budget: 4;
- seed: 11;
- target: 100 scored examples per method.

Report:

- accuracy;
- paired wins/ties/losses;
- token/cost/latency including verifier overhead;
- verifier-call count;
- correct-present-but-not-selected recoveries;
- verifier-caused regressions;
- whether the method is cost-effective.

## 12. What to avoid

- Do not call prompted verifier v1 the exact Cobbe method; it is only Cobbe-inspired.
- Do not feed the gold answer to the verifier prompt.
- Do not over-weight support count so much that the verifier is ignored.
- Do not use only final answer text if reasoning trace is available; Cobbe-style verification scores completed solutions.
- Do not skip answer normalization; answer grouping depends on it.
- Do not claim trained-verifier evidence until a trained verifier exists.

## 13. One-line project action item

Next implementation target:

> Implement `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1` as a Cobbe-inspired answer-grouped outcome-verifier reranker, then test whether it recovers DR-v2 present-not-selected failures without excessive verifier cost.

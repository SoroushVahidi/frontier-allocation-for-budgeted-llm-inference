# Selector Prior-Work Implementation Audit (2026-04-29)

## Sources audited
- OpenAI GSM8K repo: https://github.com/openai/grade-school-math
- OpenAI PRM800K repo: https://github.com/openai/prm800k
- Math-Shepherd ACL paper: https://aclanthology.org/2024.acl-long.510/
- Math-Shepherd dataset/model cards:
  - https://huggingface.co/datasets/peiyi9979/Math-Shepherd
  - https://huggingface.co/peiyi9979/math-shepherd-mistral-7b-prm

## What is public vs not
| Source | Public assets | Trained verifier/PRM available? | Notes |
|---|---|---|---|
| grade-school-math | GSM8K data format, `####` answer extraction convention, illustrative pipeline | No released paper verifier training pipeline | README explicitly says sample training code is illustrative only. |
| prm800k | 800k step labels, labeler instructions, grading logic (`grader.py`) and eval harness | Data + eval code; not OpenAI production model weights | Includes conservative sympy-backed answer grading and large best-of-N eval protocol. |
| Math-Shepherd | paper + dataset + checkpoints on HF | Yes, open checkpoints; internal PPO code not fully open | Dataset card says step-wise PPO code is internal, but SFT/PRM/RL checkpoints are provided. |

## Scoring/aggregation and grading takeaways
- GSM8K: final numeric extraction is the value after `####`; calculator annotations (`<<...>>`) are part of format support.
- PRM800K: step supervision labels are at step granularity; grading relies on normalization + sympy equivalence, with explicit caveats about conservativeness.
- PRM800K eval uses large sample pools (best-of-N with many candidates per problem), unlike our current candidate_count=2 surface.
- Math-Shepherd verifies step-by-step with a trained process reward model and uses reranking of multiple outputs.

## Current implementation comparison
| Dimension | Prior-work behavior | Current behavior | Mismatch | Expected impact | Recommended fix |
|---|---|---|---|---|---|
| Verifier type (OV) | Trained verifier/ORM (Cobbe-style) | Prompted Cohere JSON judge | High | weak calibration, noisy rerank | treat as approximation; add warning and avoid overclaims |
| PRM type | Trained PRM scoring steps | Prompted step judge (Cohere) | High | poor transfer vs PRM800K-style gains | integrate open PRM checkpoint before claiming PRM fidelity |
| Candidate pool size | best-of-N often large | mostly N=2 in rerun | High | little rerank headroom | increase candidate count first |
| Step aggregation | multiple aggregation possibilities in literature | one fixed hybrid mean-min | Medium | suboptimal solution scoring | add pluggable aggregation modes + offline sweep |
| Answer grading | robust normalization/equivalence (PRM800K grader) | lightweight lowercase canonicalization in selector path | Medium | misses equivalent answers | import/adapt stricter grading/normalization layer |
| Step supervision format | explicit step labels and alternative completions | inferred steps from plain trace splitting | Medium | unstable per-step judgments | align segmentation and metadata schema |

## Low-risk fixes implemented in this change
1. Added configurable PRM aggregation modes (`hybrid_mean_min`, `min_step`, `mean_step`, `product`, `last_step`, `hybrid_mean_min_major_error_cap`).
2. Added offline script to sweep aggregation modes from existing rerun artifacts.
3. Added candidate-count warning in PRM selector metadata when `candidate_count <= 2`.

## Not portable without training / unavailable details
- Cobbe/OpenAI verifier training details and weights.
- OpenAI production PRM/ORM checkpoints.
- Math-Shepherd internal step-wise PPO training code (dataset card says internal code is not open).

## Decision guidance
- OV and PRM selectors here are **rough prompted approximations**, not faithful reproductions of trained verifier/PRM pipelines.
- Before further heuristic layering, prioritize:
  1) stronger answer normalization/equivalence grading;
  2) larger candidate pools (best-of-N);
  3) optional integration of open PRM checkpoints for true process scoring.

## Artifact-status note (local checkout)
- Missing in this checkout: `outputs/cohere_real_model_cost_normalized_validation_20260429T_SELECTOR_COMPARISON_30CASE_COHERE_RERUN/per_example_records.jsonl`.
- Best available local file used for plumbing validation: `outputs/cohere_real_model_cost_normalized_validation_20260425T133000Z_COHERE_STAGE1_MIN/per_example_records.jsonl`.
- Therefore, 30-case rerun aggregation conclusions remain pending until the intended rerun artifact is restored.

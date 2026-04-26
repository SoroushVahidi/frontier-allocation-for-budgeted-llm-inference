# Non-math failure diagnosis and roadmap

This note records current non-math evidence boundaries and a small future direction. It is anonymous and diagnostic-only.

## Current evidence

- The Wulver non-math audit is mixed and incomplete; treat it as provenance or appendix context.
- Natural Plan did not complete cleanly in the audit.
- GPQA Diamond evidence is partial.
- Strict/frontier methods did not clearly beat `external_l1_max` across the audited non-math slices.
- Unsupported method issues, including TALE runner support mismatches, should be avoided in future runs unless runner support is verified first.

## Diagnosis

- Current selection logic is math-shaped and over-indexes exact numeric support.
- GPQA needs option-aware verification rather than free-form numeric answer selection.
- Natural Plan needs constraint and plan-validity verification rather than answer-string aggregation.
- Answer support alone can mislead on MCQ and planning tasks.
- Direct baselines can be strong on knowledge-heavy tasks.
- Branching creates additional distractors when the selector is weak.

## Proposed diagnostic method idea

`direct_reserve_strong_plus_diverse_domain_rerank_v1`

Status: idea only, diagnostic-only, not implemented. It would keep direct-reserve candidate generation but replace generic answer support with domain-aware reranking features.

## GPQA features to add

- Option extraction confidence.
- Explanation-to-option consistency.
- Cross-prompt option agreement.
- Answer flip detection.
- Final option appears in final line.
- Contradiction between explanation and final option.
- Ranked or elimination signal.

## Natural Plan features to add

- Parseable plan format.
- Hard constraint satisfied count.
- Hard constraint violated count.
- Ordering validity.
- Missing or duplicate steps.
- Entity coverage.
- Local transition feasibility.
- Exact-output compatibility.

## Smallest future experiment

- Datasets: 20 GPQA Diamond examples and 20 Natural Plan examples.
- Provider: Cohere only.
- Budget: 4 only.
- Methods:
  - `external_l1_max`
  - `direct_reserve_strong_plus_diverse_v1`
  - future `direct_reserve_strong_plus_diverse_domain_rerank_v1`
- Report:
  - Direct accuracy.
  - Candidate-pool oracle accuracy.
  - Selector accuracy on gold-present subset.
  - Present-but-misselected rate.
  - Easy/control degradation.

Do not run broad non-math reruns until option-aware and plan-validity checks are implemented.

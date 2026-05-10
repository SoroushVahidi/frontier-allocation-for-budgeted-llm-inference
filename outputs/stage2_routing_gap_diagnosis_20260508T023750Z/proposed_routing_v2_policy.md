# Proposed routing v2 policy (offline proposal)

## Route updates

### percent_base_denominator
- Trigger (gold-free): contains `%` or words like "percent", "fraction", "increase/decrease", plus multiple base quantities or multi-period updates.
- Scaffold: `percent_base_denominator` (new).
- Example cases: `openai_gsm8k_683`, `openai_gsm8k_687`, `openai_gsm8k_702`.
- Budget cost: 1 call per triggered case.
- Risk: medium (base misidentification still possible).
- Prompt reuse/new: new scaffold template.

### average_target_score
- Trigger: words like "average", "score", "need on next/final test".
- Scaffold: `average_target_score` (new).
- Example case: `openai_gsm8k_758`.
- Budget cost: 1.
- Risk: low.
- Prompt reuse/new: new scaffold template.

### combinatorics_counting
- Trigger: split/partition/count-with-constraints patterns; discrete group sizing.
- Scaffold: `combinatorics_counting` (new).
- Example case: `openai_gsm8k_752`.
- Budget cost: 1.
- Risk: medium (order/constraint ambiguity).
- Prompt reuse/new: new scaffold template.

### ratio_partition
- Trigger: "twice", "half", ratio parts, share/partition requests.
- Scaffold: `ratio_partition` (new).
- Example cases: `openai_gsm8k_769`, `openai_gsm8k_706`, `openai_gsm8k_726`.
- Budget cost: 1.
- Risk: low-medium.
- Prompt reuse/new: new scaffold template.

### state_composition
- Trigger: multi-step add/subtract/transform with order dependency and unit conversion.
- Scaffold: `state_composition` (new) or reuse `before_after_state` where adequate.
- Example cases: `openai_gsm8k_695`, `openai_gsm8k_707`, `openai_gsm8k_725`, `openai_gsm8k_746`, `openai_gsm8k_765`.
- Budget cost: 1.
- Risk: medium for long narratives.
- Prompt reuse/new: mostly new scaffold; `openai_gsm8k_674` can reuse `before_after_state`.

## Notes
- Routing v2 remains gold-free and should start allowlisted to diagnosed cases/patterns.
- Existing prompts (`quantity_ledger_v2_1`, `rate_table_v1`, `target_difference_v1`) remain valid fallback routes.

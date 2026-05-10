# Discovery retry — experiment / replay plan

## Proposed method id

`direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_targeted_retry_v1`

## Positive targets (gold-absent union)

Exact case_ids (37):

```
openai_gsm8k_1003, openai_gsm8k_1006, openai_gsm8k_1019, openai_gsm8k_1027, openai_gsm8k_1029, openai_gsm8k_1045, openai_gsm8k_1099, openai_gsm8k_1125, openai_gsm8k_1155, openai_gsm8k_1166, openai_gsm8k_1187, openai_gsm8k_1198, openai_gsm8k_1215, openai_gsm8k_1230, openai_gsm8k_1244, openai_gsm8k_1248, openai_gsm8k_1281, openai_gsm8k_674, openai_gsm8k_683, openai_gsm8k_720, openai_gsm8k_750, openai_gsm8k_752, openai_gsm8k_758, openai_gsm8k_769, openai_gsm8k_773, openai_gsm8k_787, openai_gsm8k_814, openai_gsm8k_818, openai_gsm8k_829, openai_gsm8k_841, openai_gsm8k_851, openai_gsm8k_864, openai_gsm8k_875, openai_gsm8k_906, openai_gsm8k_931, openai_gsm8k_970, openai_gsm8k_995
```

## Guardrail cases (avoid regressions)

- **Structural commit v1 replay guardrails:** 188 rows from
  `outputs/structural_commit_v1_replay_20260508T120000Z/structural_commit_v1_replay_cases.csv`
  (`guardrail_*` cohorts). Any new retry must keep **0** correct→wrong flips on that set offline.
- **Present-not-selected fixed anchors:** continue to monitor `openai_gsm8k_1087`, `1279`, `1290`.

## Dry-run / offline first

- **Yes:** keyword scaffold router + manifest-only dry run using `problem_text` from union/bank CSV
  (no API): emit `planned_scaffold`, slot consumption, estimated tokens (rough).
- **No HF / no Cohere** for offline manifests.

## When Cohere API is needed

- After offline manifest review: **one** capped pilot on a 10–15 case anchor subset per family
  to measure real win rate and guardrail harm.

## Proposed manifest fields (pre-API)

- `case_id`, `source_artifact`, `derived_problem_family`, `derivation_confidence`
- `candidate_retry_scaffold`, `recommended_retry_prompt_family`
- `budget_schedule` (A or B), `slot_index`, `replaced_action_kind`
- `structural_commit_applied` (bool), `discovery_retry_eligible` (bool), `abstain_reason`

## Metrics

- Gold-absent primary: exact-match delta vs baseline PAL method on frozen 37-case list.
- Secondary: average tokens, scaffold distribution, guardrail flip count (must stay 0 initially).

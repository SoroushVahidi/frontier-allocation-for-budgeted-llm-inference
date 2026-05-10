# GSM8K structural validator — offline batch evaluation

> **Prefer `stratified_report.md` + `stratified_summary.json`** for fair metrics. Global gold vs non-gold means below mix `pal_trace_code` with `answer_only` rows.

Diagnostic run only; scores are **metadata** and do not prove downstream ranking quality.

- **Bundle:** `/home/soroush/research-next-wt/outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z`
- **Output:** `/home/soroush/research-next-wt/outputs/gsm8k_structural_validator_eval_20260507`

## Missing inputs

```json
[]
```

## Scale

- Candidate rows: **1296**
- Distinct cases: **228**

## Global separation (gold-matching vs non-gold candidate rows)

- Mean structural_score (gold-matching): **0.4734**
- Mean structural_score (non-gold): **0.6563**

## Separation by cohort

```json
{
  "guardrail_correct": {
    "mean_gold_matching": 0.5080574290567546,
    "n_gold_rows": 834,
    "mean_non_gold": 0.7838416265382558,
    "n_non_gold_rows": 89
  },
  "gold_absent_discovery": {
    "mean_gold_matching": 0.1823684210526316,
    "n_gold_rows": 38,
    "mean_non_gold": 0.5251791726791728,
    "n_non_gold_rows": 99
  },
  "other": {
    "mean_gold_matching": 0.0,
    "n_gold_rows": 0,
    "mean_non_gold": 0.64375,
    "n_non_gold_rows": 6
  },
  "present_not_selected": {
    "mean_gold_matching": 0.33799558080808084,
    "n_gold_rows": 132,
    "mean_non_gold": 0.6737159863945579,
    "n_non_gold_rows": 98
  }
}
```

## Present-not-selected

- Cases total (present_not_selected cohort): **23**
- Cases with ≥1 gold-matching candidate in emitted pool: **23**
- Comparable (scores present for wrong `current_final` and some gold alt): **23**
- Cases where some gold-matching candidate scored higher than wrong final: **0**
- Tie scores: **20**
- Missing score / no gold alt in pool: **0**
- Wrong final scored strictly higher than best gold alt (misleading signal): **3**

### Example helper cases (validator ranks gold alternative above wrong final)

```json
[]
```

### Example misleading cases

```json
[
  {
    "case_id": "openai_gsm8k_1083",
    "wrong_final_score": 0.7250000000000001,
    "best_gold_score": 0.23500000000000001,
    "wrong_answer": "605"
  },
  {
    "case_id": "openai_gsm8k_1299",
    "wrong_final_score": 0.8500000000000001,
    "best_gold_score": 0.1575,
    "wrong_answer": "5"
  },
  {
    "case_id": "openai_gsm8k_1307",
    "wrong_final_score": 0.7250000000000001,
    "best_gold_score": 0.0975,
    "wrong_answer": "21"
  }
]
```

## Guardrail (PAL + best external correct)

- `current_final` rows counted: **183**
- Fraction with ≥1 warning: **0.361**

## Top warning strings

```json
[
  [
    "unused_salient_problem_quantities",
    736
  ],
  [
    "low_quantity_coverage_vs_problem",
    608
  ],
  [
    "missing_operation_cue_in_trace_or_code:rate",
    375
  ],
  [
    "rate_question_weak_operator_evidence_in_trace",
    346
  ],
  [
    "missing_operation_cue_in_trace_or_code:temporal",
    263
  ],
  [
    "temporal_story_weak_follow_through_in_trace",
    162
  ],
  [
    "missing_operation_cue_in_trace_or_code:fraction",
    107
  ],
  [
    "comparison_question_weak_contrast_evidence_in_trace",
    88
  ],
  [
    "missing_operation_cue_in_trace_or_code:difference",
    82
  ],
  [
    "missing_operation_cue_in_trace_or_code:total",
    80
  ],
  [
    "aggregation_question_weak_total_evidence_in_trace",
    80
  ],
  [
    "money_context_but_answer_not_numeric",
    2
  ],
  [
    "target_type_vs_answer_surface_mismatch_heuristic",
    1
  ]
]
```

## Gold-absent discovery — common warnings on current_final / pal_stdout

```json
[
  [
    "missing_operation_cue_in_trace_or_code:fraction",
    7
  ],
  [
    "unused_salient_problem_quantities",
    7
  ],
  [
    "missing_operation_cue_in_trace_or_code:temporal",
    6
  ],
  [
    "missing_operation_cue_in_trace_or_code:rate",
    2
  ],
  [
    "rate_question_weak_operator_evidence_in_trace",
    2
  ]
]
```

## Track alignment (non-final judgment)

- **Track B (commitment / overlay):** usable only if calibrated; separation above is necessary but not sufficient.
- **Track A (discovery / retry):** warning clusters may seed triggers; watch guardrail false-positive rate.

**API:** not used.
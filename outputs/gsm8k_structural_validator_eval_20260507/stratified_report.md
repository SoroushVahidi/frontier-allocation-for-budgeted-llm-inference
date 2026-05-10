# Stratified GSM8K structural validator evaluation

Offline batch only; **no** selection wiring; **no** API.

## Evidence stratification

- **`pal_trace_code`:** trace and code both non-empty in the batch spec passed to `validate_gsm8k_candidate`.
- **`text_trace`:** trace without code.
- **`answer_only`:** no trace and no code (typical `external_answer`).
- **`score_family`:** `structural_trace_score` vs `answer_only_diagnostic` — same validator numeric field, **different interpretation**.

**Do not** rank PAL rows against externals using one pooled scalar — see `deprecated_legacy_global_means` in `stratified_summary.json`.

## Stratified gold vs non-gold means (within evidence class only)

```json
{
  "answer_only": {
    "mean_structural_score_gold_matching_rows": 0.269232186912594,
    "n_gold_matching_rows": 608,
    "mean_structural_score_non_gold_rows": 0.20722284226190477,
    "n_non_gold_rows": 64
  },
  "pal_trace_code": {
    "mean_structural_score_gold_matching_rows": 0.786477519941987,
    "n_gold_matching_rows": 394,
    "mean_structural_score_non_gold_rows": 0.7804729437229437,
    "n_non_gold_rows": 220
  },
  "text_trace": {
    "mean_structural_score_gold_matching_rows": 0.8500000000000001,
    "n_gold_matching_rows": 2,
    "mean_structural_score_non_gold_rows": 0.8343750000000001,
    "n_non_gold_rows": 8
  }
}
```

## PAL-internal present-not-selected (excludes `external_answer`)

- Cases with ≥1 internal gold alt: **20**
- Comparable cases: **20**
- Gold internal scored higher than wrong `current_final`: **0**
- Ties: **20**
- Misleading (wrong final higher): **0**
- Missing internal gold or score: **3**

## Guardrail `current_final` warning rates

- All evidence classes (**183** rows): **0.361**
- **`pal_trace_code` only** (**183** rows): **0.361**

## Track signal (diagnostic)

- **Track B:** Interpret **`pal_trace_code`** PN-internal deltas only; mixed evidence invalidated the first headline.
- **Track A:** Warning tags on **`pal_trace_code`** guardrail rows remain a plausible retry signal; rate drops when restricting to trace+code.

**API:** not used.
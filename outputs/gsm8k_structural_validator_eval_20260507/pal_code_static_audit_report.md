# PAL code static audit (Track A diagnostic)

Offline only — **no** API, **no** controllers, **no** selection.

## A. Why broad validator triggers were insufficient

Coarse regex cues (`temporal_cue_gap`, etc.) achieved **low recall** on gold-absent rows and **material guardrail FPs**. This audit inspects **PAL Python** directly for structural patterns (ops, literals vs problem quantities, opacity).

## B. PAL-code audit method

- Sources: `all_results.jsonl` + `selected_failure_cases.jsonl` (`pal_execution.pal_code`, stdout preview).
- **Problem quantities**: `_salient_problem_norms` (same as structural validator) — **no gold as checker input**.
- **Quantity coverage**: `validate_gsm8k_candidate` called with **problem + code + stdout preview** for the coverage field only.
- AST: literals, `+ - * / //`, `sum()`, subtraction binops, final `print`/`answer` snippet heuristics.

## C. Gold-absent vs guardrail code-feature comparison

```json
{
  "mean_quantity_coverage_gold_absent": 0.8244897959183672,
  "mean_quantity_coverage_guardrail": 0.9386666666666666,
  "mean_unused_salient_gold_absent": 0.8571428571428571,
  "mean_unused_salient_guardrail": 0.24,
  "mean_opaque_one_expr_gold_absent": 0.7142857142857143,
  "mean_opaque_one_expr_guardrail": 0.36
}
```

## D. Candidate static triggers

| Trigger | GA rate | Guardrail FP rate | Precision-like | Retry schema |
|---------|---------|-------------------|----------------|--------------|
| `many_unused_final_sparse` | **0.190** | **0.040** | **0.500** | quantity-grounding retry |
| `opaque_one_expr_low_coverage` | **0.048** | **0.000** | **0.250** | aggregation / decomposition retry |
| `rate_no_muldiv` | **0.143** | **0.000** | **0.600** | rate-equation retry |
| `syntax_exec_or_empty` | **0.095** | **0.000** | **0.500** | PAL repair / codegen retry |
| `temporal_no_state_no_sub` | **0.238** | **0.080** | **0.500** | state-table retry |
| `ungrounded_final_literal` | **0.000** | **0.000** | **0.000** | quantity-grounding retry |

## E. Promising / rejected triggers

- **Highest precision-like (among fired):** `rate_no_muldiv` (~**0.60**).
- **Highest guardrail FP rate:** `temporal_no_state_no_sub` (~**0.08** on this sample).

**Verdict:** Even the busiest trigger fires **≤10** times total here — too few events to claim a clear algorithmic win over coarse validator cues. Treat **`rate_no_muldiv`** precision-like (~0.60) as **hypothesis only**. **Pause** automatic Track A triggers until a larger PAL-code audit.

## F. Examples worth manual inspection

- **`openai_gsm8k_1115`:** unused_salient=4, opaque=True, cov=0.7142857142857143
- **`openai_gsm8k_1198`:** unused_salient=3, opaque=True, cov=0.4
- **`openai_gsm8k_1112`:** unused_salient=2, opaque=False, cov=0.6
- **`openai_gsm8k_1081`:** unused_salient=2, opaque=True, cov=0.5
- **`openai_gsm8k_1215`:** unused_salient=1, opaque=False, cov=0.8

## G. Relationship to Combinatorial Opt Agent verification

Same philosophy: **cheap structural checks** on candidate artifacts before expensive reasoning — here applied to **PAL code shape**.

## H. Whether to continue Track A PAL-code validator direction

**The static-analysis trigger path does not yet produce enough fired events** on this bundle to justify continuing toward runtime Track A policy — **pause** automation; optional **manual** review of `pal_code_static_audit.csv`.

## I. Exact next implementation query

> If any static trigger keeps precision-like **>** ~0.35 **and** guardrail FP **<** ~0.15 on **large** slices with **≥30** aggregate fires, prototype optional retry templates behind flags. On this tiny audit, **do not** enable automatic triggers.

**API:** not required.
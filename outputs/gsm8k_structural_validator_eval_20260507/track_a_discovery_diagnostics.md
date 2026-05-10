# Track A discovery diagnostics (GSM8K structural validator)

Offline telemetry only — **no** API, **no** controllers, **no** selection wiring.

**Bundle:** `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z`

## A. Why Track B ranking is paused

Mixed-evidence scoring and weak PAL-internal separation showed `structural_score` is **not** a reliable commitment ranker. See `stratified_report.md`. Track B scalar comparison is **paused** until evidence-normalized or pairwise designs exist.

## B. Track A diagnostic objective

Treat validator output as **Combinatorial-Opt-Agent-style tags**: detect missing quantity coverage, missing operation cues (rate/temporal/total/difference), target-type mismatches, and exec/syntax failures that might justify **targeted retry / richer trace** policies on **gold-absent discovery** failures.

## C. Gold-absent warning patterns

- **Preferred** gold-absent cases in this bundle: **11**
- **Secondary** (both-wrong style) gold-absent cases: **10**

Inspect per-case PAL `current_final` and `pal_stdout` rows in `track_a_discovery_diagnostics.csv` (warnings JSON, unused salient quantities, cues, coverage).

## D. Guardrail false positives

Guardrail cohort = PAL + best external **correct** (`all_casebook.csv`). Triggers are evaluated on **`current_final` only** for FP rates — correct answers should ideally **not** fire discovery retries.

## E. Candidate trigger-family table

| Trigger | Fire rate gold-absent | FP guardrail | Precision-like |
|---------|----------------------|--------------|----------------|
| `difference_contrast_cue_gap` | **0.000** (0/21) | **0.033** (6/183) | **0.000** |
| `exec_or_syntax_bad_plus_low_cov` | **0.000** (0/21) | **0.000** (0/183) | **0.000** |
| `low_cov_and_missing_operation_cue` | **0.000** (0/21) | **0.005** (1/183) | **0.000** |
| `rate_ratio_cue_gap` | **0.048** (1/21) | **0.071** (13/183) | **0.062** |
| `target_type_mismatch` | **0.000** (0/21) | **0.000** (0/183) | **0.000** |
| `temporal_cue_gap` | **0.143** (3/21) | **0.131** (24/183) | **0.094** |
| `total_aggregation_cue_gap` | **0.000** (0/21) | **0.011** (2/183) | **0.000** |

## F. Promising triggers, if any

- **`temporal_cue_gap`:** fires on **3/21** gold-absent cases (**14.3%** recall-like); guardrail FP **13.1%** (`24/183`).
- **`rate_ratio_cue_gap`:** fires on **1/21** gold-absent cases (**4.8%** recall-like); guardrail FP **7.1%** (`13/183`).
- **`target_type_mismatch`:** fires on **0/21** gold-absent cases (**0.0%** recall-like); guardrail FP **0.0%** (`0/183`).
- **`exec_or_syntax_bad_plus_low_cov`:** fires on **0/21** gold-absent cases (**0.0%** recall-like); guardrail FP **0.0%** (`0/183`).
**Interpretation:** No coarse trigger meets a strict **≥25% gold-absent recall & ≤25% guardrail FP** bar here. `temporal_cue_gap` shows the **strongest recall-like signal** among cue-gap families; treat as **soft** telemetry.

## G. Triggers to reject

- **`low_cov_and_missing_operation_cue`:** precision-like **0.00** when conditioned on fired — not gold-absent-targeted here.
- **`total_aggregation_cue_gap`:** precision-like **0.00** when conditioned on fired — not gold-absent-targeted here.
- **`difference_contrast_cue_gap`:** precision-like **0.00** when conditioned on fired — not gold-absent-targeted here.

## H. Relationship to Combinatorial Opt Agent

Same principle: **cheap offline structural checks** as telemetry; triggers are **hypotheses** for policy, not proof of missing reasoning. Precision/recall here are **approximate** on a small GSM8K bundle.

## I. Exact next implementation query

> Implement optional **retry/TRCE hooks** gated behind env flags: when trigger X fires on PAL `current_final` and cohort is gold-absent discovery, allocate budget to structured scratchpad (state table / rate equation / aggregation template). **Do not** change default selection. Add regression harness on this CSV archive.

**API:** not required for trigger evaluation.
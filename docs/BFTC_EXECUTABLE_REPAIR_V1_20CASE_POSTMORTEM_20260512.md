# BFTC Executable Repair v1 — 20-Case Postmortem
**Date:** 2026-05-12  
**Experiment:** `bftc_executable_repair_v1`  
**Live output:** `outputs/bftc_executable_repair_v1_live_20cases_20260512T221521Z`  
**Model:** Cohere `command-r-plus-08-2024`, temperature=0, max_tokens=2048  
**Casebook:** `docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv`  
**Analysis artifacts:** `bftc_executable_case_error_analysis.jsonl`, `bftc_executable_case_error_analysis.csv`  

---

## Executive Summary

The executable-repair pilot was mechanically perfect:

- `20/20` calls succeeded
- `20/20` JSON parse ok
- `20/20` schema ok
- `20/20` formulas present
- `20/20` formulas evaluated safely
- `0` formula safety rejections

But it did **not** improve exact recovery over BFTC-only:

- BFTC-only exact: `2/20`
- executable model final exact: `0/20`
- executable final exact: `2/20`
- union recovered across BFTC-only and executable final: `4/20`

The two executable wins were:

- `openai_gsm8k_1025`
- `openai_gsm8k_1027`

The two BFTC-only exact recoveries that execution lost were:

- `openai_gsm8k_1021`
- `openai_gsm8k_162`

The main finding is not formula safety failure. The main failure is that the formulas usually encoded the **wrong relation**, **wrong variable binding**, or both. A second important finding is that this 20-case slice contains **6 prompt/gold inconsistencies**, which confound exact-recovery scoring and make the raw `2/20` headline an underestimate of prompt-surface correctness in several cases.

---

## Summary Metrics

| Metric | Result |
|---|---|
| Calls attempted / succeeded | `20 / 20` |
| JSON parse ok | `20 / 20` |
| Schema ok | `20 / 20` |
| formula eval ok | `20 / 20` |
| formula eval errors | `0 / 20` |
| formula result mismatched model final | `13 / 20` |
| New executable candidates vs prior pool | `13 / 20` |
| BFTC-only exact | `2 / 20` |
| Executable model final exact | `0 / 20` |
| Executable final exact | `2 / 20` |
| Union recovered across BFTC-only and executable final | `4 / 20` |

Additional comparison signals from the case-level audit:

- executable final improved over BFTC-only on `6/20`
- executable final matched BFTC-only error on `3/20`
- executable final worsened vs BFTC-only on `11/20`
- among the `13` formula/model mismatches, execution improved over model final on only `3` and worsened on `10`

This means the problem was not “the formula branch rarely fired.” It fired every time. The problem is that replacing the verbal answer with the executable result was usually **not epistemically justified**.

---

## Per-Case Category Counts

| Primary category | Count | Cases |
|---|---:|---|
| `executable_recovered` | 2 | `openai_gsm8k_1025`, `openai_gsm8k_1027` |
| `bftc_only_recovered_but_execution_lost` | 2 | `openai_gsm8k_1021`, `openai_gsm8k_162` |
| `wrong_variable_binding_in_formula` | 3 | `openai_gsm8k_1003`, `openai_gsm8k_184`, `openai_gsm8k_233` |
| `ratio_or_percentage_base_error_in_formula` | 3 | `openai_gsm8k_1006`, `openai_gsm8k_166`, `openai_gsm8k_190` |
| `state_before_after_error_in_formula` | 2 | `openai_gsm8k_1029`, `openai_gsm8k_180` |
| `unit_or_scale_error_in_formula` | 1 | `openai_gsm8k_183` |
| `missing_source_fact_in_formula` | 1 | `openai_gsm8k_22` |
| `other` | 6 | `openai_gsm8k_1035`, `openai_gsm8k_1069`, `openai_gsm8k_213`, `openai_gsm8k_228`, `openai_gsm8k_239`, `openai_gsm8k_262` |

Grouped by broader failure axis:

- `relation_construction`: `9`
- `source_fact_extraction`: `2`
- `unit_scale`: `1`
- `arithmetic`: `2`
- `artifact_mismatch`: `6`

The dominant error type is therefore **relation construction**, not arithmetic execution and not formula safety.

---

## Special Focus Cases

### Executable wins

| case_id | BFTC-only | model final | executable final | gold | Why it worked |
|---|---:|---:|---:|---:|---|
| `openai_gsm8k_1025` | 20 | 20 | 23 | 23 | Formula corrected a multi-step counting slip while keeping the right target |
| `openai_gsm8k_1027` | 1.818 | 1.818 | 2 | 2 | Formula corrected the discounted cost-per-pair arithmetic |

These two wins validate the narrow original hypothesis: if the target and variables are right, execution can repair a local arithmetic slip.

### BFTC-only exact recoveries lost by execution

| case_id | BFTC-only | executable final | gold | What execution lost |
|---|---:|---:|---:|---|
| `openai_gsm8k_1021` | 8 | 16 | 8 | Omitted the 4-pages-per-sheet relation and replaced exact reasoning with `pages / 2` |
| `openai_gsm8k_162` | 50 | 90 | 50 | Dropped the Peter = Paul + John relation and collapsed to `combined_age - difference` |

These are the clearest demonstrations that execution without a relation verifier can destroy already-correct BFTC answers.

---

## Formula Mismatch Analysis

There were `13` cases where `solution_formula` did not equal the model’s own `final_answer`.

Breakdown:

- mismatch improved over model final: `3`
  - `openai_gsm8k_1025`
  - `openai_gsm8k_1027`
  - `openai_gsm8k_190`
- mismatch worsened relative to model final: `10`
  - `openai_gsm8k_1003`
  - `openai_gsm8k_1006`
  - `openai_gsm8k_1029`
  - `openai_gsm8k_1035`
  - `openai_gsm8k_1069`
  - `openai_gsm8k_166`
  - `openai_gsm8k_184`
  - `openai_gsm8k_228`
  - `openai_gsm8k_233`
  - `openai_gsm8k_239`

Interpretation:

1. The mismatch itself is useful signal.
2. Blindly trusting the executable branch is usually harmful.
3. The next infrastructure should not merely “execute if parsable.” It must judge whether the formula preserves the target relation better than the verbal answer.

This strongly supports adding:

- a `formula verifier`
- a `target-sensitive relation verifier`
- a `variable-dict rebinding selector`

before another live replacement policy is attempted.

---

## Formula Variable Sufficiency

Assessment over the 20 cases:

- `enough`: `8`
- `insufficient`: `6`
- `prompt_gold_inconsistent`: `5`
- `definite_mismatch_and_insufficient`: `1`

Interpretation:

- In only `8/20` cases did the `formula_variables` dictionary clearly contain enough numeric information to recover gold if the relation were corrected.
- In `6/20`, the variable dictionary itself was missing needed structure or used wrong derived values.
- In `6/20`, the prompt surface and casebook gold did not match cleanly enough to use the exact score as a pure formula-quality measure.

This means the answer to “did the variable dictionary often contain enough information to compute gold?” is:

**Partially, but not reliably.** It was often good enough for local arithmetic repair, but not good enough as a stable symbolic interface.

Gold-value leakage check:

- exact gold value present as some formula variable in `2/20`
- variable close to gold in `5/20`

These were not evidence of leakage. They were ordinary prompt-derived quantities, often coincidental and semantically unrelated to the target.

---

## Prompt/Gold Inconsistency Audit

The following cases appear to have **definite prompt/gold mismatch** when read directly from the prompted question text:

| case_id | Prompt-surface answer | Casebook gold | Notes |
|---|---:|---:|---|
| `openai_gsm8k_1035` | 25% | 193 | Prompt explicitly asks for a percentage |
| `openai_gsm8k_1069` | 41 | 191 | The stated scoring surface totals to 41 |
| `openai_gsm8k_213` | 28 | 24 | Park-fee arithmetic from the prompt totals to 28 |
| `openai_gsm8k_228` | 1128 | 127 | Four-week TikTok time from the prompt is far larger than 127 |
| `openai_gsm8k_239` | 64800 | 13 | The prompt explicitly asks for a month-long revenue delta |
| `openai_gsm8k_262` | 24 | 23 | Prompt arithmetic does not land on the casebook gold |

This does **not** mean executable repair succeeded on these cases. Some formulas were still wrong. It does mean the raw `2/20` exact count is not a clean measure of whether the prompted formula branch was doing the right thing on the exact task surface it was given.

---

## Research Questions

### 1. Did executable repair fail because formulas were mathematically unsafe, or because formulas encoded wrong relations?

Wrong relations. Safety was not the problem.

Evidence:

- `20/20` formula eval ok
- `0/20` safety rejections
- dominant category count is relation-construction failure

### 2. Did the formula_variables dictionary often contain enough information to compute gold?

Only partially.

- clear yes: `8/20`
- clear no: `6/20`
- confounded by prompt/gold inconsistency: `6/20`

The dictionary was useful for local arithmetic correction in the two wins, but not reliable enough to support unconditional execution.

### 3. Did execution create useful new candidates even when not exact?

Yes, but weakly.

- `13/20` executable results were new relative to the prior pool
- `6/20` executable results improved over BFTC-only by absolute error
- only `2/20` became exact

So execution did add candidate diversity, but the average new candidate quality was too low to justify direct promotion.

### 4. What does the next fix need?

Priority order:

1. **D. target-sensitive relation verifier**
2. **B. formula verifier**
3. **E. variable-dict rebinding selector**
4. **C. declarative equation branch**

Not recommended as the next step:

- **A. stricter formula prompt only**
  - prompt tightening alone will not fix prompt/gold inconsistency, missing relations, or wrong derived bindings
- **F. abandon BFTC/execution and move to learned edge policy**
  - this pilot still showed two real arithmetic-repair wins and useful diagnostic signal

### 5. Is another live API run justified after only prompt changes?

No.

The next step should be **offline formula-verification / relation-verification infrastructure**, not another prompt-only live rerun.

Rationale:

- execution already fires reliably
- the failure is in *what* gets encoded, not in parseability
- unconditional substitution from formula to final answer is often harmful
- the slice contains prompt/gold inconsistencies that should be audited before using it as a live regression target again

---

## Recommended Next Method

Recommended next method:

**BFTC + relation-verifier + formula-verifier + variable-dict rebinding selector**

Concrete offline agenda:

1. Build a no-API verifier that checks whether a formula preserves the requested target relation, not just whether it evaluates.
2. Add a rebinding pass over `formula_variables` to detect obviously wrong derived bindings such as bad day counts, inverted conversion factors, and invented state variables.
3. Separate prompt/gold inconsistency cases from genuine method failures before using this slice as the main gating set again.
4. Re-score the 20 cases under:
   - BFTC-only answer
   - model final answer
   - executable final answer
   - verifier-selected best of model vs executable

Only after that offline infrastructure exists should another live run be considered.

---

## Bottom Line

- Executable repair did **not** beat BFTC-only on this 20-case slice.
- The failure was **not** formula safety.
- The dominant failure was **wrong relation / wrong binding**, plus a significant prompt/gold inconsistency confound.
- Another live run is **not justified now**.
- The next step should be **offline formula and relation verification infrastructure**, not prompt-only iteration.

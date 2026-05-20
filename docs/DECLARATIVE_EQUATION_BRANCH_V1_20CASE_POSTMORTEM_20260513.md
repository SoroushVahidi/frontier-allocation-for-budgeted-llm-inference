# Declarative Equation Branch v1 — 20-Case Postmortem
**Date:** 2026-05-13  
**Experiment:** `declarative_equation_branch_v1`  
**Live output:** `outputs/declarative_equation_branch_v1_live_20cases_20260513T001028Z`  
**Model:** Cohere `command-r-plus-08-2024`, temperature=0, max_tokens=2048  
**Casebook:** `docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv`  
**Analysis artifacts:** `declarative_case_error_analysis.jsonl`, `declarative_case_error_analysis.csv`  

---

## Executive Summary

The live pilot produced a small coverage gain but not a structurally clean branch. Exact recovery improved from `2/20` in both BFTC-only and executable-repair to `3/20` here, and the branch added `11/20` executable candidates not already in the prior pool. But `schema_ok` fell to `0/20`, and that zero is a mixture of two different problems:

1. **Validator artifact in relations:** `unknown_relation_variable` is likely a false-positive validator artifact in `15/20` cases, mostly because ordinary English relation prose was tokenized as undeclared variables.
2. **Real structural failures in equations/formulas:** even after relaxing relation validation conservatively, only `2/20` cases remain fully clean on parse + relation + equation + formula + target-match checks.

So the branch did not fail because declarative reasoning is useless. It failed because the current prompt and validator are misaligned: relations are written as natural-language summaries, while equations and formulas often introduce undeclared derived variables or malformed numeric literals.

The safe interpretation is: **marginal candidate-generation improvement, but no justification for another live run until validator cleanup and prompt/schema tightening are done first.**

---

## Main Questions

### 1. Why is `schema_ok = 0/20` despite strong field presence?

- Because field presence is not the bottleneck. `18/20` rows had relations, equations, and target matching, but the validator then rejected them for relation-token unknowns, undeclared equation variables, parse failures from non-JSON numeric literals, or formula evaluation failures.
- Under the current strict validator: `strict_schema_ok_count = 0`.
- Under conservative relation relaxation only: `relaxed_relation_schema_ok_count = 16`.
- Under relation relaxation while keeping equation/formula/target strict: `full_relaxed_structural_ok_count = 2`.

### 2. Are `unknown_relation_variable` counts mostly true errors?

- Mostly no. `15/20` cases look like false positives from relation prose or punctuation tokenization.
- The clear true-positive relation cases are the ones that place undeclared derived snake_case variables directly into relation strings, especially `openai_gsm8k_1006` and `openai_gsm8k_213`.
- Cases like `openai_gsm8k_1021`, `openai_gsm8k_1025`, `openai_gsm8k_162`, `openai_gsm8k_184`, and `openai_gsm8k_239` are structurally understandable relations that the validator penalized only because they were phrased in English.

### 3. Are `unknown_equation_variable` counts true equation errors?

- Mostly yes. These are usually undeclared derived variables such as `total_bill`, `total_contacts`, `final_value`, `money_made_widgeteer`, or `share_first_person` appearing in equations or solution formulas without corresponding entries in `variables`.
- This is not a validator artifact. It is a real interface mismatch between the prompt contract and the model outputs.

### 4. Which validation rules should stay strict?

- `parse_ok`: responses still need to be valid JSON.
- `target_variable == solve_for`: this stayed useful and already hit `18/20`.
- `solution_formula` AST safety and evaluability: keep strict.
- equation variable declaration for `equations` and `solution_formula`: keep strict.
- numeric final/formula agreement when both are present: keep strict as a diagnostic and gating signal.

### 5. Which validation rules should be relaxed or split?

- Split **relation quality** from **equation quality**.
- Do not tokenize plain English relation sentences into undeclared variables.
- Allow a softer relation diagnostic that checks presence and topical relevance, while reserving hard undeclared-variable failures for equation-like relation strings or explicit identifier references.
- Consider a targeted prompt tweak requiring that every derived symbol used in equations or formulas either appears in `variables` or is expanded inline.

### 6. Did declarative equation improve candidate-pool coverage despite `schema_ok = 0/20`?

- Yes, but only marginally. The branch produced `11/20` new executable candidates and raised exact recovery from `2/20` to `3/20`.
- That is a real, bounded signal on this 20-case slice, not a promotion result.

### 7. Which cases recovered gold, and why?

- `openai_gsm8k_1021`: exact via declarative final/executable answer. The model recovered the gold answer exactly; schema failure is from relation prose being tokenized as undeclared variables.
- `openai_gsm8k_1025`: exact via declarative final/executable answer. Gold was recovered exactly, but the target variable was used as a derived equation symbol without being declared in variables.
- `openai_gsm8k_184`: exact via declarative final/executable answer. Gold was recovered exactly, but equations inlined unit words like pounds, calories, and days instead of using declared variable names only.

### 8. Which cases were near misses?

- `openai_gsm8k_162`: near miss under 20% relative error. Schema failure is a relation-tokenization artifact, but the solved system still misses one relation and lands on 45 instead of 50.
- `openai_gsm8k_190`: near miss under 20% relative error. The share equations are internally inconsistent and the closed-form denominator is wrong; undeclared target-side symbols remain in equations.
- `openai_gsm8k_213`: near miss under 20% relative error. The prompt-surface arithmetic is 28, so the casebook gold 24 is inconsistent; relation and equation fields also used undeclared derived cost variables.

### 9. How do failures line up with topology labels?

- `arithmetic_precision`: `3` cases -> openai_gsm8k_1025, openai_gsm8k_1027, openai_gsm8k_166
- `final_after_process`: `4` cases -> openai_gsm8k_1029, openai_gsm8k_184, openai_gsm8k_22, openai_gsm8k_233
- `prompt_gold_inconsistent`: `5` cases -> openai_gsm8k_1035, openai_gsm8k_1069, openai_gsm8k_213, openai_gsm8k_228, openai_gsm8k_239
- `relation_composition_missing`: `7` cases -> openai_gsm8k_1003, openai_gsm8k_1006, openai_gsm8k_1021, openai_gsm8k_162, openai_gsm8k_180, openai_gsm8k_190, openai_gsm8k_262
- `unit_conversion`: `1` cases -> openai_gsm8k_183

Interpretation:
- `relation_composition_missing` remains the main genuine generation bottleneck.
- `final_after_process` cases often combined process/state mistakes with undeclared derived variables.
- `arithmetic_precision` was not the main issue here; two of those three cases were blocked more by malformed declarations than by arithmetic itself.
- `unit_conversion` appeared only once and was mixed with malformed JSON output.
- `prompt_gold_inconsistent` affected five clear cases, with `openai_gsm8k_262` also showing a definite mismatch signal even though its topology label stayed under relation composition.

### 10. What does the result justify next?

- **A. validator cleanup only:** necessary, but not sufficient.
- **B. prompt/schema revision:** necessary.
- **C. declarative_equation_branch_v2:** justified only after A+B, not before.
- **D. relation verifier:** justified as a no-API design target, because true misses cluster around relation composition and derived-symbol discipline.
- **E. no further live tests on this slice until prompt/gold inconsistencies are removed:** yes.

---

## Strict vs Relaxed Validation Summary

| Metric | Count |
|---|---:|
| `strict_schema_ok_count` | `0` |
| `relaxed_relation_schema_ok_count` | `16` |
| `equation_strict_ok_count` | `5` |
| `formula_strict_ok_count` | `12` |
| `target_solve_for_match_count` | `18` |
| `parse_ok_count` | `18` |
| `final_answer_count` | `16` |
| `executable_answer_count` | `16` |
| `model_final_exact_count` | `3` |
| `executable_final_exact_count` | `3` |
| `full_relaxed_structural_ok_count` | `2` |

Interpretation: relation relaxation alone fixes the headline `0/20`, but it does not make the branch robust. The remaining bottleneck is undeclared derived variables plus two malformed-JSON cases.

---

## Per-Category Counts

### Recommended Fix Category

| Category | Count |
|---|---:|
| `validator_relaxation` | `1` |
| `prompt_schema_tightening` | `4` |
| `equation_generation_failure` | `8` |
| `formula_generation_failure` | `1` |
| `prompt_gold_inconsistent` | `6` |
| `no_fix` | `0` |

### Parse Failures

- `json_parse_failed`: `2` -> openai_gsm8k_166, openai_gsm8k_183
- Both parse failures were caused by arithmetic expressions like `2/3` or `1/12` being emitted as raw JSON values instead of numeric literals.

### Validator Artifact Counts

- Cases with likely false-positive relation-token failures: `15` -> openai_gsm8k_1003, openai_gsm8k_1021, openai_gsm8k_1025, openai_gsm8k_1027, openai_gsm8k_1029, openai_gsm8k_1035, openai_gsm8k_1069, openai_gsm8k_162, openai_gsm8k_180, openai_gsm8k_184, openai_gsm8k_190, openai_gsm8k_22, openai_gsm8k_233, openai_gsm8k_239, openai_gsm8k_262
- Cases that become structurally clean just by relaxing relation validation while keeping equation/formula/target strict: `2` -> openai_gsm8k_1021, openai_gsm8k_162

---

## 20-Case Table

| case_id | topology | gold | final | exec | final_exact | exec_exact | parse | rel | eq | target | formula | unk_rel | unk_eq | rel_artifact | fix |
|---|---|---:|---:|---:|---|---|---|---|---|---|---|---:|---:|---|---|
| `openai_gsm8k_1003` | `relation_composition_missing` | `20` | `None` | `None` | `false` | `false` | `true` | `true` | `true` | `true` | `false` | `14` | `0` | `true` | `equation_generation_failure` |
| `openai_gsm8k_1006` | `relation_composition_missing` | `25` | `61.0` | `61.0` | `false` | `false` | `true` | `true` | `true` | `true` | `true` | `2` | `2` | `false` | `equation_generation_failure` |
| `openai_gsm8k_1021` | `relation_composition_missing` | `8` | `8.0` | `8.0` | `true` | `true` | `true` | `true` | `true` | `true` | `true` | `12` | `0` | `true` | `validator_relaxation` |
| `openai_gsm8k_1025` | `arithmetic_precision` | `23` | `23.0` | `23.0` | `true` | `true` | `true` | `true` | `true` | `true` | `true` | `17` | `1` | `true` | `prompt_schema_tightening` |
| `openai_gsm8k_1027` | `arithmetic_precision` | `2` | `1.0` | `1.0` | `false` | `false` | `true` | `true` | `true` | `true` | `false` | `31` | `3` | `true` | `equation_generation_failure` |
| `openai_gsm8k_1029` | `final_after_process` | `70000` | `195000.0` | `195000.0` | `false` | `false` | `true` | `true` | `true` | `true` | `true` | `11` | `2` | `true` | `equation_generation_failure` |
| `openai_gsm8k_1035` | `prompt_gold_inconsistent` | `193` | `25.0` | `25.0` | `false` | `false` | `true` | `true` | `true` | `true` | `true` | `23` | `1` | `true` | `prompt_gold_inconsistent` |
| `openai_gsm8k_1069` | `prompt_gold_inconsistent` | `191` | `41.0` | `41.0` | `false` | `false` | `true` | `true` | `true` | `true` | `false` | `25` | `4` | `true` | `prompt_gold_inconsistent` |
| `openai_gsm8k_162` | `relation_composition_missing` | `50` | `45.0` | `45.0` | `false` | `false` | `true` | `true` | `true` | `true` | `true` | `14` | `0` | `true` | `equation_generation_failure` |
| `openai_gsm8k_166` | `arithmetic_precision` | `15` | `None` | `None` | `false` | `false` | `false` | `false` | `false` | `false` | `false` | `0` | `0` | `false` | `prompt_schema_tightening` |
| `openai_gsm8k_180` | `relation_composition_missing` | `8` | `20.0` | `29.0` | `false` | `false` | `true` | `true` | `true` | `true` | `true` | `19` | `1` | `true` | `formula_generation_failure` |
| `openai_gsm8k_183` | `unit_conversion` | `40` | `None` | `None` | `false` | `false` | `false` | `false` | `false` | `false` | `false` | `0` | `0` | `false` | `prompt_schema_tightening` |
| `openai_gsm8k_184` | `final_after_process` | `525` | `525.0` | `525.0` | `true` | `true` | `true` | `true` | `true` | `true` | `true` | `20` | `3` | `true` | `prompt_schema_tightening` |
| `openai_gsm8k_190` | `relation_composition_missing` | `420` | `460.0` | `460.0` | `false` | `false` | `true` | `true` | `true` | `true` | `true` | `12` | `1` | `true` | `equation_generation_failure` |
| `openai_gsm8k_213` | `prompt_gold_inconsistent` | `24` | `28.0` | `28.0` | `false` | `false` | `true` | `true` | `true` | `true` | `true` | `3` | `3` | `false` | `prompt_gold_inconsistent` |
| `openai_gsm8k_22` | `final_after_process` | `291` | `108.0` | `108.0` | `false` | `false` | `true` | `true` | `true` | `true` | `false` | `20` | `0` | `true` | `equation_generation_failure` |
| `openai_gsm8k_228` | `prompt_gold_inconsistent` | `127` | `580.0` | `580.0` | `false` | `false` | `true` | `true` | `true` | `true` | `false` | `0` | `0` | `false` | `prompt_gold_inconsistent` |
| `openai_gsm8k_233` | `final_after_process` | `21` | `636.0` | `636.0` | `false` | `false` | `true` | `true` | `true` | `true` | `true` | `20` | `1` | `true` | `equation_generation_failure` |
| `openai_gsm8k_239` | `prompt_gold_inconsistent` | `13` | `64800.0` | `64800.0` | `false` | `false` | `true` | `true` | `true` | `true` | `true` | `21` | `2` | `true` | `prompt_gold_inconsistent` |
| `openai_gsm8k_262` | `relation_composition_missing` | `23` | `None` | `None` | `false` | `false` | `true` | `true` | `true` | `true` | `false` | `11` | `2` | `true` | `prompt_gold_inconsistent` |

Detailed diagnosis text for each row is in `declarative_case_error_analysis.jsonl` and `.csv`.

---

## Recommended Next Method

1. Commit the one-line prompt hygiene patch separately; it is a valid safety fix and already proved necessary for the literal gate.
2. Do no further live runs on this slice until prompt/gold inconsistencies are removed from the evaluation subset or explicitly carved out.
3. Build a no-API `declarative_equation_branch_v2` spec that does three things:
   - forces decimal JSON literals for all numeric `value` fields
   - requires every derived symbol used in `equations` or `solution_formula` to appear in `variables`
   - separates `relations` into prose-only semantic descriptions and keeps algebra exclusively in `equations`
4. Clean the validator so relation prose is a soft diagnostic, not a hard undeclared-variable failure.
5. Only after that, consider a new capped live run; the current evidence does not justify another live pilot now.

## Safe Claims

- Declarative equation branching produced a marginal 20-case improvement (`3/20` exact vs `2/20` previously) and `11/20` new executable candidates.
- The main reason for `schema_ok = 0/20` is not lack of relation/equation presence; it is misalignment between prompt, validator, and generated derived symbols.
- `unknown_relation_variable` is mostly a validator artifact on this slice, while `unknown_equation_variable` is mostly a real contract violation.
- Another live run is not justified until validator cleanup, prompt/schema revision, and prompt/gold inconsistency cleanup are completed.


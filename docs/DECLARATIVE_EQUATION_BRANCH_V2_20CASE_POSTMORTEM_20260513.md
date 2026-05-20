# Declarative Equation Branch v2 - 20-Case Postmortem
**Date:** 2026-05-13  
**Experiment:** `declarative_equation_branch_v2`  
**Live output:** `outputs/declarative_equation_branch_v2_live_20cases_20260513T004717Z`  
**Model:** Cohere `command-r-plus-08-2024`, temperature=0, max_tokens=2048  
**Casebook:** `docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv`  
**Analysis artifacts:** `declarative_v2_case_error_analysis.jsonl`, `declarative_v2_case_error_analysis.csv`, `declarative_v2_normalization_summary.json`  

## Executive Summary

`declarative_equation_branch_v2` did not recover the target slice. The live pilot produced 20/20 successful calls and 20/20 JSON parses, but only **1/20 executable exact recovery** and **0/20 model-final exact recovery**. The strongest signal is not a relation-prose validator problem anymore: v2 largely removed the v1 relation-token false positives, yet the remaining failures are dominated by semantically wrong equations/formulas rather than pure schema noise.

A conservative offline normalization pass repaired some mechanical defects, but it did not change the core conclusion. The normalized executable exact count stayed at **1/20**, so the live run is still a no-go for another v2 pilot in its current form.

## Files Read

- `outputs/declarative_equation_branch_v2_live_20cases_20260513T004717Z/manifest.json`
- `outputs/declarative_equation_branch_v2_live_20cases_20260513T004717Z/pilot_summary.json`
- `outputs/declarative_equation_branch_v2_live_20cases_20260513T004717Z/live_report.md`
- `outputs/declarative_equation_branch_v2_live_20cases_20260513T004717Z/raw_responses.jsonl`
- `outputs/declarative_equation_branch_v2_live_20cases_20260513T004717Z/parsed_responses.jsonl`
- `outputs/declarative_equation_branch_v2_live_20cases_20260513T004717Z/declarative_candidate_rows.jsonl`
- `outputs/declarative_equation_branch_v1_live_20cases_20260513T001028Z/declarative_case_error_analysis.csv`
- `outputs/missing_gold_topology_v1_20260512T231758Z/missing_gold_topology_rows.jsonl`
- `docs/DECLARATIVE_EQUATION_BRANCH_V1_20CASE_POSTMORTEM_20260513.md`
- `docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv`

## Outcome At A Glance

| Metric | Count |
|---|---:|
| Calls attempted / succeeded | `20/20` |
| JSON parse ok | `20/20` |
| `schema_ok` | `2/20` |
| `relation_present_count` | `20/20` |
| `equation_present_count` | `20/20` |
| `equation_strict_ok_count` | `15/20` |
| `formula_strict_ok_count` | `10/20` |
| `target_solve_for_match_count` | `19/20` |
| `solve_for_declared_count` | `11/20` |
| `numeric_variable_value_ok_count` | `20/20` |
| `formula_eval_ok_count` | `10/20` |
| `final_answer_extracted_count` | `17/20` |
| `executable_final_answer_count` | `17/20` |
| `gold_recovered_by_final_answer_count` | `0/20` |
| `gold_recovered_by_executable_answer_count` | `1/20` |

Comparison baseline:

- BFTC-only exact: `2/20`
- BFTC executable exact: `2/20`
- declarative v1 exact: `3/20`
- prior candidate oracle: `5/20`
- declarative v2 executable exact: `1/20`
- declarative v2 model-final exact: `0/20`

## Core Answer

The run failed mostly because the generated relations/equations were semantically wrong, not because the schema was merely too strict.

Evidence:

- v2 removed the v1-style relation prose false positives.
- 11/20 cases had a mechanically repairable schema defect under conservative normalization, but those repairs did not turn the slice into an exact-recovery slice.
- Only one formula evaluation error became evaluable under normalization, and it still stayed wrong.
- The exact answer set shrank from `3/20` in v1 to `1/20` in v2.

## Normalization Experiment

Conservative normalization rules applied offline:

- add a synthetic declaration when `solve_for` is missing, using the target symbol only as a placeholder and never inventing numeric values
- strip a purely syntactic `lhs =` wrapper from `solution_formula`
- normalize simple case/punctuation variants of variable names
- do not invent numeric values
- do not use gold to choose the rewrite

Results:

| Metric | Count |
|---|---:|
| Original executable exact | `1` |
| Normalized executable exact | `1` |
| Original formula-evaluable cases | `10` |
| Normalized formula-evaluable cases | `11` |
| Formula eval errors fixed by normalization | `1` |
| `solve_for`-not-declared cases | `9` |
| `solve_for`-not-declared cases repairable by normalization | `9` |
| Target-symbol equation aliases repairable by normalization | `4` |
| Normalization made formula evaluable but still wrong | `1` |
| Loose upper bound if selecting among original final answer, executable answer, normalized executable answer, and declared variable values | `3` |

Interpretation:

- Mechanical schema repair exists, but it is not the main missing piece.
- The live run is not bottlenecked by one validator quirk.
- Normalization does not create new exact answers beyond the single exact executable recovery already present.
- Two extra values in the loose upper bound come from declared variables that happen to match gold numerically, but they are not valid answer sources.

## Per-Case Classification

| Case | Topology | Primary label | Mechanical? | V1 -> V2 note |
|---|---|---|---|---|
| `openai_gsm8k_1003` | `relation_composition_missing` | `equation_semantically_wrong` | `false` | semantically wrong remains |
| `openai_gsm8k_1006` | `relation_composition_missing` | `equation_semantically_wrong` | `true` | semantically wrong remains |
| `openai_gsm8k_1021` | `relation_composition_missing` | `formula_semantically_wrong` | `false` | regressed from exact in v1 |
| `openai_gsm8k_1025` | `arithmetic_precision` | `exact_recovered` | `true` | exact in both |
| `openai_gsm8k_1027` | `arithmetic_precision` | `formula_semantically_wrong` | `false` | semantically wrong remains |
| `openai_gsm8k_1029` | `final_after_process` | `equation_semantically_wrong` | `true` | semantically wrong remains |
| `openai_gsm8k_1035` | `prompt_gold_inconsistent` | `prompt_gold_inconsistent` | `true` | semantically wrong remains |
| `openai_gsm8k_1069` | `prompt_gold_inconsistent` | `prompt_gold_inconsistent` | `true` | semantically wrong remains |
| `openai_gsm8k_162` | `relation_composition_missing` | `equation_semantically_wrong` | `false` | semantically wrong remains |
| `openai_gsm8k_166` | `arithmetic_precision` | `formula_syntax_failure` | `true` | v2 improved structurally but remained non-exact |
| `openai_gsm8k_180` | `relation_composition_missing` | `equation_semantically_wrong` | `true` | semantically wrong remains |
| `openai_gsm8k_183` | `unit_conversion` | `formula_semantically_wrong` | `false` | v2 improved structurally but remained non-exact |
| `openai_gsm8k_184` | `final_after_process` | `equation_semantically_wrong` | `true` | regressed from exact in v1 |
| `openai_gsm8k_190` | `relation_composition_missing` | `equation_semantically_wrong` | `false` | semantically wrong remains |
| `openai_gsm8k_213` | `prompt_gold_inconsistent` | `prompt_gold_inconsistent` | `false` | semantically wrong remains |
| `openai_gsm8k_22` | `final_after_process` | `equation_semantically_wrong` | `false` | semantically wrong remains |
| `openai_gsm8k_228` | `prompt_gold_inconsistent` | `solve_for_not_declared_only` | `true` | semantically wrong remains |
| `openai_gsm8k_233` | `final_after_process` | `unknown_equation_variable_mechanical` | `true` | semantically wrong remains |
| `openai_gsm8k_239` | `prompt_gold_inconsistent` | `prompt_gold_inconsistent` | `true` | semantically wrong remains |
| `openai_gsm8k_262` | `relation_composition_missing` | `other` | `false` | semantically wrong remains |

## Mechanical vs Semantic

| Bucket | Cases |
|---|---:|
| Mechanically repairable offline | `11` |
| Semantic / inconsistent / other | `9` |

This is the central result: the slice has some offline-repairable structure, but the majority of the remaining loss is semantic, not validator noise.

## v1 vs v2

### Improved cases

- `openai_gsm8k_166`: v1 had a parsing failure; v2 parses cleanly, but the answer is still wrong.
- `openai_gsm8k_183`: v1 had a parsing failure; v2 is syntactically valid and evaluable, but still wrong.

### Regressed cases

- `openai_gsm8k_1021`: v1 recovered the exact gold 8; v2 regressed to a coherent but incorrect 16.
- `openai_gsm8k_184`: exact recovery in v1 was lost in v2.
- `openai_gsm8k_1025`: exact executable recovery is preserved, but the model-final field regressed.

### Stable non-exacts

The rest of the slice stayed wrong or inconsistent, even when the schema was repaired.

## Safe Conclusion

- v2 reduced relation-validation false positives.
- v2 did **not** improve candidate accuracy.
- The stricter schema did not solve the real bottleneck and may have exposed it more clearly.
- Another live declarative v2 run is **not** justified in the current form.

## Recommended Next Method

`relation verifier`

Rationale:

- the remaining errors are mostly semantic equation/relation mistakes
- the live run already shows that more schema pressure alone does not buy exact recovery
- a verifier is a better next no-API target than another prompt-only live pilot

## Commit Guidance

- A docs-only commit for this postmortem would be reasonable.
- No prompt hygiene commit is needed from this analysis alone.
- If you later commit generated artifacts, keep the doc separate from the output JSON/CSV files.

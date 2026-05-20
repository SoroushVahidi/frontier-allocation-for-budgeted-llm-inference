# BFTC Candidate Rebinding Selector v1 Analysis
**Date:** 2026-05-12  
**Output directory:** `/home/soroush/frontier-allocation-for-budgeted-llm-inference/outputs/bftc_candidate_rebinding_selector_v1_20260512T224257Z`  
**Mode:** offline / no-API

## Motivation

The BFTC executable-repair pilot showed that formulas executed safely but usually encoded the wrong relation or variable binding. This analysis asks a narrower offline question: if we union the candidates already available from BFTC-only, executable-repair finals, executable formula outputs, and formula-variable values, how much selector headroom is present without another model call?

## Input Pilots

- `outputs/bftc_live_pilot_v1_20cases_20260512T210634Z`
- `outputs/bftc_executable_repair_v1_live_20cases_20260512T221521Z`
- `docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv`
- `outputs/bftc_executable_repair_v1_live_20cases_20260512T221521Z/bftc_executable_case_error_analysis.jsonl`

## Candidate Set Construction

Per case, the candidate set unions:

- BFTC-only final answer
- executable-repair model final answer
- executable formula final answer
- numeric values from `formula_variables`
- any top-level repaired-candidate / final-answer fields that were numeric

Candidates are deduplicated numerically, while provenance is preserved.

## Feature Definitions

For each candidate, the analysis records:

- provenance type(s)
- whether the candidate equals a formula-variable value
- lexical overlap between variable name/description and the requested target
- unit match between variable unit and target/question text
- whether the candidate came from the executable formula
- whether the candidate came from the BFTC-only final
- whether the postmortem marks the relation category as suspicious
- whether the case is prompt/gold inconsistent

Gold is attached only after candidate construction for offline labels and reporting.

## Selector Results

| Selector | Exact |
|---|---:|
| `prefer_bftc_only_final` | `2/20` |
| `prefer_exec_formula_final` | `2/20` |
| `prefer_model_final` | `0/20` |
| `prefer_variable_with_target_overlap` | `0/20` |
| `prefer_non_prompt_inconsistent_best_target_overlap` | `0/20` |
| `oracle_upper_bound` | `5/20` |

## Oracle Upper Bound

- Gold appears somewhere in the combined candidate set for `5/20` cases.
- Oracle upper bound: `5/20`
- Variable-rebinding recoverable without another model call: `1` cases

## Prompt/Gold Inconsistency Effect

- Prompt/gold inconsistent cases: `6`
- Inconsistent but still oracle-recoverable: `0`
- Inconsistent and unrecoverable/misleading: `6`

This means the 20-case slice should not be reused as a clean live gating set without first separating provenance-clean cases from prompt/gold mismatches.

## Recommendation

- Do not build the current heuristic rebinding selector directly into runtime yet.
- Clean or quarantine the 6 prompt/gold inconsistent cases before more live tests.
- The next live candidate should be `relation-verifier + formula-verifier`, not a prompt-only rerun.
- A rebinding selector is still worth building offline, because the combined candidate pool exceeds the 4/20 union recovered by direct system outputs alone whenever gold lands in a formula-variable value.

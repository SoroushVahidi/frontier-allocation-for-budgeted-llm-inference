# Target-Variable Dict PAL Branch v1 — Specification
**Date:** 2026-05-12  
**Experiment ID:** target_variable_dict_pal_branch_v1  
**Status:** Preflight only — no live API calls until evidence threshold is met  

---

## Motivation

The dominant failure mode in the wrong-supported-consensus-97 slice is **final-target binding failure**: the frontier generates candidates that are internally coherent but answer a different quantity than asked. PAL code helps with arithmetic correctness but still fails when the final assignment (`print(result)`) binds to the wrong intermediate variable.

This branch adds an explicit **target-variable dictionary** layer:
- The model must name the final target as a semantic variable (`daily_profit`, not `x`).
- It must list all intermediate variables with descriptions and units.
- It must explicitly reject tempting nearby non-final values.
- It must confirm that `answer_variable_name == target_variable_name`.

This addresses the structural gap identified by `frontier_next_edge_policy_v1`:
- 61/97 gold-absent cases require a verifier/backward-target-check branch.
- PAL alone binds to the wrong final variable in those cases.

---

## Output Schema

The model must return a single valid JSON object with **exactly** these fields:

```json
{
  "problem_summary": "<one sentence: what is being computed>",
  "target_question": "<verbatim or paraphrased quantity being asked>",
  "target_variable_name": "<semantic name, e.g. daily_profit, items_per_box>",
  "target_unit": "<unit or type, e.g. dollars, items, percent>",
  "variables": [
    {
      "name": "<semantic_variable_name>",
      "description": "<what this variable represents>",
      "unit": "<unit or type>",
      "expression": "<arithmetic expression or formula used>",
      "value": "<numeric result>"
    }
  ],
  "rejected_non_final_variables": [
    "<semantic name of a tempting but wrong intermediate>"
  ],
  "answer_variable_name": "<must equal target_variable_name>",
  "final_answer": "<bare integer or decimal — no $, %, commas, or units>"
}
```

### Field rules

| Field | Rule |
|-------|------|
| `target_variable_name` | Concise snake_case; not generic (`x`, `answer`, `result`, `val`) |
| `variables[*].name` | Concise snake_case; must include the target variable as the **last** entry |
| `answer_variable_name` | Must exactly equal `target_variable_name` AND the `name` field of the last entry in `variables[]`. No synonyms, aliases, or alternate spellings. |
| `rejected_non_final_variables` | At least one entry when a tempting intermediate exists |
| `final_answer` | Bare integer or decimal; no `$`, `%`, commas, units, or string wrapping |

---

## Prompt Rules

- **No gold leakage**: prompt must not include `gold_answer`, `answer_key`, hidden labels, or the correct answer.
- **No generic variable names**: `x`, `y`, `z`, `answer`, `result`, `val` are forbidden.
- **snake_case names only**: all variable names must be lowercase with underscores; no spaces, no camelCase.
- **Final variable last**: the target variable must be the last entry in `variables[]`.
- **No aliases**: the final target variable must have exactly one name, used consistently in `target_variable_name`, the last `variables[].name`, and `answer_variable_name`.
- **Reject tempting nearby values**: always name at least one rejected variable when the question involves subtraction, profit/loss, ratio, or original-before-process.
- **One JSON object only**: no markdown fence, no explanation before or after.

---

## Routing / Case Selection

Cases are selected and ranked using gold-free cues only:

| Cue | Score |
|-----|-------|
| Missing edge recommendation = backward_from_target_check | +3 |
| Heldout policy label = backward_from_target_check | +2 |
| Transformed-target cue count > 0 | +2 |
| profit/revenue/cost cue | +1 |
| ratio/base cue | +1 |
| original-before-process cue | +1 |
| per-unit/share cue | +1 |
| difference/remainder cue | +1 |
| unit conversion cue | +1 |

Gold answers are not used for selection or ranking. The `gold_absent` flag is read from `subset_memberships` in the trace packet.

---

## Preflight Outputs

| File | Contents |
|------|----------|
| `manifest.json` | Experiment metadata, case count, gold-safety flags |
| `selected_cases.jsonl` | One row per selected case with question, cues, score |
| `provider_requests_dry_run.jsonl` | One row per request (dry-run only, no API call) |
| `routing_summary.csv` | Per-case routing cues and scores |
| `prompt_audit.json` | Gold-leak check results for every rendered prompt |
| `dry_run_report.md` | Human-readable summary |

---

---

## Live Pilot Results

These are **schema and feasibility pilots only**. They do not constitute evidence of accuracy improvement.  
Gold was not included in any prompt. All gold comparisons were made post-hoc for reporting only.

### Cohere pilot — 2026-05-12 (8 cases, `command-r-plus-08-2024`)

| Metric | Value |
|--------|-------|
| Calls succeeded | 8/8 |
| JSON parse | 8/8 (100%) |
| Schema compliance | 8/8 (100%) |
| `answer_variable_name == target_variable_name` | 8/8 |
| `final_answer` bare number | 8/8 |
| New candidates (not in existing pool) | 6/8 |
| Matches proxy structural best (post-hoc) | 0/8 |
| Schema issues | None |

Output: `outputs/target_variable_dict_pal_branch_v1_live_pilot_8_20260512T175650Z/`

### Cerebras pilot — 2026-05-12 (8 cases, `llama3.1-8b`)

| Metric | Value |
|--------|-------|
| Calls succeeded | 8/8 |
| JSON parse | 8/8 (100%) |
| Schema compliance | 6/8 (75%) |
| `answer_variable_name == target_variable_name` | 8/8 |
| `final_answer` bare number | 8/8 |
| New candidates (not in existing pool) | 7/8 |
| Matches proxy structural best (post-hoc) | 0/8 |
| Schema issues | `answer_variable_not_in_variables`: 2/8 |

Output: `outputs/cerebras_target_variable_dict_pal_live_pilot_8_20260512T193711Z/`

**Root cause of `answer_variable_not_in_variables` (2/8 cases):** The model declared `answer_variable_name: "X"` and `target_variable_name: "X"` but used a different string as the final variable's `name` field in `variables[]`. This is a naming-consistency failure, not an arithmetic or structural error. The prompt has been tightened to make the exact-match constraint explicit.

**Note on 0/8 proxy-best match:** The proxy structural best is derived from the existing candidate pool, which already contains wrong-target answers. Generating new candidates that do not match the pool is expected behaviour, not a failure. Accuracy against gold requires a held-out live evaluation, which has not been run.

---

## Safe Claims

- Explicit target-variable binding addresses the structural gap identified in `frontier_next_edge_policy_v1`.
- The Cohere 8-case pilot shows 100% schema compliance on the tightened JSON schema.
- The Cerebras 8-case pilot shows 75% schema compliance; the 2/8 failure type has a known root cause and a prompt fix.
- Gold was not included in prompts in either pilot. Gold comparison was post-hoc only.
- These pilots are schema/feasibility evidence only; they do not prove accuracy improvement over `external_l1_max`.

## Unsafe Claims

- Do not claim accuracy improvement over `external_l1_max` without held-out live evaluation on the wrong-supported-consensus-97 slice.
- Do not claim schema compliance equals accuracy on the underlying math task.
- Do not generalize Cerebras 8-case results to the full 97-case slice.

---

## Recommended Next Steps

1. Prompt tightening complete (this update). Re-run preflight to confirm no gold leakage.
2. Run a 20-case BFTC pilot (highest-priority: lift 1.60, 23/24 Cerebras recommendation).
3. Run a 20-case Cerebras TVD PAL follow-up to verify `avn_not_in_variables` rate drops after prompt fix.
4. Only claim accuracy improvement after a held-out pilot with gold-absent case evaluation.

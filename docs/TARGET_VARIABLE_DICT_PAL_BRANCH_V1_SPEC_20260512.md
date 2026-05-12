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
| `target_variable_name` | Semantic, not generic (`x`, `answer`, `result`, `val`) |
| `variables[*].name` | Semantic; must include the target variable as one entry |
| `rejected_non_final_variables` | At least one entry when a tempting intermediate exists |
| `answer_variable_name` | Must exactly match `target_variable_name` |
| `final_answer` | Bare integer or decimal; no `$`, `%`, commas, units, or string wrapping |

---

## Prompt Rules

- **No gold leakage**: prompt must not include `gold_answer`, `answer_key`, hidden labels, or the correct answer.
- **No generic variable names**: `x`, `y`, `z`, `answer`, `result`, `val` are forbidden.
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

## Safe Claims

- Explicit target-variable binding addresses the structural gap identified in `frontier_next_edge_policy_v1`.
- This is a no-API preflight; no model output has been collected yet.
- Case selection is gold-free and reproducible.

## Unsafe Claims

- Do not claim accuracy improvement over external_l1_max without live pilot evidence.
- Do not claim the JSON schema will be reliably produced without validation on live outputs.
- Do not run a live pilot until preflight passes and the `frontier_next_edge_policy_v1` evidence threshold is confirmed.

---

## Recommended Next Steps

1. Pass preflight (this document).
2. Run a ≤12-case Cohere-only fixed-budget live pilot.
3. Validate JSON schema compliance and `answer_variable_name == target_variable_name`.
4. Check backward_from_target_check recall on live pilot.
5. Only expand if live pilot shows ≥3/12 exact-match improvement on gold-absent slice.

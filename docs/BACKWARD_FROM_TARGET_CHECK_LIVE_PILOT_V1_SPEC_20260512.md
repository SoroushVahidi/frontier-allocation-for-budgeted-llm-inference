# Backward-From-Target-Check Live Pilot v1 — Specification
**Date:** 2026-05-12
**Experiment ID:** backward_from_target_check_live_pilot_v1
**Status:** Preflight ready. Live API calls require explicit approval.

---

## Purpose

Run a small prospective live pilot that allocates the `backward_from_target_check` branch to
20 gold-absent wrong-supported-consensus cases, then evaluate post-hoc whether the branch
recovers the gold answer into the candidate pool. This is the first prospective test of the
BFTC allocation hypothesis.

---

## Failure Mode Targeted

**Final-target binding failure:** the frontier generates candidates that answer a different
quantity than asked. For 70/97 wrong-supported-consensus cases, the gold answer is absent from
the candidate pool entirely — no reranking can recover these. The `backward_from_target_check`
branch was not allocated to any of these 70 cases by the controller; the pilot tests whether
allocating it generates a candidate closer to the correct target.

Sub-patterns: profit vs. sale price, difference vs. total, original-before-process vs. after,
per-unit vs. total, unit conversion, ratio/percentage base.

---

## Why BFTC Is Prioritized

Three independent evidence streams converge on BFTC as the highest-priority next allocation:

| Evidence source | Signal |
|---|---|
| Colored reasoning-edge mining (`mine_reasoning_edge_sequences.py`) | PAL→verifier/backward-check transition: lift **1.60**, support 22 cases, precision 0.95 — highest single lift in the transition table |
| Frontier node-distribution mining (`mine_frontier_node_distribution.py`) | Per-case ML proxy predicts BFTC improvement: AUC **0.78** |
| Held-out next-edge policy (`evaluate_frontier_next_edge_policy_v1.py`) | 5-split cross-validation logistic classifier consistently selects BFTC as top recommended next edge |
| Cerebras failure-pattern pilot (24 cases, `llama3.1-8b`) | **23/24** cases independently recommend `backward_from_target_check` as next edge, from a separate evidence packet that did not include the offline lift scores |

---

## What This Evidence Does and Does Not Prove

**Does prove (offline):**
- BFTC is the strongest historically observed next allocation by three independent metrics.
- The 23/24 Cerebras recommendation is independent from the offline mining signals.

**Does not prove:**
- That allocating BFTC prospectively will recover gold answers in held-out cases.
- Any accuracy improvement over `external_l1_max` (no held-out live evidence yet).
- That the lift signal generalizes to the 70 gold-absent cases (offline training set may overlap).

The pilot exists to produce the first prospective evidence.

---

## Proposed 20-Case Pilot Design

| Parameter | Value |
|---|---|
| Branch | `backward_from_target_check_live_pilot_v1` |
| Case pool | 70 gold-absent wrong-supported-consensus cases |
| Cases selected | 20, deterministic (sorted by case_id) |
| Provider | Cohere `command-r-plus-08-2024` (or Cerebras `llama3.1-8b` as secondary) |
| Temperature | 0 |
| Max output tokens | 2048 |
| API calls | 20 (one per case) |
| Gold in prompts | Never |
| Gold comparison | Post-hoc only, using case_id lookup |

---

## Case-Selection Rule

1. Load trace packets from the wrong-supported-consensus-97 batch.
2. If a gold pool report is provided, restrict to the 70 gold-absent case IDs from Section B.
3. Sort remaining cases by `case_id` (lexicographic) for deterministic reproducibility.
4. Take the first 20.

If no gold pool report is available, all wrong-consensus cases are used and the manifest is
labelled `all_wrong_consensus_cases` (a weaker selection, not recommended).

---

## Prompt Contract

Prompt template: `prompts/backward_from_target_check_live_pilot_v1.md`

Template variables:
- `{{question}}`: the exact question text from the trace packet.
- `{{candidate_pool_summary}}`: a gold-free summary of existing model-generated candidate
  values (numeric strings only, no gold label, no selection indicator).

**Forbidden in prompts:**
- `gold_answer`, `answer_key`, `hidden_labels`, `gold:` fields.
- Any numeric value known to be the gold answer.
- The `gold_present_in_candidate_pool` field from selector_metadata.

The rendered prompt instructs the model to:
1. Identify the exact target quantity.
2. Work backward through the reasoning to validate each step.
3. Review existing candidates against the target.
4. Output a structured JSON with `final_answer` as a bare number.

---

## No-Gold-Leakage Rules

- Gold answers are stored only in `docs/project_handoff_*` audit files. They must not be
  copied into any prompt, provider request field, or rendered text.
- The `gold_absent` flag in the request JSONL is derived from the gold pool report (a
  pre-computed label), not from model output. It is used only for post-hoc stratification.
- Post-hoc evaluation reads the gold from local audit files keyed by `case_id`, never from
  the provider request or prompt.

---

## Output Schema (per provider request)

Each row in `provider_requests_dry_run.jsonl` contains:

| Field | Type | Description |
|---|---|---|
| `request_id` | str | Unique ID: `experiment_id:case_id:index` |
| `case_id` | str | Case identifier |
| `question` | str | The question text (from trace packet) |
| `prompt_text` | str | Rendered BFTC prompt (gold-free) |
| `candidate_pool` | list[str] | Prior model-generated candidate values (no gold label) |
| `candidate_pool_size` | int | Number of prior candidates |
| `baseline_answer` | str | The answer selected before BFTC allocation |
| `gold_absent` | bool\|null | True if gold absent from pool (from gold pool report); null if unknown |
| `dry_run` | bool | True in preflight |
| `api_call_made` | bool | False in preflight |
| `prompt_sha256` | str | SHA-256 of rendered prompt for tamper detection |
| `max_output_tokens` | int | 2048 |
| `required_output_fields` | list[str] | Fields expected in model response |

---

## Post-Hoc Evaluation Metrics

After live calls, evaluate each response against these metrics (gold used only at this stage):

| Metric | Description |
|---|---|
| `parse_ok` | Response is valid JSON with all required fields |
| `final_answer` | Numeric value extracted from response |
| `is_new_candidate` | `final_answer` not in `candidate_pool` |
| `gold_recovered` | `final_answer` matches gold (post-hoc lookup only, never in prompt) |
| `matches_baseline` | `final_answer` matches `baseline_answer` |
| `bftc_review_says_none` | `candidate_pool_review` contains "none" (BFTC agrees no prior candidate is correct) |
| `backward_steps_count` | Number of steps in `backward_check_steps` |
| `all_steps_consistent` | All steps have `consistent_with_target: true` |
| `error_category` | If `parse_ok` is False: truncation / schema_missing / json_parse_failure |

Primary metric: **gold recovery rate** (how many of the 20 cases generate a new candidate
that matches gold, where gold was absent before).

---

## Stop/Go Criteria

| Recovery | Decision |
|---|---|
| 0–2/20 | Do not scale. Reconsider BFTC prompt design or case selection. |
| 3/20 | Borderline. Inspect failures qualitatively before deciding. |
| 4–6+/20 | Justified to run a 50–100-case follow-up pilot. |
| ≥8/20 | Strong signal. Plan a full 70-case pilot. |

These thresholds are informal and must be reviewed alongside parse rate, schema compliance,
and whether failures cluster in a specific sub-pattern.

---

## Safe Claims

- The offline evidence (lift 1.60, AUC 0.78, 23/24 Cerebras recommendations) justifies a
  prospective BFTC pilot as the highest-priority next live experiment.
- The preflight generates gold-free provider requests only.
- Case selection is deterministic and reproducible.

## Unsafe Claims

- Do not claim BFTC will recover gold in any specific number of cases before the pilot runs.
- Do not claim any accuracy improvement over `external_l1_max` until a held-out evaluation
  on the full 97-case (or larger) slice is complete.
- Do not generalize 20-case pilot results to the full dataset without a larger follow-up.
- Do not interpret schema compliance rate as accuracy on the underlying math task.

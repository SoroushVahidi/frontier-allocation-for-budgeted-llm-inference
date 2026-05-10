# Target + staged subgoal PAL retry — offline experiment design (2026-05-07)

**Worktree:** `/home/soroush/research-next-wt`  
**Status:** Design / specification only — **no API executed**, **no controller changes**, **no runtime retry wiring**.  
**Grounding:** `outputs/gold_absent_external_success_schema_mining_20260507/` (especially 11 **primary** gold-absent / external-correct rows) plus collection bundle artifacts.

---

## 1. Motivation (schema mining → experiment)

Schema mining on **gold_absent_discovery** cases showed a repeatable gap between failing PAL and successful externals:

| Pattern | Role |
|--------|------|
| **`multi_step_chain`** | Dominant — most problems need staged quantities before a final transform. |
| **`aggregation_total`**, **`temporal_state_update`**, **`difference_comparison`**, **`target_mapping_error`** | Recur often as sub-structure. |
| PAL failure modes | **`wrong_operator`**, **`arithmetic_from_wrong_relation`**, **`wrong_target_variable`**, **`failed_code_or_empty_code`**, **`missing_intermediate_state`**. |
| External successes | Often **restate the target**, **name missing quantities**, **aggregate by group**, **answer the asked variable** after intermediate steps. |

**Hypothesis:** Forcing an explicit **formulation layer** (target, units, grounded quantities, ordered subgoals, checks) **before** `PYTHON` code will reduce compressed/wrong-relation PAL and improve gold-absent recovery, **without** relying on scalar validator scores or automatic triggers.

This parallels **Combinatorial Opt Agent** practice: **slots / objective / checks first**, executable solve second; **validation metadata** is separate from the final numeric answer.

---

## 2. Pilot case selection

### 2.1 Primary pilot (11) — gold-absent + external-correct

**Source:** `schema_mining_cases.csv` rows with `selection_tier == primary_external_correct` (aligned with `schema_mining_summary.json`).

| case_id | required_schemas (mining) | pal_failure_modes | operation_hint_tags |
|---------|---------------------------|-------------------|---------------------|
| `openai_gsm8k_1099` | target_mapping_error \| aggregation_total \| multi_step_chain | wrong_target_variable | — |
| `openai_gsm8k_1125` | rate_equation \| temporal_state_update \| multi_step_chain | wrong_operator \| missing_intermediate_state | rate_ratio |
| `openai_gsm8k_1155` | unit_conversion \| product_grouping | wrong_operator \| arithmetic_from_wrong_relation | — |
| `openai_gsm8k_1166` | multi_step_chain \| rate_equation | failed_code_or_empty_code | temporal_change |
| `openai_gsm8k_1187` | difference_comparison \| multi_step_chain | arithmetic_from_wrong_relation | difference |
| `openai_gsm8k_1198` | temporal_state_update \| multi_step_chain | overcompressed_one_expression \| missing_intermediate_state | difference \| temporal_change |
| `openai_gsm8k_1215` | difference_comparison \| multi_step_chain | failed_code_or_empty_code | — |
| `openai_gsm8k_1230` | aggregation_total \| proportional_scaling | wrong_target_variable | — |
| `openai_gsm8k_1244` | unit_conversion \| multi_step_chain | wrong_target_variable | — |
| `openai_gsm8k_1248` | target_mapping_error \| multi_step_chain | arithmetic_from_wrong_relation | — |
| `openai_gsm8k_1281` | multi_step_chain \| aggregation_total | omitted_quantity \| arithmetic_from_wrong_relation | — |

**Allowlist file (for future pilot script):** e.g. `outputs/target_staged_pal_retry_pilot_20260507/allowlist_primary_11.jsonl` — one `example_id` / `case_id` per line (to be created when scripting; **not created in this design-only step**).

### 2.2 Guardrail regression set (20) — not run in this design phase

**Definition:** `all_casebook.csv` rows with `pal_correct == 1` and `best_external_correct == 1` (183 total). For a **fixed, reproducible** first control slice, use the **first 20 by sorted `case_id`**:

1. `openai_gsm8k_1072`  
2. `openai_gsm8k_1073`  
3. `openai_gsm8k_1074`  
4. `openai_gsm8k_1075`  
5. `openai_gsm8k_1076`  
6. `openai_gsm8k_1077`  
7. `openai_gsm8k_1078`  
8. `openai_gsm8k_1079`  
9. `openai_gsm8k_1080`  
10. `openai_gsm8k_1084`  
11. `openai_gsm8k_1086`  
12. `openai_gsm8k_1088`  
13. `openai_gsm8k_1089`  
14. `openai_gsm8k_1090`  
15. `openai_gsm8k_1091`  
16. `openai_gsm8k_1092`  
17. `openai_gsm8k_1093`  
18. `openai_gsm8k_1094`  
19. `openai_gsm8k_1096`  
20. `openai_gsm8k_1098`  

**Note:** None of these overlap the 11 primary IDs. Future pilots may rotate or stratify this list; this document fixes **v1** for comparability.

---

## 3. Retry template (precise — all deployable variants)

**Shared rule:** The model must emit **six labeled sections in order**, then **only** a Python block. Any natural-language explanation **outside** these sections is discouraged; if present, parsers should **only** trust the labeled spans.

### 3.1 Section contract

| Section | Meaning |
|---------|---------|
| **`TARGET:`** | One sentence: the **exact quantity** the question asks for (e.g. “half the total number of spots”, “total tap count in 5 minutes”, “dollars Pat still spends”), paraphrased **from the question**, not from an intermediate. |
| **`UNITS:`** | Final answer **unit or type** (e.g. `count`, `dollars`, `minutes`, `weeks`, `dimensionless integer`). If mixed, state the **final line’s** unit. |
| **`GIVEN_QUANTITIES:`** | Bullet list; each line: `- <number> : <short meaning from problem>` using **problem-consistent units** (convert in text if needed). |
| **`SUBGOALS:`** | Ordered bullets: intermediate values **to compute before** the final line, each tied to a **named** sub quantity (e.g. “spots per mamba”, “taps per minute arms down”). |
| **`CHECKS:`** | Bullets stating **what the final numeric must represent** and **sanity constraints** (e.g. “final equals (cobra total + mamba total) / 2”, “must not multiply two independent per-minute foot rates together”). |
| **`PYTHON:`** | Single fenced block or bare code: **executable** Python that assigns a clearly named final variable and **prints** one numeric result consistent with `TARGET` / `UNITS`. |

### 3.2 Example skeleton (not tied to a real case — illustration only)

```
TARGET: <verbatim paraphrase of asked quantity>
UNITS: <final unit/type>
GIVEN_QUANTITIES:
- ...
SUBGOALS:
- ...
CHECKS:
- ...
PYTHON:
```python
# code only
print(...)
```
```

### 3.3 Parser / materializer expectations (offline prep)

**Expected machine-readable extraction:**

- `target_line`, `units_line`, `given_quantities[]`, `subgoals[]`, `checks[]`, `python_source`.

**`materializer` fields (per case, per run)** — to be populated when scripting:

| Field | Description |
|-------|-------------|
| `case_id` | GSM8K id |
| `template_variant` | `target_staged_pal_retry_v1`, etc. |
| `raw_model_text` | Full string returned before code execution |
| `parsed_target` | From `TARGET:` |
| `parsed_units` | From `UNITS:` |
| `parsed_given_json` | List of `{value_str, meaning}` |
| `parsed_subgoals_json` | List of strings |
| `parsed_checks_json` | List of strings |
| `parsed_python` | Source string |
| `pal_exec_ok`, `pal_stdout`, `pal_stderr_type` | Execution metadata |
| `final_answer_raw`, `final_answer_normalized` | Post-exec |
| `exact_match` | vs gold (offline scoring) |
| `target_restatement_ok` | Boolean: heuristic match of `TARGET:` vs question cues (see §5) |
| `salient_quantity_coverage_delta` | Optional: compare count of salient norms in code vs baseline PAL from `all_results.jsonl` |
| `cohere_logical_api_calls` | From run manifest |
| `budget_config` | echo of pilot budget (e.g. 6) |

---

## 4. Variants

### Variant A — `target_staged_pal_retry_v1` (generic, deployable spec)

- **Content:** Section contract in §3 only.
- **No external traces** in the prompt beyond the **GSM8K question** (and standard system style if the pilot harness adds one).
- **Use:** Default for any future **live** PAL retry lane.

### Variant B — `target_staged_pal_retry_no_external_v1`

- **Content:** Identical to **A** in structure (same six sections and `PYTHON` rule).
- **Hard rule:** Prompt MUST **not** reference or paste **external traces**, **baseline method names**, **`schema_mining_*` excerpts**, or any text not derivable from the GSM8K **question** (+ minimal style instructions).
- **Naming purpose:** Explicit ablation flag in logs / manifests when proving **zero external leakage** on audits.
- **Use:** Side-by-side logging against **A** if future harnesses add optional hints; **A** and **B** remain deployable; **C** is not.

### Variant C — `target_staged_pal_retry_oracle_external_v1` (**non-deployable / diagnosis only**)

- **Content:** Same six sections, **plus** (after `CHECKS:` or in a clearly separated `ORACLE_SCHEMA_HINT:` block) **one short hint** derived **offline** from a **known-correct external** `final_nodes` reasoning excerpt — e.g. mined schema tags (`multi_step_chain`, `aggregation_total`) or a single-line “gold path” summary.

- **Constraints:**
  - **Must never** ship in production or sit on the decision path for commitment.
  - **Only** for: ceiling analysis, parser debugging, or labeling whether the template fixes failures that are **purely internal** vs **need stronger hints**.

- **Labeling in outputs:** `deployable: false`, `oracle_assisted: true`.

---

## 5. Offline preparation (before any API)

**Deliverables to create in a future PR / script pass (not in this document step):**

1. **Prompt spec** — Markdown or `.txt` under e.g. `prompts/target_staged_pal_retry/`:
   - `system_stub.md` (optional, minimal)
   - `user_template_v1.md` embedding §3 instructions + `{question}` placeholder
2. **Allowlist** — 11 IDs as in §2.1.
3. **JSON schema** — for `materializer` JSONL rows (or CSV column list).
4. **Scoring plan** — script-readable:
   - Load gold from `all_casebook.csv` / bundle.
   - Load **baseline PAL** from `all_results.jsonl` (`direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`) for `salient_quantity_coverage_delta` and wrong-answer comparison.
   - **Target restatement check:** offline string test — e.g. key n-grams from question’s wh-phrase (“half”, “average”, “per week”, “each day in the second half”) must appear in `TARGET:` or in first bullet of `CHECKS:`; failures flagged `target_restatement_ok=false`.

**Status now:** This file **is** the spec. Prompt files and scripts **do not** exist yet **by design**.

---

## 6. API phase (future) — caps only; **no API in this step**

The **first test that exercises new codegen** requires **Cohere** (or equivalent) because the template asks the **model** to produce new text + Python.

**Proposed run budget (v1 pilot):**

| Item | Value |
|------|--------|
| Cases | 11 primary |
| Method variants | 1 deployed template per run (start with **A**); optional separate run for **C** with oracle flag |
| Frontier / PAL budget | **6** logical steps (match recent pilots; adjust only with written rationale) |
| **Estimated** logical calls | ≤ **80** (11 × ~7 including retries overhead — conservative envelope) |
| **Hard absolute cap** | **120** logical calls for the entire pilot job (fail closed; no batch extension without new doc) |

**Guardrail pass (same API session or immediate follow-up):**

- 20 cases × 1 variant × same budget ≈ **≤150** estimated; **hard cap 200** logical calls if batched with primary in one manifest.

**This document:** **no API was run** during its creation.

---

## 7. Success criteria (v1)

### 7.1 Primary (11)

- **Win bar:** ≥ **3 / 11** cases move from **wrong** baseline PAL (per `all_results.jsonl` / casebook) to **exact match** under the new template, **without** introducing new failure modes that violate checks (e.g. empty `PYTHON:`).
- **Diagnostics required** per case: full raw output, parsed sections, executed code, stdout, `exact_match`, `target_restatement_ok`, `salient_quantity_coverage_delta`, logical call count.

### 7.2 Guardrail (20)

- **Regression bar:** ≤ **1 / 20** cases flip from **correct** to **incorrect** vs baseline PAL on the same gold.
- If regression > 1, **stop** template promotion; analyze verbosity / parser / wrong target restatement.

### 7.3 No automatic trigger

Passing bars **only** justify **continued experimentation** (larger allowlists, trigger design). It does **not** authorize controller wiring.

---

## 8. Risks

| Risk | Mitigation |
|------|------------|
| **Overfit to 11 cases** | Hold out secondary gold-absent rows; expand allowlist; avoid hand-tuning checklist wording per case. |
| **Verbosity / parse failures** | Strict section headers; unit tests on parser; fallback “repair prompt” is **out of scope** for v1 — record `parse_ok`. |
| **Wrong `TARGET:`** | `target_restatement_ok` gate + human spot-check on first 3 failures. |
| **No trigger** | Template is independent of validator triggers (paused per static audit). |
| **Guardrail damage unknown** | Mandatory 20-case guardrail pass with hard flip cap. |
| **Oracle variant leakage** | Variant **C** isolated in manifests; forbidden in any “deployable” flag path. |

---

## 9. Future code (explicitly **not** implemented now)

| Artifact | Purpose |
|----------|---------|
| `scripts/materialize_target_staged_pal_prompt.py` (or similar) | Fill `{question}`, write per-case prompt files. |
| `scripts/run_target_staged_pal_pilot.py` | Drive Cohere within cap; write `per_example_records.jsonl`. |
| `tests/test_target_staged_pal_output_parse.py` | Golden tests for section extraction + edge cases. |
| Optional: validator hook | Never-raise list of warnings on parsed checklist vs `validate_gsm8k_candidate` **quantity** fields — **sidecar only**. |

**Controllers:** remain untouched until a separate design explicitly approves wiring behind a flag.

---

## 10. Connection to Combinatorial Opt Agent

| COA idea | This experiment |
|----------|-----------------|
| Formulation before solve | `TARGET` + `GIVEN_QUANTITIES` + `SUBGOALS` = structured slots before `PYTHON`. |
| Objective clarity | `TARGET` / `UNITS` mirror objective + type in opt models. |
| Constraints / checks | `CHECKS` = feasibility / sanity lines (not full proof). |
| Metadata vs answer | Checklist stored **separately** from executed numeric; scoring uses both. |
| Lightweight validators | Future optional checks on checklist (never auto-override selection). |

---

## 11. Exact next actionable query (for implementation chat)

> Implement **offline** prompt files + `allowlist_primary_11.jsonl` + **unit tests** for §3 parsers; then **one** gated Cohere pilot run for **`target_staged_pal_retry_v1`** on the 11 IDs with **≤120** logical-call cap, writing a `per_example_records.jsonl` + `schema_mining_comparison.json` against baseline `all_results.jsonl`; run the **20-case guardrail** in the same manifest only if the primary run stays under cap, else schedule as second job with **≤200** total calls.

---

## 12. Document control

| | |
|--|--|
| **Report path** | `docs/TARGET_STAGED_PAL_RETRY_EXPERIMENT_PLAN_20260507.md` |
| **Template names** | `target_staged_pal_retry_v1` (**A**), `target_staged_pal_retry_no_external_v1` (**B**), `target_staged_pal_retry_oracle_external_v1` (**C**, non-deployable) |
| **API executed in this step** | **None** |
| **Algorithmic next step** | **Yes — concrete:** staged formulation → codegen pilot with caps, dual success criteria (primary + guardrail), parser tests first |

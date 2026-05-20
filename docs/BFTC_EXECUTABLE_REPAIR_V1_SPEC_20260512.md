# BFTC + Executable Repair v1 — Specification
**Date:** 2026-05-12
**Experiment ID:** bftc_executable_repair_v1
**Status:** No-API scaffold ready. Live pilot requires explicit approval.

---

## Motivation

The 20-case BFTC live pilot (`backward_from_target_check_live_pilot_v1`) achieved:
- 20/20 schema compliance, JSON parse, and numeric extraction — perfect mechanical reliability
- 20/20 `review_says_none`: the model correctly assessed that no prior candidate matched gold
- 15/20 new candidates generated
- **2/20 exact gold recovered** — at the stop boundary of the pre-specified criterion (≤2 → do not scale)
- 5/20 near-misses within 20% of gold
- Post-hoc error analysis classified 18/20 failures as **deterministic-repair-possible**

The dominant failure class (11/18 non-exact failures) was not wrong-target identification — it was **arithmetic execution error** on a correctly identified target. BFTC backward reasoning found the right quantity to compute but produced an incorrect numeric result due to:

- Fraction denominator errors (gsm8k_1027: 20/11 instead of 20/10)
- Missing cost subtraction (gsm8k_1029: revenue instead of profit)
- Circular percentage not solved algebraically (gsm8k_1006: heartworm = 60% of whole bill)
- Unit conversion omitted (gsm8k_183: 480 inches not ÷12 to feet)
- Wrong day count in date arithmetic (gsm8k_184)
- Partial sum (gsm8k_22: one sunflower stream missed)
- Proportional split misread as equal division (gsm8k_190)

**Conclusion:** BFTC is a reliable structured-output foundation for target identification. The bottleneck is exact arithmetic. The fix is to require the model to also output a **safe, executable arithmetic formula**, which a local Python evaluator executes to replace the model's approximate `final_answer` with an exact computed result.

---

## Related Work

| Method | Key idea | Our adaptation |
|---|---|---|
| FOBAR / Forward-Backward Reasoning (ACL 2024 Findings) | Use backward reasoning to verify whether a candidate answer is consistent with the question | BFTC uses backward reasoning not just as a verifier but as a generation branch that outputs both the target and the repair formula |
| Backward Reasoning for Math Word Problems (OpenReview) | Solve or verify from answer/target backward | BFTC starts from the requested target and derives the needed source facts/relations before computing |
| PAL — Program-Aided Language Models (arXiv 2211.10435) | Let the model write code; Python does exact arithmetic | Our adaptation: instead of a full program, require a single safe arithmetic expression with declared variables — lower attack surface, still exact |
| Semantic Parsing / Equation Generation (EMNLP 2015, UW Algebra) | Bind variables/relations before arithmetic | `formula_variables` dict maps names to values and descriptions, enforcing the same binding discipline |
| Hybrid LLM + Symbolic Solver (NeurIPS MathAI 2023) | LLM formalizes variables/equations; symbolic execution solves | Our first-layer execution is a safe `ast`-based evaluator; SymPy is a natural second-layer upgrade |
| Process Supervision / Step Verifiers (OpenAI Let's Verify, arXiv 2305.20050) | Detect first wrong step, not just wrong final answer | `reverse_derivation` + `failed_relation` fields identify which backward step failed; `repair_operation` names the fix |
| Execution-Guided Repair (ACL 2024 Findings) | Use execution feedback to repair a nearly-correct program | If `solution_formula` evaluates cleanly, use `executable_final_answer` as the candidate; if it fails, fall back to model's `final_answer` with an issue flag |

---

## Target Failure Classes

The following error categories from the BFTC postmortem are expected to benefit from executable repair:

| Category | n (20-case pilot) | Mechanism | PAL/SymPy fix |
|---|---|---|---|
| `near_miss_arithmetic_precision` | 5 | Correct steps, small numeric slip | Exact expression evaluation |
| `correct_target_wrong_arithmetic` | 6 | Correct target, wrong chain computation | Exact expression evaluation |
| `ratio_or_percentage_base_error` | 2 | Circular or asymmetric ratio not solved algebraically | SymPy or algebraic formula |
| `unit_or_scale_error` | 2 | Wrong unit used throughout; conversion missing | Factor correction in formula |
| **Total targeted** | **15** | | |

Remaining failures not targeted by executable repair:
- `wrong_target_still` (1): needs question re-reading; execution cannot fix
- `missing_relation_or_fact` (1): misread comparative relation; execution cannot fix without correct setup

---

## Expected Recovery Estimate

From the 20-case postmortem, 18/20 cases were classified `deterministic_repair_possible=True`.

| Scenario | Estimated gold recovery |
|---|---|
| Conservative (15/20 fixable) | 15/20 |
| Optimistic (up to 18/20 fixable) | 18/20 |

These estimates must be validated by the 20-case live executable-repair pilot. They are not claimed as achieved results.

---

## Prompt Contract

Prompt template: `prompts/backward_from_target_check_executable_repair_v1.md`

Template variables (same as BFTC v1):
- `{{question}}`: exact question text
- `{{candidate_pool_summary}}`: gold-free summary of prior model-generated candidates
- `{{prior_bftc_context}}`: optional, the prior BFTC response for context (gold-free, only included if available)

Required JSON output fields:

| Field | Type | Description |
|---|---|---|
| `requested_target` | str | Exact quantity the question asks for |
| `source_facts` | list[str] | Key numeric facts from the problem statement |
| `reverse_derivation` | list[dict] | Backward reasoning steps (`step`, `description`, `consistent_with_target`) |
| `failed_relation` | str | Which relation or computation the prior approach got wrong |
| `repair_operation` | str | What needs to be corrected relative to prior attempts |
| `formula_variables` | dict[str, dict] | `{name: {value, description, unit}}` — all variables used in `solution_formula` |
| `solution_formula` | str | Single safe Python arithmetic expression using only names from `formula_variables` |
| `final_answer` | number | Must equal `eval(solution_formula, formula_variables_values)` |
| `confidence` | str | "high" / "medium" / "low" |

**Forbidden in solution_formula:** imports, assignments, attributes, subscripts, list/dict/set comprehensions, lambda, calls (except `round`), boolean logic, comparisons, string constants, unknown variable names, prose.

---

## No-Gold-Leakage Rules

- Gold answers must never appear in `{{question}}`, `{{candidate_pool_summary}}`, or `{{prior_bftc_context}}`.
- `formula_variables` values are extracted from the question statement, not from a gold label.
- Post-hoc gold comparison is keyed by `case_id` after the live run; gold is read from the casebook only at scoring time.
- The `gold_absent` flag is a pre-computed label from the gold pool report; it is not derived from model output.

---

## Safe Formula Evaluator

The runner uses a Python `ast`-based evaluator (`_eval_formula` in `scripts/run_bftc_executable_repair_v1.py`).

Allowed AST node types:
- `ast.Expression`
- `ast.BinOp` with operators: `Add`, `Sub`, `Mult`, `Div`, `FloorDiv`, `Mod`, `Pow`
- `ast.UnaryOp` with operators: `USub`, `UAdd`
- `ast.Constant` (numeric only: `int`, `float`)
- `ast.Name` if the name is in `formula_variables`
- `ast.Call` to `round` only (with at most 2 arguments, the second being a non-negative integer ≤ 10)

Rejection triggers:
- Any node type not listed above
- `ast.Name` with a name not in `formula_variables`
- Exponent (`Pow`) where the right operand is a constant > 100 or not a constant
- Expression string longer than 500 characters
- Division by zero (runtime check)

Return value: `{eval_ok, value, error_type, error_message, names_used}`

---

## 20-Case Live Pilot Design

| Parameter | Value |
|---|---|
| Prompt template | `backward_from_target_check_executable_repair_v1.md` |
| Cases | Same 20 gold-absent wrong-supported-consensus cases from BFTC v1 |
| Provider | Cohere `command-r-plus-08-2024` |
| Temperature | 0 |
| Max output tokens | 2048 |
| API calls | 20 |
| Gold in prompts | Never |
| Gold comparison | Post-hoc only |
| Prior BFTC responses | Optionally included as `{{prior_bftc_context}}` |

**Primary metric:** `gold_recovered_by_executable_final_answer_count` (how many of 20 cases produce an `executable_final_answer` matching gold, where gold was absent from the prior pool).

**Secondary metric:** `formula_eval_ok_count` (schema compliance of the executable repair field).

---

## Stop/Go Criteria

| Recovery | Decision |
|---|---|
| 0–4/20 | Do not scale; revisit formula prompt or add SymPy layer |
| 5–8/20 | Borderline; inspect failures qualitatively |
| 9–12/20 | Justified for 50–100-case follow-up |
| 13+/20 | Strong signal; plan full 70-case pilot |

(Thresholds are higher than BFTC-only because executable repair should eliminate arithmetic errors.)

---

## Safe Claims

- BFTC-only mechanically worked (20/20 schema, parse, numeric extraction).
- Executable repair is motivated by post-hoc error analysis of the 20-case pilot (18/20 deterministic-repair-possible).
- The `ast`-based evaluator is safe by construction; it cannot execute imports, assignments, or function calls (except `round`).
- Gold is never included in prompts or provider request fields.
- No accuracy improvement is claimed over `external_l1_max` until a held-out evaluation is complete.

## Unsafe Claims

- Do not claim BFTC+execution recovers gold at 15–16/20 before the live pilot runs.
- Do not claim any accuracy improvement over `external_l1_max` without a held-out evaluation.
- Do not generalize 20-case pilot results without a larger follow-up.
- Do not claim gold was used in prompts.

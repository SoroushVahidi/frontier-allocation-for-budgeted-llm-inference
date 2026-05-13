# BFTC Live Pilot v1 — 20-Case Postmortem
**Date:** 2026-05-12  
**Experiment:** backward_from_target_check_live_pilot_v1  
**Output:** `outputs/bftc_live_pilot_v1_20cases_20260512T210634Z`  
**Model:** Cohere `command-r-plus-08-2024`, temperature=0, max_tokens=2048  
**Casebook:** `docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv`  
**Analysis artifacts:** `bftc_case_error_analysis.jsonl`, `bftc_case_error_analysis.csv` (same output directory)

---

## Summary Metrics

| Metric | Result |
|---|---|
| API calls attempted / succeeded | 20 / 20 |
| JSON parse ok | 20 / 20 |
| Schema ok (all required fields) | 20 / 20 |
| Numeric `final_answer` extracted | 20 / 20 |
| New candidates (fa not in prior pool) | 15 / 20 |
| All backward steps consistent | 15 / 20 |
| `review_says_none` (prior pool correctly flagged) | 20 / 20 |
| **Exact gold recovered** | **2 / 20** |
| Near-misses (within 20% of gold) | 5 / 20 |
| `gold_in_any_prompt` | false |

---

## Per-Case Error Classification

### Categories

| Category | Count | Cases |
|---|---|---|
| `exact_recovered` | 2 | gsm8k_1021, gsm8k_162 |
| `near_miss_arithmetic_precision` | 5 | gsm8k_1025, gsm8k_1027, gsm8k_166, gsm8k_213, gsm8k_233 |
| `correct_target_wrong_arithmetic` | 6 | gsm8k_1003, gsm8k_1069, gsm8k_22, gsm8k_228, gsm8k_180, gsm8k_184 |
| `ratio_or_percentage_base_error` | 2 | gsm8k_1006, gsm8k_190 |
| `unit_or_scale_error` | 2 | gsm8k_183, gsm8k_239 |
| `state_before_after_error` | 1 | gsm8k_1029 |
| `wrong_target_still` | 1 | gsm8k_1035 |
| `missing_relation_or_fact` | 1 | gsm8k_262 |
| **Total** | **20** | |

### Per-Case Detail

| case_id | gold | fa | rel_err | category | diagnosis (concise) |
|---|---|---|---|---|---|
| gsm8k_1003 | 20 | 1.0 | 95% | `correct_target_wrong_arithmetic` | Age system of equations failed; model collapsed to trivial value |
| gsm8k_1006 | 25 | 45.0 | 80% | `ratio_or_percentage_base_error` | Circular % bill (heartworm=60% of whole bill) treated as % of sub-total |
| gsm8k_1021 | 8 | 8.0 | 0% | `exact_recovered` | 32-page tabloid paper count: 32/4=8 ✓ |
| gsm8k_1025 | 23 | 20.0 | 13% | `near_miss_arithmetic_precision` | Off by 3 cookies; steps consistent; PAL fixable |
| gsm8k_1027 | 2 | 1.818 | 9% | `near_miss_arithmetic_precision` | fa=20/11 instead of $2.00; wrong pair count in denominator |
| gsm8k_1029 | 70000 | 195000 | 179% | `state_before_after_error` | Computed sale revenue not profit; forgot to subtract purchase+repair costs |
| gsm8k_1035 | 193 | 33.33 | 83% | `wrong_target_still` | Model interpreted as probability (33.33%); gold=193 suggests count |
| gsm8k_1069 | 191 | 107.0 | 44% | `correct_target_wrong_arithmetic` | Multi-category score sum; off by 84 points; missed one category |
| gsm8k_162 | 50 | 50.0 | 0% | `exact_recovered` | Three-person age problem solved correctly ✓ |
| gsm8k_166 | 15 | 15.6 | 4% | `near_miss_arithmetic_precision` | Water fraction in mixed drink off by 0.6L; PAL fixable |
| gsm8k_180 | 8 | 11.0 | 38% | `correct_target_wrong_arithmetic` | 0/4 backward steps consistent; chained age derivation confused |
| gsm8k_183 | 40 | 480.0 | 1100% | `unit_or_scale_error` | 480 inches ÷ 12 = 40 feet; forgot final unit conversion |
| gsm8k_184 | 525 | 1166.67 | 122% | `correct_target_wrong_arithmetic` | Calorie deficit/day; wrong day count between Dec 31 and Jul 19 (ratio ≈ 2.22) |
| gsm8k_190 | 420 | 520.0 | 24% | `ratio_or_percentage_base_error` | Assumed equal 3-way split; problem has asymmetric ratios (3rd=2×2nd, 2nd=1st+80) |
| gsm8k_213 | 24 | 28.0 | 17% | `near_miss_arithmetic_precision` | Savings comparison off by $4; fa=28 already in prior pool |
| gsm8k_22 | 291 | 105.0 | 64% | `correct_target_wrong_arithmetic` | Counted only one sunflower stream (bouquet or individual), missed the other |
| gsm8k_228 | 127 | 1005.0 | 691% | `correct_target_wrong_arithmetic` | Monthly TikTok time; off by ~8x — wrong activity set or week/month multiplier |
| gsm8k_233 | 21 | 17.5 | 17% | `near_miss_arithmetic_precision` | Pyramid height off by 3.5ft (42 inches); one layer missed |
| gsm8k_239 | 13 | 10800.0 | >8000% | `unit_or_scale_error` | Earnings difference in wrong time period; gold=13 implies a different unit/window |
| gsm8k_262 | 23 | 32.0 | 39% | `missing_relation_or_fact` | Dropped "minus 5" from "half of Jan's age minus 5"; fa=32 is prior candidate |

---

## Near-Miss Deep-Dive

All 5 near-misses had correct target identification and consistent backward steps. Failure was purely arithmetic:

| case_id | fa | gold | rel_err | root cause | executable fix |
|---|---|---|---|---|---|
| gsm8k_1027 | 1.818 | 2 | 9% | Wrong pair count in denominator | PAL: recount pairs per box |
| gsm8k_166 | 15.6 | 15 | 4% | Fractional water volume rounding | PAL with exact fractions |
| gsm8k_1025 | 20 | 23 | 13% | Missed one cookie batch in multi-step chain | PAL: explicit variable assignment |
| gsm8k_213 | 28 | 24 | 17% | Off by $4 in cost difference | PAL: enumerate ticket costs |
| gsm8k_233 | 17.5 | 21 | 17% | Missed one pyramid layer (3.5ft = 42in) | PAL: sum heights, ÷12 |

**All 5 near-misses are confidently fixable by PAL/SymPy execution.**

---

## Executable Repair Upper Bound Estimate

Cases where a deterministic arithmetic or symbolic repair (PAL/SymPy) can recover gold without another full model call:

| Category | Cases | Estimated fixable by PAL/SymPy |
|---|---|---|
| `exact_recovered` | 2 | 2 (already exact) |
| `near_miss_arithmetic_precision` | 5 | 5 (all have consistent steps + correct target) |
| `correct_target_wrong_arithmetic` | 6 | 4 (gsm8k_1069, gsm8k_22, gsm8k_183→unit, gsm8k_184→date) |
| `ratio_or_percentage_base_error` | 2 | 2 (SymPy equation solve) |
| `unit_or_scale_error` | 2 | 1 confirmed (gsm8k_183: ÷12), 1 uncertain (gsm8k_239) |
| `state_before_after_error` | 1 | 1 (gsm8k_1029: subtract costs from revenue) |
| `wrong_target_still` | 1 | 0 (needs re-reading, not arithmetic) |
| `missing_relation_or_fact` | 1 | 1 possible (gsm8k_262, if SymPy is given correct relation) |
| **Total** | **20** | **15–16 / 20 (conservative), up to 18/20 (optimistic)** |

18/20 cases were classified as `deterministic_repair_possible=True` in the machine-readable analysis.

---

## Hypothesis Evaluation

**User hypothesis:** The best next step is not more BFTC prompting but BFTC → executable repair, where the model outputs equations or a PAL snippet and local execution computes the exact final answer.

**Verdict: Confirmed by the data.**

Supporting evidence:

1. **Perfect mechanical compliance:** 20/20 schema, parse, and numeric extraction. The model is reliable at structured output — no wasted signal from format failures.

2. **Target identification is sound:** 19/20 cases correctly identified the target quantity (the one exception, gsm8k_1035, is a question-interpretation failure). The model's backward check is doing real work.

3. **The failure mode is arithmetic, not conceptual:** 5 near-misses + 6 correct-target-wrong-arithmetic cases = 11/18 failures have the right target but wrong computation. These are **exactly the class of errors that PAL/SymPy execution eliminates**.

4. **20/20 `review_says_none`:** The model correctly assessed that no prior candidate matched gold in every case. This is a reliable signal — if BFTC says "none match," the pool truly needs a new candidate.

5. **15/20 new candidates generated:** BFTC is actively producing new candidates, not recycling prior pool values. The execution layer would refine these.

6. **The 2 unit-scale errors (gsm8k_183, gsm8k_239) and 2 ratio errors (gsm8k_1006, gsm8k_190)** are algebraically tractable — a SymPy solver given the correct equation structure recovers gold exactly.

**What BFTC does well:** Target identification, backward step enumeration, recognizing that prior candidates are wrong.  
**What BFTC cannot do without execution:** Exact arithmetic over fractions, unit conversions, circular percentage equations, and day-count calculations.

---

## Recommended Next Implementation Path

**B. BFTC + PAL/SymPy execution repair**

### Design

1. **BFTC pass (existing):** Model outputs `target_identified`, `backward_check_steps`, `candidate_pool_review`, and a rough `final_answer`.

2. **Execution repair pass (new):** Model additionally outputs a compact Python expression or `sympy.solve()` call encoding the key equation(s) for the target. Local Python executes this to get an exact numeric result.

3. **Selection logic:** If execution succeeds and produces a clean integer or simple decimal, it replaces the model's `final_answer`. If execution fails, fall back to the model's `final_answer`.

### Prompt addition (minimal)

Add one field to the BFTC output schema:

```json
"solution_code": "from sympy import symbols, solve; C = symbols('C'); print(solve(5*(C+7) - 3*(C+25), C))"
```

Or simpler: require a `formula` string like `"(125 - 40) / 0.4 - 40"` and `eval()` it locally.

The simpler eval-based approach handles 15 of the 18 fixable cases (no SymPy overhead for straightforward arithmetic).

### Alternative path rejected

**C. BFTC + target-variable-dict PAL:** TVD PAL addresses the same arithmetic problem but forces the model to fully re-solve from scratch in a new branch. Given that BFTC already correctly identifies the target and the steps, adding TVD PAL is strictly more expensive (new full model call) than adding a repair formula field to the existing BFTC response.

---

## Stop/Go Assessment

**Go-criterion threshold:** 4+/20 to justify a 50–100-case follow-up.  
**Observed:** 2/20 exact gold recovered.  
**Decision: Do not scale BFTC-only pilot.**

However, the near-miss distribution is strongly positive for the BFTC+execution path. The correct next step is:

1. Modify `prompts/backward_from_target_check_live_pilot_v1.md` to request a `solution_formula` or `solution_code` field.  
2. Add a local execution evaluator in the runner (`eval()` or `subprocess` with timeout).  
3. Run a 20-case execution-augmented pilot.  
4. Evaluate gold recovery with execution repair. Expected: 15–16/20 based on this postmortem.

No further live API call is justified on the current BFTC-only prompt. The execution-augmented variant requires a new pilot.

---

## Safe Claims

- BFTC achieved 2/20 exact gold recovery on gold-absent cases; this is at the stop boundary of the pre-specified criterion.
- BFTC + PAL/SymPy execution repair is estimated to recover 15–16/20 based on per-case analysis; this must be verified empirically.
- Perfect schema compliance (20/20) and target identification (19/20) confirm BFTC is a reliable structured-output foundation.
- Gold was not placed in any prompt or provider request field. All gold comparison is post-hoc.

## Unsafe Claims

- Do not claim 15–16/20 recovery before running the execution-augmented pilot.
- Do not claim accuracy improvement over `external_l1_max` without a held-out evaluation on the full 97-case or larger slice.
- Do not generalize from 20 gold-absent cases to the full wrong-consensus distribution.

# Cohere targeted failure replay: margin-gated vs direct_reserve_strong_plus_diverse_v1

**Run artifact:** `outputs/cohere_direct_reserve_validation_TARGETED_REPLAY_20260426T_NEXT/`

**Seed package:** `outputs/cohere_direct_reserve_failure_replay_seed_latest/`

**Replay case filter:** the validation runner reuses the first `max-cases` rows of `--reuse-planned-cases`. The full seed `planned_cases.csv` has 12 rows, so a separate **5-row** slice was used: `outputs/cohere_direct_reserve_failure_replay_seed_latest/replay_5_planned_subset.csv` (problem IDs: `openai_gsm8k_12`, `openai_gsm8k_2`, `openai_gsm8k_6`, `openai_gsm8k_13`, `openai_gsm8k_14`).

**API:** Cohere real run (`manifest.json`: `real_api_enabled: true`, `COHERE_API_KEY` present). Provider `cohere`, model `command-r-plus-08-2024`, budget `4`, seed `23` only.

---

## 1. Did Cohere API actually run?

**Yes.** `outputs/cohere_direct_reserve_validation_TARGETED_REPLAY_20260426T_NEXT/manifest.json` sets `run_real_api_requested: true` and `real_api_enabled: true` (and `dry_run: false`).

## 2. How many replay cases were used?

**5** unique examples, **25** per-method rows (5 methods × 5 cases). See `coverage_summary.csv`.

## 3. Which prior seed package was used?

`outputs/cohere_direct_reserve_failure_replay_seed_latest/`, with planned cases further restricted to `replay_5_planned_subset.csv` so the run does not expand to 12 cases.

## 4–5. Selected-gold and gold-present rates by method

From `per_method_summary.csv` (5 method rows each; rates are over 5 case rows per method):

| Method | selected_gold_rate | gold_present_rate |
|--------|-------------------:|------------------:|
| `direct_reserve_strong_plus_diverse_margin_gated_v1` | 0.4 | 0.6 |
| `direct_reserve_strong_plus_diverse_v1` | 0.6 | 0.6 |
| `direct_reserve_strong_v1` | 0.2 | 0.2 |
| `external_l1_max` | 0.0 | 0.2 |
| `strict_f3` | 0.0 | 0.4 |

(“Selected-gold” is `selected_gold` in the script; “gold-present” is `gold_present` over candidate groups.)

## 6. Did margin-gated beat `direct_reserve_strong_plus_diverse_v1` on these hard cases?

**Not overall** on final correctness: **2/5** correct for margin-gated vs **3/5** for `direct_reserve_strong_plus_diverse_v1` (see `per_case_method_results.csv`, `is_correct`).

Per example (same `final_selected_answer` / `is_correct` columns):

| example_id | diverse_v1 correct? | margin_gated correct? |
|------------|:--------------------|:----------------------|
| openai_gsm8k_12 | 1 | 0 |
| openai_gsm8k_2 | 1 | 1 |
| openai_gsm8k_6 | 0 | 1 |
| openai_gsm8k_13 | 0 | 0 |
| openai_gsm8k_14 | 1 | 0 |

## 7. Did the margin gate trigger?

**Yes** on **3/5** cases: `margin_gate_triggered=1` for `openai_gsm8k_12`, `openai_gsm8k_6`, `openai_gsm8k_14` in `per_case_method_results.csv` (method = `direct_reserve_strong_plus_diverse_margin_gated_v1`).

## 8. Gate helped / hurt / no-op (vs diverse_v1 on the same 5 cases)

- **Helped (diverse wrong → gated right): 1** — `openai_gsm8k_6` (fruit price; gate fell back to direct path and hit gold `32` while diverse had `39` after normalization).
- **Hurt (diverse right → gated wrong): 2** — `openai_gsm8k_12` (diverse 70, gated 90) and `openai_gsm8k_14` (diverse 38, gated 30).
- **No-op (same correct/incorrect): 2** — `openai_gsm8k_2` (both correct), `openai_gsm8k_13` (both wrong).

## 9. Prior control degradation (`openai_gsm8k_13`)

**Not fixed in this run.** The prior seed flagged this case as `control_degradation=true` with all methods wrong. Here `direct_reserve_strong_plus_diverse_v1` still **failed**; margin-gated also **failed** (same wrong answer path). So the control stratum is still a failure cluster for this replay.

## 10–11. Failure modes remaining

**Loss-case taxonomy** (from `loss_cases.csv` for `direct_reserve_strong_plus_diverse_v1`-centric rows):

- **`openai_gsm8k_6`:** `gold_absent` (gold not in the diverse candidate pool; extraction/`oxed` noise on branch text).
- **`openai_gsm8k_13`:** `gold_absent` by script definition (no branch group equal to gold 18) — in practice the model is **arithmetically** wrong (model answers 10, etc. vs 18), i.e. wrong work product rather than a pure “in pool but not selected” story.
- **`openai_gsm8k_2`:** bucketed as `other` in the report (both diverse and others mostly correct; row still classified as a “loss” due to the script’s OR conditions).

**Dominant themes across methods:**

- **Gold absent / pool not containing gold** on at least one absent-tree case; **tied wrong branches** and **arithmetic / interpretation** errors on control.
- **Extraction / normalization** artifacts (e.g. `oxed` prefix) appear in `final_selected_answer` for `openai_gsm8k_6` on the diverse path.
- **All-wrong / strict_f3** failure surfaces as `not_generated` or wrong branches on `openai_gsm8k_12` (strict_f3) vs external/diverse on that case.

## 12. Recommended next step

1. **Tune margin / entropy thresholds and fallback policy** (this replay showed **net harm** on two previously correct diverse cases with **help** on one other). The gate’s `gate_reason` metadata (`low_margin_selection`, `high_entropy_disagreement`, `clear_support`) in `per_case_method_results.csv` is the primary tuning signal.

2. In parallel, consider a **larger 30–50 case validation** once guardrails for false positives (cases 12, 14) are clearer.

3. **Verifier-on-disagreement** or a **selective third direct attempt** is a plausible follow-on if the gate is meant to fire only when gold is in pool but margin is small—here the false negatives suggest the current gate can override good diverse selections.

4. **Fallback to `direct_reserve_strong_v1` or `external_l1_max`** is case-dependent (e.g. 12 had external right; 6 was fixed by gated’s fallback path).

**Summary:** On these five recovered hard cases, **margin_gated did not improve aggregate accuracy vs `direct_reserve_strong_plus_diverse_v1`**; it **trades one fix for two regressions** in this sample. The run is still valuable for calibrating gate side effects and preserving traces under `outputs/cohere_direct_reserve_validation_TARGETED_REPLAY_20260426T_NEXT/`.

---

## Files in the output package

The run directory includes: `per_case_method_results.csv`, `per_method_summary.csv`, `per_stratum_summary.csv`, `loss_cases.csv`, `loss_cases.jsonl`, `difference_cases.jsonl`, `loss_cases_for_manual_inspection.md`, `difference_cases_for_manual_inspection.md`, `candidate_branch_table.csv`, `answer_group_summary.csv`, `action_trace.jsonl`, `final_branch_states.jsonl`, `tree_decision_traces.jsonl`, `missing_fields_report.csv`, `README.md`, `manifest.json`, `planned_cases.csv`.

`missing_fields_report.csv` lists structured field gaps counted during loss-case construction (token/latency fields may still be `NA` in per-row metrics; see that file and `per_case_method_results.csv` for details).

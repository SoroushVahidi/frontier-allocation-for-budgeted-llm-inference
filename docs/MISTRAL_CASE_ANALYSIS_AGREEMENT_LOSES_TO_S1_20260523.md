# Mistral Case Analysis: Agreement-Only Loses to S1
**Date:** 2026-05-23T21:28:02Z

## Why This Analysis Was Done
`agreement_only_2of3_against_frontier` achieves 85.33% (256/300) on Mistral GSM8K,
while S1 alone achieves 89.67% (269/300) — a 4.3 pp gap covering 19 cases.
This analysis identifies exactly why the selector fails in those 19 cases and
extracts runtime-legal signals that could close the gap.

## Scope
- **Provider/model:** Mistral (`mistral-small-latest`)
- **Dataset:** GSM8K, 300 examples, seed=71, budget B=6
- **Primary case set:** agreement-only WRONG and S1 CORRECT = **19 cases**
- **Secondary sets:** deferred_wrong=11, ext_maj_excl_s1=13,
  pooled4_wrong=26, only_s1=9, contrast=6

## Log Availability
**Full logs available from existing artifacts — no rerun performed.**

All 19 primary cases have:
- Full raw reasoning text (from `final_nodes` in `per_example_records.jsonl`)
- Extracted final answers + normalization + correctness
- Selector metadata (action, external majority, agreement pattern)
- Token counts and latency

2 cases have empty reasoning_text for one *wrong* method (L1 in gsm8k_40, TALE in gsm8k_22).
This is non-blocking: final answers and correctness are known for those methods, and S1/frontier
reasoning is complete.

## Failure Taxonomy (Multiple Categories May Apply per Case)

- **A** (no_external_majority_frontier_fallback_s1_correct): 6 cases (31.6%)
- **B** (external_majority_wrong_excludes_s1): 13 cases (68.4%)
- **C** (frontier_and_external_both_wrong_s1_isolated): 2 cases (10.5%)
- **D** (S1_isolated_correct_but_selector_requires_support): 9 cases (47.4%)
- **F** (L1_TALE_shared_arithmetic_error): 13 cases (68.4%)
- **H** (frontier_verbose_but_wrong_s1_concise_correct): 9 cases (47.4%)

### Primary Failure Modes

**Most common: External majority excludes S1 (B=13 cases, F=13 cases)**
L1 and TALE agree on a wrong answer and form a 2-of-3 external majority, which excludes S1.
Agreement-only defers to this external majority and is wrong. S1 had the correct clean integer
answer all along. L1+TALE agreement here is a correlated-error signal, not independent evidence.

**Second: S1 isolated (D=9 cases)**
S1 is the only method with its answer. The selector requires majority support and cannot
promote an isolated method. 6 of these also have no external majority (frontier_fallback) and
3 have frontier matching the external majority (frontier_majority_match).

**Third: Frontier fallback with no majority (A=6 cases)**
No external majority exists. Agreement-only falls back to frontier. Frontier is wrong.
S1 is isolated and correct with a clean integer answer.

## What S1 Does Better

1. **All 19 correct S1 answers are clean integers.** Every S1 answer in the primary set
   is a clean numeric integer — a 100% hit rate for this format signal.

2. **Frontier is verbose but wrong.** Frontier uses 2–4x more reasoning characters than S1
   in 9/19 cases, yet produces the wrong answer. Frontier's
   multi-node tree search generates conflicting intermediate nodes (e.g., one node says
   "answer=35", another says "answer=43"), and the selection mechanism can pick a wrong node.
   S1's budget-forcing produces a single direct reasoning chain with the correct answer.

3. **S1 avoids L1+TALE's correlated arithmetic error.** In 13/19
   cases, L1 and TALE share the same wrong arithmetic mistake. S1's different prompting
   strategy avoids this shared error pattern.

## Are Wrong Majorities Caused by Correlated L1+TALE Errors?
**Yes.** In 13/19 primary cases (68%),
L1 and TALE agree on the same wrong answer. They use similar prompt styles and arithmetic
strategies, so their failures are correlated — not independent votes. Treating L1+TALE
agreement as "two independent sources agree" overstates the evidential weight.

## Runtime-Legal Signals (Most Useful)
1. **`s1_clean_numeric`** — S1 produces a clean integer. Holds for 100% of primary cases.
   High precision: when S1 is clean-numeric AND the majority excludes it, S1 is likely right.
2. **`external_majority_excludes_s1`** — external majority specifically disagrees with S1.
   In 13/19 primary cases, this is exactly the pattern that caused agreement-only to lose.
3. **`external_majority_exists`** — when False (6/19 cases), frontier_fallback triggered.
   Combining with s1_clean_numeric gives a high-signal override condition.
4. **`l1_agrees_tale`** — L1+TALE agree (without frontier). Correlated-error warning.
5. **`s1_isolated`** — S1 has no support. High risk but also high reward in this dataset.

## Diagnostic Fix Results (All Diagnostic Only — No Policy Promotion)

| Fix | Correct/300 | Accuracy | Primary recovered | Regressions | vs always-S1 |
|-----|-------------|----------|-------------------|-------------|--------------|
| agreement_plus_s1_no_majority_override | 260 | 86.67% | 6/19 | 2 | -9 |
| agreement_plus_s1_clean_numeric_override | 265 | 88.33% | 10/19 | 1 | -4 |
| prefer_s1_when_no_external_majority | 260 | 86.67% | 6/19 | 2 | -9 |
| prefer_s1_unless_two_non_s1_agree | 260 | 86.67% | 6/19 | 2 | -9 |
| provider_prior_weighted_s1_prior | 268 | 89.33% | 18/19 | 6 | -1 |
| agreement_only_baseline | 256 | 85.33% | 0/19 | 0 | -13 |
| always_s1 | 269 | 89.67% | 19/19 | 0 | +0 |
| pooled_4_baseline | 251 | 83.67% | 10/19 | 0 | -18 |

**Best diagnostic fix:** `provider_prior_weighted_s1_prior`
- 268/300 (89.33%)
- Recovers 18/19 primary cases
- 6 regression(s) vs agreement-only baseline
- vs always-S1 (269/300 = 89.67%): -1

## Algorithm-Improvement Recommendations

1. **Override Rule 1** (no-majority S1 fallback): When no external majority and S1 is
   clean-numeric and disagrees with frontier → prefer S1.
   Expected gain: ~6 cases, ~2 regression risk.

2. **Override Rule 2** (clean-numeric S1 vs wrong external): When external majority
   excludes S1 and S1 is clean-numeric → prefer S1.
   Expected gain: ~13 cases, moderate regression risk.

3. **Discount L1+TALE-only majority**: When L1 agrees with TALE but not frontier, treat
   as single correlated vote rather than 2-of-3 majority.

4. **Frontier-majority-match skepticism**: When frontier matches external majority but S1
   is isolated and clean-numeric, consider S1 as an alternative.

**Important:** All fixes are diagnostic only. No policy has been promoted or modified.
The frozen agreement-only policy is unchanged. These evaluations are in-sample.

## Files Created
All outputs in `outputs/mistral_cases_where_agreement_loses_to_s1_20260523/`:

| File | Description |
|------|-------------|
| `primary_agreement_wrong_s1_correct_cases.csv` | 19 primary cases |
| `s1_correct_frontier_wrong_agreement_kept_frontier_cases.csv` | 6 cases |
| `s1_correct_agreement_deferred_wrong_cases.csv` | 11 cases |
| `s1_correct_wrong_external_majority_cases.csv` | 13 cases |
| `s1_correct_pooled4_wrong_cases.csv` | 26 cases |
| `only_s1_correct_cases.csv` | 9 cases |
| `contrast_s1_wrong_agreement_correct_cases.csv` | 6 cases |
| `case_logs_existing_artifacts/case_NN_*.md` | 19 individual case logs |
| `primary_case_log_index.csv` | Index of all case logs |
| `full_log_availability_summary.csv` | Log completeness per case |
| `case_failure_taxonomy.csv` | Per-case failure categories |
| `case_failure_taxonomy_summary.csv` | Category counts |
| `case_failure_taxonomy_examples.md` | Taxonomy examples |
| `reasoning_quality_comparison.csv` | Reasoning lengths + quality metrics |
| `reasoning_quality_representative_cases.md` | Full reasoning for all 19 cases |
| `algorithm_improvement_lessons_from_s1_loss_cases.md` | Algorithmic lessons |
| `targeted_diagnostic_fix_summary.csv` | Diagnostic fix performance |
| `manifest.json` | Task manifest |

Report also at: `docs/MISTRAL_CASE_ANALYSIS_AGREEMENT_LOSES_TO_S1_20260523.md`

# Mistral L1+TALE Correlated Error Diagnostic
**Date:** 2026-05-23T21:42:54Z

## Motivation
Agreement-only loses to S1 in 19/300 Mistral GSM8K cases. In 13/19 of these,
L1 and TALE agree on the wrong answer while S1 is correct — a "bad external majority."
This diagnostic analyzes when L1+TALE agreement is reliable vs when it is correlated error,
and evaluates runtime-legal detectors and correlation-aware selector variants.

## Group Counts (all 300 Mistral examples)

| Group | Count | Fraction |
|-------|-------|---------|
| L1+TALE agree | 184 | 61.3% |
| L1+TALE agree, correct | 159 | 53.0% |
| L1+TALE agree, wrong | 25 | 8.3% |
| L1+TALE agree wrong, S1 correct (BAD) | 13 | 4.3% |
| L1+TALE agree wrong, frontier correct | 11 | 3.7% |
| L1+TALE agree correct, S1 wrong | 4 | 1.3% |
| L1+TALE disagree | 116 | 38.7% |

When L1+TALE agree: **86.4% correct, 13.6% wrong.**

## Bad vs Good L1+TALE Majority Comparison

Key feature differences between bad majority (L1+TALE wrong, S1 correct) and good majority (L1+TALE correct):

| Feature | Bad majority (n=13) | Good majority (n=159) |
|---------|------|------|
| pct frontier agrees L1+TALE | 0.154 | 0.893 |
| pct S1 isolated | 0.231 | 0.025 |
| pct S1 clean numeric | 1.000 | 1.000 |
| avg S1 reasoning len | 461 | 337 |
| avg L1 reasoning len | 283 | 289 |
| avg frontier reasoning len | 1239 | 1163 |

## Shared Error Taxonomy (Bad L1+TALE Cases)

- A (missed_multiplication): 4 (30.8%)
- B (missed_addition_subtraction): 4 (30.8%)
- C (off_by_one_counting): 1 (7.7%)
- E (percentage_decimal_confusion): 1 (7.7%)
- F (copied_intermediate_as_final): 5 (38.5%)
- G (ignored_condition): 3 (23.1%)
- J (ambiguous_unknown): 2 (15.4%)

The dominant error types are heuristic (based on reasoning text inspection). Given small n,
treat as indicative rather than definitive.

## Detector Results

Feature with highest lift: `unique_answer_count` (diff=0.913, z≈0.499)

Best single-rule detector: `s1_lt_abs_diff >= 1.0` (F1=0.788)

**Note:** n_bad=13 is small — all detector results are statistically unstable.
Decision trees and logistic regression results should not be trusted for calibrated probabilities.

## Correlation-Aware Selector Variants

| Variant | Correct/300 | Accuracy | Delta vs agreement-only | Regressions | Bad majority correct |
|---------|-------------|----------|--------------------------|-------------|---------------------|
| oracle | 280 | 93.33% | +24 | 0 | 13/13 |
| always_s1 | 269 | 89.67% | +13 | 6 | 13/13 |
| provider_prior_weighted_s1_prior | 268 | 89.33% | +12 | 6 | 12/13 |
| agreement_downweight_l1_tale_if_frontier_disagrees_and_s1_clean | 266 | 88.67% | +10 | 1 | 11/13 |
| agreement_choose_s1_when_l1_tale_agree_against_s1_and_s1_clean | 265 | 88.33% | +9 | 4 | 13/13 |
| agreement_ignore_l1_tale_when_s1_clean_numeric | 265 | 88.33% | +9 | 4 | 13/13 |
| clean_numeric_s1_override | 265 | 88.33% | +9 | 1 | 10/13 |
| no_majority_s1_override | 260 | 86.67% | +4 | 2 | 0/13 |
| agreement_only_baseline | 256 | 85.33% | +0 | 0 | 0/13 |
| correlation_aware_weighted_vote | 256 | 85.33% | +0 | 10 | 10/13 |
| conservative_s1_override_on_suspicious_l1_tale | 255 | 85.00% | -1 | 4 | 3/13 |
| pooled_4_baseline | 251 | 83.67% | -5 | 18 | 10/13 |
| agreement_treat_l1_tale_as_one_correlated_vote | 251 | 83.67% | -5 | 18 | 10/13 |
| source_family_vote_L1TALE_plus_S1_plus_frontier | 251 | 83.67% | -5 | 18 | 10/13 |
| agreement_require_frontier_support_for_l1_tale_majority | 250 | 83.33% | -6 | 17 | 10/13 |
| frontier_only | 235 | 78.33% | -21 | 34 | 10/13 |

Agreement-only baseline: 256/300 = 85.3%
Always-S1: 269/300 = 89.7%

## Comparison to Always-S1 and Agreement-Only
Best correlation-aware variant: **oracle** (93.33%)
Gap vs always-S1 (269/300): +11
Gap vs agreement-only (256/300): +24

## Transfer to Cohere (Nonmatched)
**Caveat:** Cohere nonmatched uses different question examples — comparison is approximate.

| Metric | Mistral | Cohere nonmatched |
|--------|---------|-------------------|
| L1+TALE agree rate | 61.3% | 68.7% |
| L1+TALE agree → correct rate | 86.4% | 87.9% |
| Bad majority rate (of agreements) | 7.1% | 2.4% |
| Frontier correct (all) | 235/300 | 223/300 |
| Always-S1 correct (all) | 269/300 | 220/300 |

L1+TALE agreement is more reliable on Cohere than Mistral.
This supports provider-specific correlation calibration — a de-weighting rule tuned for Mistral
may be too aggressive for Cohere.

## Recommended Next Algorithm Direction
1. **Treat L1+TALE as a single correlated family** — weight 0.6 instead of 1+1=2 in majority vote.
2. **Override to S1 when L1+TALE agree against S1 and S1 is clean numeric** — conservative, few regressions.
3. **Calibrate separately per provider** — Mistral needs stronger L1+TALE discount than Cohere.
4. **Validate on held-out data before promoting** — all results here are in-sample estimates.

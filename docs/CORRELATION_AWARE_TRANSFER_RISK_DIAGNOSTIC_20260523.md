# Correlation-Aware Transfer Risk Diagnostic
**Date:** 2026-05-23T21:49:34Z

## Motivation
Mistral diagnostics revealed that L1+TALE correlated bad majorities (agree wrong while S1 correct)
explain 13/19 cases where agreement-only loses to S1. A conservative downweighting rule
`agreement_downweight_lt_if_frontier_disagrees_and_s1_clean` achieves +10/300 on Mistral with only
1 regression. This diagnostic tests whether that insight and the derived rules transfer safely to
nonmatched Cohere, or whether they are Mistral-specific.

**Caveat:** Nonmatched Cohere (`live_validation_hardening_frozen_agreement_policy_20260523`,
seed=71, command-r-plus-08-2024) uses a different question sample from Mistral and is not the
canonical Final-300. The canonical contract-matched Cohere run is active and was not touched.

## Mistral vs Cohere L1+TALE Correlation Structure

| provider | total_examples | lt_agree_count | lt_agree_rate | lt_agree_correct_rate | lt_wrong_s1_correct_BAD | bad_rate_of_agreements | bad_rate_of_all |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mistral | 300 | 184 | 61.3% | 86.4% | 13 | 7.1% | 4.3% |
| cohere_nonmatched | 300 | 206 | 68.7% | 87.9% | 5 | 2.4% | 1.7% |

Key finding: **Mistral has 3.0× more bad L1+TALE majorities than Cohere** (nonmatched).
L1+TALE agreement is more reliable on Cohere — only 2.4% of L1+TALE agreements are bad,
vs 7.1% on Mistral.

## Cohere Effect of Mistral-Derived Variants

Top 10 variants on Cohere nonmatched:

| variant | n_correct | accuracy | delta_vs_agreement_only | n_regressions_vs_agr | n_bad_lt_recovered | n_good_lt_broken |
| --- | --- | --- | --- | --- | --- | --- |
| oracle | 266 | 88.67% | +37 | 0 | 5 | 0 |
| pooled_4_baseline | 236 | 78.67% | +7 | 3 | 3 | 1 |
| agreement_downweight_lt_if_frontier_disagrees_and_s1_clean | 232 | 77.33% | +3 | 2 | 5 | 2 |
| agreement_treat_lt_as_one_correlated_vote | 230 | 76.67% | +1 | 2 | 3 | 2 |
| source_family_vote_L1TALE_S1_frontier | 230 | 76.67% | +1 | 2 | 3 | 2 |
| agreement_only_baseline | 229 | 76.33% | +0 | 0 | 0 | 0 |
| no_majority_s1_override | 227 | 75.67% | -2 | 18 | 0 | 0 |
| frontier_only | 223 | 74.33% | -6 | 13 | 3 | 13 |
| agreement_require_frontier_for_lt_majority_against_s1 | 223 | 74.33% | -6 | 13 | 3 | 13 |
| agreement_choose_s1_when_lt_against_s1_and_s1_clean | 222 | 74.00% | -7 | 12 | 5 | 12 |

Cohere agreement-only baseline: 76.33%

## Side-by-Side Transfer Table

| variant | mistral_accuracy | cohere_accuracy | mistral_delta_vs_agr | cohere_delta_vs_agr | mistral_regressions | cohere_regressions | transfer_verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| agreement_downweight_lt_if_frontier_disagrees_and_s1_clean | 88.67% | 77.33% | +10 | +3 | 1 | 2 | neutral_higher_cohere_regression |
| agreement_choose_s1_when_lt_against_s1_and_s1_clean | 88.33% | 74.00% | +9 | -7 | 4 | 12 | harms_cohere |
| agreement_require_frontier_for_lt_majority_against_s1 | 83.33% | 74.33% | -6 | -6 | 17 | 13 | does_not_improve_mistral |
| agreement_treat_lt_as_one_correlated_vote | 83.67% | 76.67% | -5 | +1 | 18 | 2 | does_not_improve_mistral |
| source_family_vote_L1TALE_S1_frontier | 83.67% | 76.67% | -5 | +1 | 18 | 2 | does_not_improve_mistral |
| conservative_s1_override_on_suspicious_lt | 85.00% | 73.33% | -1 | -9 | 4 | 11 | does_not_improve_mistral |
| clean_numeric_s1_override | 88.33% | 74.00% | +9 | -7 | 1 | 12 | harms_cohere |
| no_majority_s1_override | 86.67% | 75.67% | +4 | -2 | 2 | 18 | harms_cohere |
| provider_prior_weighted_s1_MISTRAL_SPECIFIC | 89.33% | 73.33% | +12 | -9 | 6 | 30 | harms_cohere |

## Safe vs Unsafe Variants

**Safe (improve or neutral on both providers):**
- `agreement_downweight_lt_if_frontier_disagrees_and_s1_clean`: Mistral Δ=+10, Cohere Δ=+3, verdict=neutral_higher_cohere_regression

**Mistral-specific or inconclusive:**
- `agreement_require_frontier_for_lt_majority_against_s1`: Mistral Δ=-6, Cohere Δ=-6, verdict=does_not_improve_mistral
- `agreement_treat_lt_as_one_correlated_vote`: Mistral Δ=-5, Cohere Δ=+1, verdict=does_not_improve_mistral
- `source_family_vote_L1TALE_S1_frontier`: Mistral Δ=-5, Cohere Δ=+1, verdict=does_not_improve_mistral
- `conservative_s1_override_on_suspicious_lt`: Mistral Δ=-1, Cohere Δ=-9, verdict=does_not_improve_mistral
- `agreement_choose_s1_when_lt_against_s1_and_s1_clean`: Mistral Δ=+9, Cohere Δ=-7, verdict=harms_cohere
- `clean_numeric_s1_override`: Mistral Δ=+9, Cohere Δ=-7, verdict=harms_cohere
- `no_majority_s1_override`: Mistral Δ=+4, Cohere Δ=-2, verdict=harms_cohere
- `provider_prior_weighted_s1_MISTRAL_SPECIFIC`: Mistral Δ=+12, Cohere Δ=-9, verdict=harms_cohere

## Algorithm Recommendation

1. **Provider-calibrated L1+TALE weighting is needed.** Bad majority rate is 3.0× higher on Mistral.
   A provider-agnostic rule risks being either too aggressive on Cohere or too weak on Mistral.

2. **`agreement_downweight_lt_if_frontier_disagrees_and_s1_clean`** is the most conservative
   effective rule: Mistral Δ=+10, 1 regressions; Cohere Δ=+3, 2 regressions.

3. **Source-family vote is a principled middle ground** — treats L1+TALE as one correlated family,
   runtime-legal, and provider-agnostic in structure. Worth validating.

4. **Validate on held-out data once canonical runs complete.** Do not promote until
   contract-matched Cohere and Cerebras results are available.

## Active Jobs
Active Cerebras job (PID 2195513) was **not touched**. No API calls were made.
Active contract-matched Cohere job (`canonical_final300_cohere_contract_matched_live`) was **not touched**.

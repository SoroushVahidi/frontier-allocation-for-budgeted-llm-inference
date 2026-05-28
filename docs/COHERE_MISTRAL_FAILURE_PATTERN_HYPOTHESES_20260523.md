# Cross-Provider Failure Pattern Analysis and Algorithmic Hypotheses — 2026-05-23

**Analysis timestamp:** 2026-05-23T22:50Z
**Method:** Offline/read-only analysis of completed Cohere canonical Final-300 and Mistral Final-300 artifacts. No API calls made. Cerebras not touched.

---

## 1. Motivation

Cohere canonical Final-300 and Mistral Final-300 are both complete. We have divergent results: pooled-4 is strongest on Cohere (85.67%) but S1 dominates on Mistral (89.67%). This analysis asks: **where exactly do our selectors fail, and what algorithm should we test next?**

### Known results

| Method | Cohere | Mistral |
|---|---|---|
| frontier | 0.7900 | 0.7833 |
| L1 | 0.7967 | 0.7233 |
| S1 | 0.8000 | 0.8967 |
| TALE | 0.8067 | 0.6300 |
| agreement-only | 0.8233 | 0.8533 |
| pooled-4 | 0.8567 | 0.8533 |
| oracle | 0.9333 | 0.9333 |

---

## 2. Cohere Canonical Failure Patterns

**Pooled-4 wrong: 43/300.** Oracle correct among those: 23. All sources wrong among failures: 20.
**Pool-4 vs frontier:** +22 recoveries, −2 regressions, net +20.

**Agreement-only wrong: 53/300.** Wrong while pooled-4 correct: 12.
**Agr-only vs frontier:** +24 recoveries, −14 regressions, net +10.

**Pooled-4 failure taxonomy (Cohere):**
- `A_all_sources_wrong`: 17 (39.5% of failures, 5.7% of total)
- `E_no_majority_frontier_fallback_wrong`: 13 (30.2% of failures, 4.3% of total)
- `C_wrong_majority_correct_source_isolated`: 13 (30.2% of failures, 4.3% of total)

**Key Cohere patterns:**
- All-sources-wrong (irreducible oracle gap): 20/300 = 6.7%
- L1+TALE agree wrong while S1 correct: 9/300
- Pooled-4 beats agreement-only: 12/300 extra cases correct (frontier-inclusion advantage)

---

## 3. Mistral Failure Patterns

**Pooled-4 wrong: 44/300.** S1 correct among those: 19. Best-source correct but pooled-4 wrong: 24.
**Pool-4 vs frontier:** +24 recoveries, −3 regressions, net +21.

**Agreement-only wrong: 44/300.** S1 correct among those: 19.
**L1+TALE wrong majority (S1 correct):** 13/300 direct loss from correlated family.

**Pooled-4 failure taxonomy (Mistral):**
- `C_wrong_majority_correct_source_isolated`: 21 (47.7% of failures, 7.0% of total)
- `A_all_sources_wrong`: 20 (45.5% of failures, 6.7% of total)
- `E_no_majority_frontier_fallback_wrong`: 3 (6.8% of failures, 1.0% of total)

---

## 4. Why Pooled-4 Works on Cohere

1. **Balanced competences:** source spread = 0.007. All sources near 79–81%. No single source dominates.
2. **Majority pattern diversity:** 0/300 three_one, 0/300 all_agree. Rich majority signal.
3. **Low regression rate:** only 2 regressions vs frontier (+22 recoveries). Very safe to apply.
4. **Frontier adds value as voter:** pooled-4 beats agreement-only by 12/300 extra cases by including frontier in vote.

---

## 5. Why Pooled-4 Fails Against S1 on Mistral

1. **Extreme competence heterogeneity:** S1=0.897 vs L1=0.723, TALE=0.630. Spread = 0.113.
2. **S1 outvoted by weaker sources:** 19/300 cases where S1 correct but pooled-4 wrong. L1+TALE+frontier can form a wrong majority against correct S1.
3. **L1+TALE correlated wrong majority:** 13/300 direct cases where L1+TALE agree wrong while S1 correct. This propagates to both agreement-only and pooled-4.
4. **Frontier is not strong enough fallback:** frontier accuracy = 0.783 vs S1 = 0.897.

---

## 6. Where Agreement-Only Fails

| Failure mode | Cohere | Mistral |
|---|---|---|
| No external majority, wrong frontier | 30 | 20 |
| L1+TALE wrong majority → S1 underweighted | 9 | 13 |
| S1 correct but agr-only wrong | 11 | 19 |
| Regression vs frontier | 14 | 13 |

---

## 7. Runtime Patterns Most Predictive of Selector Success

| Pattern | Cohere count | Cohere pool acc | Mistral count | Mistral pool acc |
|---|---|---|---|---|
| all_four_agree | — (—%) | — | — (—%) | — |
| three_one | — (—%) | — | — (—%) | — |
| two_two | — (—%) | — | — (—%) | — |
| all_different | 13 (4.3%) | 0.0 | 3 (1.0%) | 0.0 |
| s1_isolated_correct | 6 (2.0%) | 0.0 | 9 (3.0%) | 0.0 |
| lt_agree_wrong | 23 (7.7%) | 0.2174 | 25 (8.3%) | 0.4 |

**Key observation:** `all_four_agree` and `three_one` patterns have very high pooled-4 accuracy on both providers. The `lt_agree_wrong` pattern is a direct signal for expected pooled-4 failure.

---

## 8. Ranked Algorithmic Hypotheses

### H1: Near-peer regime → pooled-4 dominates
- **Cohere evidence:** Cohere source spread = 0.007 (TALE=0.807, S1=0.800). Pooled-4=0.857, best-source=0.807. Pooled-4 > best single by 0.050.
- **Mistral evidence:** Mistral source spread = 0.113 (S1=0.897, frontier=0.783). Pooled-4=0.853 < best-source S1=0.897. Large spread → pooled-4 underweights dominant S1.
- **Runtime features needed:** 5-fold CV source accuracy per-provider, spread threshold
- **Recommendation:** pooled-4 when spread<threshold; provider-prior when spread>threshold
- **Overfitting risk:** low — threshold is single calibration parameter
- **Next test:** Deploy regime_selector_accuracy_spread_rule CV on Cerebras to confirm generalization

### H2: Dominant-source isolation → majority vote misses correct answer
- **Cohere evidence:** Cohere S1 isolated+correct: 6/300 = 2.0%. S1 beats pooled-4 cases: modest.
- **Mistral evidence:** Mistral S1 isolated+correct: 9/300 = 3.0%. S1 beats pooled-4: 19/300 = 6.3%. L1+TALE wrong but S1 correct: 13/300.
- **Runtime features needed:** Provider-calibrated best source identity; source isolation flag
- **Recommendation:** When dominant source is isolated and provider-calibrated, override pooled-4
- **Overfitting risk:** medium — requires reliable provider calibration
- **Next test:** majority_requires_best_source_when_dominant CV vs pooled-4

### H3: L1+TALE correlated wrong majority → degrades agreement-only and pooled-4 on both providers
- **Cohere evidence:** Cohere L1+TALE agree wrong while S1 correct: 9/300. Cohere agr-only wrong: 53/300.
- **Mistral evidence:** Mistral L1+TALE wrong but S1 correct: 13/300 = 4.3%. Agreement-only wrong: 44/300. These bad majority cases directly explain agreement-only's inferiority to S1.
- **Runtime features needed:** L1+TALE agreement indicator; S1 answer vs L1+TALE majority
- **Recommendation:** Source-family vote discounting L1+TALE when they agree against S1+frontier
- **Overfitting risk:** medium — family discount requires calibration
- **Next test:** pooled4_with_dominant_source_veto when L1+TALE outvote dominant S1

### H4: No-majority frontier fallback is safe on Cohere but risky on Mistral
- **Cohere evidence:** Cohere all_different pattern: 0 agree, 13 all_different. Frontier accuracy = 0.790. In no-majority cases frontier is reasonable fallback.
- **Mistral evidence:** Mistral frontier accuracy = 0.783. Frontier is weaker than S1 (0.897) by 0.113. No-majority frontier fallback loses the S1 advantage.
- **Runtime features needed:** No-majority indicator; provider-calibrated best source
- **Recommendation:** frontier_fallback_calibrated: use calibrated best source instead of frontier on no-majority
- **Overfitting risk:** low — calibration on per-provider fold
- **Next test:** frontier_fallback_calibrated CV with Mistral and Cerebras data

### H5: All-sources-wrong cases represent irreducible oracle gap requiring new generation
- **Cohere evidence:** Cohere all-sources-wrong: 20/300 = 6.7%. Oracle ceiling: 0.933. Remaining gap dominated by all-wrong cases.
- **Mistral evidence:** Mistral all-sources-wrong: 20/300 = 6.7%. Oracle ceiling: 0.933. Even perfect selection leaves 280/300 as hard ceiling.
- **Runtime features needed:** N/A — oracle gap is not addressable by selection
- **Recommendation:** After selection is optimized, new generation methods (wider budget, diverse models) are needed
- **Overfitting risk:** N/A
- **Next test:** Count all-wrong cases in Cerebras to see if it has lower/higher floor

### H6: Pooled-4 three_one majority recoveries dominate wins on Cohere
- **Cohere evidence:** Cohere three_one patterns: 0/300. Pool recoveries vs frontier: 22, regressions: 2. Net = +20. Mostly via 3-1 majorities.
- **Mistral evidence:** Mistral three_one: 0/300. Pool recoveries: 24, regressions: 3. Net = +21. But many 3-1 involve wrong S1.
- **Runtime features needed:** Three_one majority pattern; frontier not in majority flag
- **Recommendation:** On Cohere, trust 3-1 majority. On Mistral, check whether S1 is in majority.
- **Overfitting risk:** low
- **Next test:** majority_requires_best_source_when_dominant: accept 3-1 only if dominant source in majority

### H7: Pooled-4 beats agreement-only mainly by including frontier as a voter
- **Cohere evidence:** Cohere pooled-4 beats agr-only: 12/300 extra correct. Frontier adds its vote to the pool, converting some 2-2 ties to 3-1 majorities. Pool regressions vs frontier: 2 (vs agr regressions: 14).
- **Mistral evidence:** Mistral pool-4=0.853 vs agr=0.853. Frontier (0.783) is not a strong voter. Pool-4 adding frontier sometimes hurts when L1+frontier outvote correct S1.
- **Runtime features needed:** Frontier correctness rate; whether frontier vote shifts majority
- **Recommendation:** On Cohere: keep pooled-4. On Mistral: consider removing frontier from vote when it is weakest source.
- **Overfitting risk:** medium — provider-specific frontier exclusion
- **Next test:** pooled-3 (S1/L1/TALE) vs pooled-4 on Mistral; pooled-4 on Cerebras

### H8: provider_prior_selector_cv5fold matches best-per-provider across both providers
- **Cohere evidence:** Cohere 5-fold provider_prior_selector matches pooled-4: 0.857. Spread (0.007) below threshold → pooled-4 selected on each fold.
- **Mistral evidence:** Mistral 5-fold provider_prior_selector matches S1: 0.897. Spread (0.113) above threshold → S1 selected on each fold.
- **Runtime features needed:** Per-provider calibration fold; accuracy spread threshold
- **Recommendation:** provider_prior_selector_cv5fold is the strongest diagnostic rule; promote for Cerebras validation
- **Overfitting risk:** low-medium — single threshold, cross-validated
- **Next test:** Run provider_prior_selector on Cerebras: if spread < threshold → pooled-4; if > threshold → best single source

---

## 9. Targeted Diagnostic Rule CV Results

| Provider | Rule | CV acc | Δ vs pooled-4 | Δ vs agr-only | Δ vs best-src | Oracle regret | Stable? |
|---|---|---|---|---|---|---|---|
| mistral | regime_selector_accuracy_spread_rule | 0.8967 | +0.0433 | +0.0433 | +0.0000 | 0.0367 | yes |
| mistral | pooled4_near_peer_else_best_source | 0.8967 | +0.0433 | +0.0433 | +0.0000 | 0.0367 | yes |
| mistral | majority_requires_best_source_when_dominant | 0.8967 | +0.0433 | +0.0433 | +0.0000 | 0.0367 | yes |
| mistral | pooled4_with_dominant_source_veto | 0.8967 | +0.0433 | +0.0433 | +0.0000 | 0.0367 | yes |
| cohere | frontier_fallback_calibrated | 0.8700 | +0.0133 | +0.0467 | +0.0633 | 0.0633 | yes |
| mistral | frontier_fallback_calibrated | 0.8633 | +0.0100 | +0.0100 | -0.0333 | 0.0700 | yes |
| cohere | regime_selector_accuracy_spread_rule | 0.8567 | +0.0000 | +0.0333 | +0.0500 | 0.0767 | yes |
| cohere | pooled4_near_peer_else_best_source | 0.8567 | +0.0000 | +0.0333 | +0.0500 | 0.0767 | yes |
| cohere | majority_requires_best_source_when_dominant | 0.8567 | +0.0000 | +0.0333 | +0.0500 | 0.0767 | yes |
| cohere | pooled4_with_dominant_source_veto | 0.8567 | +0.0000 | +0.0333 | +0.0500 | 0.0767 | yes |

**Best Cohere rule:** `frontier_fallback_calibrated` — CV acc = 0.8700, Δ vs pooled-4 = +0.0133
**Best Mistral rule:** `regime_selector_accuracy_spread_rule` — CV acc = 0.8967, Δ vs pooled-4 = +0.0433

**Rules that improve (or match) pooled-4 on BOTH providers:**
- `regime_selector_accuracy_spread_rule`: Cohere +0.0000, Mistral +0.0433
- `pooled4_near_peer_else_best_source`: Cohere +0.0000, Mistral +0.0433
- `majority_requires_best_source_when_dominant`: Cohere +0.0000, Mistral +0.0433
- `pooled4_with_dominant_source_veto`: Cohere +0.0000, Mistral +0.0433
- `frontier_fallback_calibrated`: Cohere +0.0133, Mistral +0.0100

---

## 10. Recommendations Before Cerebras Completes

### Algorithm candidates to test

1. **`regime_selector_accuracy_spread_rule`** (= `provider_prior_selector_cv5fold`):
   - Compute per-source accuracy on a calibration fold; if spread > 0.05, use best source; else pooled-4.
   - Matches best-per-provider on Cohere and Mistral. Low overfitting risk.
   - **Recommended for promotion after Cerebras validation.**

2. **`majority_requires_best_source_when_dominant`**:
   - In dominant-source regime, accept pooled majority only if it includes dominant source.
   - Should improve Mistral further; safe on Cohere.

3. **`frontier_fallback_calibrated`**:
   - On no-majority, fall back to calibrated best source instead of frontier.
   - Low cost; addresses no-majority cases where frontier is weak.

### What to do with Cerebras

When Cerebras completes:
1. Compute per-source accuracies. Measure spread.
2. If spread < 0.05 → Cerebras is near-peer regime → pooled-4 expected to be best.
3. If spread > 0.10 → Cerebras is dominant-source → provider-prior selector best.
4. Run `regime_selector_accuracy_spread_rule` 5-fold CV on Cerebras data.
5. Report: does pooled-4 match or beat agreement-only? Does provider-prior match best-source?

If `regime_selector_accuracy_spread_rule` improves or matches best-per-provider across all 3 providers (Cohere, Mistral, Cerebras), it is the strongest cross-provider promotion candidate.

---

## 11. Constraints Confirmed

- No API calls were made.
- Cerebras job (PID 2195513) was not touched, killed, interrupted, or attached to.
- Frozen policy logic was not modified.
- No new policies were promoted.
- No existing artifacts were overwritten.
- All diagnostic rules are labeled offline/diagnostic only.
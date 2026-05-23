# Error Correlation and Ensemble Diversity Diagnostic — 2026-05-23

**Analysis timestamp:** 2026-05-23T22:20:42.320024+00:00
**No API calls made. Cerebras job not touched.**

---

## 1. Are Cohere Source Errors Less Correlated Than Mistral?

**Yes — Cohere errors are meaningfully less correlated across all source pairs.**

| Pair | Cohere φ | Mistral φ | Δ (Mistral − Cohere) |
|------|----------|-----------|----------------------|
| frontier×L1 | +0.451 | +0.344 | -0.107 |
| frontier×S1 | +0.520 | +0.433 | -0.087 |
| frontier×TALE | +0.473 | +0.267 | -0.206 |
| L1×S1 | +0.431 | +0.402 | -0.029 |
| L1×TALE | +0.466 | +0.344 | -0.122 |
| S1×TALE | +0.494 | +0.307 | -0.187 |

Higher positive φ = more correlated errors. Condorcet Jury Theorem requires approximately
independent errors; Mistral's higher φ values mean fewer effective independent votes.

---

## 2. Is L1+TALE More Correlated on Mistral Than Cohere?

| Metric | Cohere | Mistral |
|--------|--------|---------|
| L1+TALE φ (correctness) | +0.4657 | +0.3440 |
| L1+TALE Q-statistic | 0.8371 | 0.6577 |
| L1+TALE double-fault rate | 0.1133 | 0.1767 |
| L1+TALE expected double-fault (indep.) | 0.0393 | 0.1024 |
| L1+TALE excess double-fault | 0.0740 | 0.0743 |
| L1+TALE answer agreement rate | 79.3% | 61.3% |
| L1+TALE agree correct rate | 90.3% | 86.4% |
| L1+TALE agree wrong rate | 9.7% | 13.6% |
| Bad majority (L1+TALE wrong, S1 correct) | 9 | 13 |
| Behavior | strongly_correlated_family | strongly_correlated_family |

**Finding:** Surprisingly, Cohere L1+TALE φ=0.466 ≥ Mistral L1+TALE φ=0.344. 
Excess double-fault: Mistral +0.0743 vs Cohere +0.0740.
Bad majority cases: Mistral 13 vs Cohere 9.

---

## 3. Does Double-Fault/Excess Double-Fault Explain Pooled-4 on Cohere?

- Cohere avg pairwise disagreement: 0.237
- Cohere pooled-4 captures 46.5% of oracle gain over frontier
  (agreement-only captures 23.3%)
- Cohere pooled-4: 22 recoveries, 2 regressions vs frontier
- Cohere majority patterns: all-4-agree 64.0%, 3-1 18.7%, 2-split 13.0%

**Yes.** Lower excess double-fault on Cohere means errors are more spread across sources,
allowing pooled majority to correct more errors. Sources behave like approximately independent voters.

---

## 4. Does Underweighting S1 Explain Pooled-4 Failing on Mistral?

- Mistral S1 accuracy: 80.0% (Cohere) vs 89.7% (Mistral)
- Mistral pooled-4 losses to S1: 19
- Of those losses, 3 driven by L1+TALE wrong majority
- Mistral pooled-4 captures only 46.7% of oracle gain
- Mistral always-S1 captures 75.6% of oracle gain

**Yes.** On Mistral, S1's log-odds weight should be ~2.1× larger than L1's and ~4× TALE's.
Uniform weighting loses 3 cases where L1+TALE outvote S1.

---

## 5. Does Source-Family Voting Improve the Situation?

- Cohere source-family vote: 85.0%
  vs pooled-4: 85.7%
- Mistral source-family vote: 85.3%
  vs pooled-4: 85.3%
  vs always-S1: 89.7%

---

## 6. Does Weighted Voting Beat Pooled-4 or Always-S1 Out of Sample?

- Best held-out variant on Cohere: **provider_prior_selector_cv5fold** = 0.8567
  vs pooled-4 = 0.8567
- Best held-out variant on Mistral: **provider_prior_selector_cv5fold** = 0.8967
  vs always-S1 = 0.8967

---

## 7. Recommended Next Promoted Algorithm

| Algorithm | Cohere | Mistral | Avg rank | Agnostic? | Recommendation |
|-----------|--------|---------|----------|-----------|----------------|
| pooled_4 | 0.8567 | 0.8533 | 5.5 | yes | promote_if_cerebras_confirms |
| agreement_only | 0.8233 | 0.8533 | 10.0 | yes | current_baseline_safe |
| source_family_vote | 0.8500 | 0.8533 | 6.0 | yes | validate_on_cerebras |
| pooled4_with_lt_discount | 0.8500 | 0.8533 | 7.5 | yes | diagnostic_only |
| log_odds_weighted_cv5fold | 0.8267 | 0.8933 | 7.5 | no | diagnostic_only_needs_dev_set |
| provider_prior_selector_cv5fold | 0.8567 | 0.8967 | 1.5 | no | diagnostic_only_provider_specific |
| always_S1 | 0.8000 | 0.8967 | 8.0 | no | reject_for_cohere_harms_cohere |

**Primary recommendation:** Promote **pooled-4** as the default provider-agnostic algorithm
if Cerebras validation confirms it beats agreement-only on a 3rd provider.

**Secondary recommendation:** **Source-family vote** (treating L1+TALE as one family) is the
safest provider-agnostic algorithm if Mistral results matter equally — it avoids the
L1+TALE double-counting problem without requiring per-provider calibration.

**Do not promote always-S1** as the main algorithm — it harms Cohere (−2.33 pp vs agreement-only).

---

## 8. What Evidence Is Still Needed from Cerebras?

1. **Primary:** Does pooled-4 beat agreement-only on Cerebras llama3.1-8b?
   If yes: pooled-4 wins on 2/3 providers → promote.
   If no: investigate whether Cerebras resembles Mistral (one dominant source) or Cohere (balanced).

2. **Secondary:** Check pairwise φ matrix on Cerebras. If φ(L1,TALE) is high (>0.2),
   source-family vote should be preferred over pooled-4.

3. **Accuracy check:** Compute Cerebras per-method accuracies. If S1 dominates (>85%)
   while others are <80%, apply provider-prior selector (not pooled-4) for Cerebras.

---

## Constraints Confirmed
- No API calls were made.
- Cerebras job (PID 2195513) was not touched, killed, or modified.
- No frozen policy was changed.
- All diagnostic variants are offline/diagnostic only. No policy was promoted.
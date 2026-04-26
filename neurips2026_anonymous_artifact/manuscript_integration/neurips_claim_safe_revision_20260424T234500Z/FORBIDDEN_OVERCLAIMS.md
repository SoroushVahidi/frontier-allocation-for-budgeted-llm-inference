# Forbidden overclaim checklist

Use this checklist during abstract/introduction/results edits.

## Forbidden phrase -> Safe replacement

1. **Forbidden:** “our method is much better than external baselines”  
   **Safe:** “our frontier-style methods are competitive under action-budget-matched comparisons, with mixed non-dominant outcomes against external baselines.”

2. **Forbidden:** “Strict-F3 is universally best”  
   **Safe:** “Strict-F3 is a matched-surface representative with competitive but surface-sensitive performance.”

3. **Forbidden:** “frontier allocation dominates external_l1_max”  
   **Safe:** “frontier allocation shows bounded competitiveness relative to external_l1_max, without universal dominance evidence.”

4. **Forbidden:** “real-model evidence confirms headline dominance”  
   **Safe:** “real-model audits provide bounded appendix-level robustness signals and constrain overclaiming.”

5. **Forbidden:** “fixed-budget means equal token/latency/dollar cost”  
   **Safe:** “fixed action budget is the primary comparison contract; token/latency/cost are supplementary diagnostics, not full systems-cost equivalence.”

6. **Forbidden:** “anti-collapse is independently validated as accuracy-improving”  
   **Safe:** “anti-collapse is a calibration-sensitive design axis; weak anti-collapse is best on the matched sweep while conditional underperforms.”

7. **Forbidden:** “Figure 7 proves anti-collapse benefit component-wise”  
   **Safe:** “Figure 7 is non-monotonic; calibration clarifies tradeoffs rather than universally validating each component.”

## Quick pre-submission checks
- [ ] No ``universally best'' / ``SOTA across providers'' phrasing.
- [ ] Real-model references are explicitly appendix-bounded.
- [ ] Strict-F3 vs Strict-Gate1-Cap-K6 language includes fragility caveat.
- [ ] External baseline comparisons are described as competitive/non-dominant unless slice-specific and qualified.
- [ ] Budget fairness sentence says ``action-budget matched'' and adds token/latency caveat.
- [ ] Anti-collapse text states calibration sensitivity (weak best, conditional worse than default).
- [ ] No component-by-component validation wording for the full controller.

# Frontier Allocation + Verifier Integration Status (2026-05-17)

## Scope

Compact handoff for the transition from verifier training to frontier-allocation validation.
This page is summary-only; detailed metrics remain in the original output reports.

## Completed State

- Verifier training: mostly complete and accepted for downstream testing.
- Selected verifier: SetFit `all-mpnet-base-v2` cfg1
  (verified OOF ready F1=0.8646, PR-AUC=0.883).
- Safety baseline: verifier scoring is offline-capable with no provider calls and no gold leakage.
- Independent/disjoint within-method validation is now complete on a Cohere 720-row artifact.

## Task G/H/I/J/K/M Summary

- **Task G (cross-method comparison):** verifier-guided selection was method-entangled and
  mostly reproduced `external_l1_max` (72.1% vs 72.2%; `external_l1_max` chosen in 705/720 groups).
- **Task H (within-method reranking, 1440-row artifact):**
  verifier-max 75.8% vs random 66.0% (+9.8pp), anti-verifier 53.8%.
- **Task I (missed-oracle audit):** misses were mostly low-margin/tiny-gap under configured thresholds;
  no large-gap confident failures were flagged.
- **Task J (tie-aware sweep):** no global gain over baseline verifier top-1; local slice gains appeared.
- **Task K (slice-aware policies):** exploratory gains on same artifact (up to +4.17pp), not independent validation.
- **Task M (15-case disjoint sanity check):** same-sign lift (+3.3pp) but underpowered (30 groups).
- **Independent 720-row disjoint validation (new):**
  verifier-max 86.67% vs random 82.08% (+4.58pp), anti-verifier 72.50%, oracle 95.83%
  over 120 `(example_id,budget,method)` groups.

## Evidence Ladder (Within-Method Reranking)

| Artifact | Groups | verifier-max | random | anti-verifier | Lift vs random | Role |
|---|---:|---:|---:|---:|---:|---|
| Exploratory cached artifact (1440 rows) | 240 | 75.8% | 66.0% | 53.8% | +9.8pp | Exploratory, same-artifact selection/eval context |
| Small disjoint sanity artifact (15-case) | 30 | same-sign | same-sign | same-sign | +3.3pp | Underpowered diagnostic |
| **Independent/disjoint Cohere artifact (dedup 720 rows)** | **120** | **86.67%** | **82.08%** | **72.50%** | **+4.58pp** | **Strongest current independent validation** |

Independent artifact references:
- Generation root: `outputs/within_method_validation_generation_cohere_20260517T100852Z/`
- Dedup file: `.../per_example_records_dedup.jsonl` (raw 738 -> dedup 720; 18 duplicates removed across 5 duplicate keys; duplicates divergent)
- Validation report: `.../generation_validation_report.md`
- Scoring output: `outputs/verifier_scoring_new_multiseed_validation_full_20260517T144315Z/`
- Reranking output: `outputs/within_method_reranking_new_multiseed_validation_20260517T144336Z/`

## Current Bottlenecks / Next Work

1. Add uncertainty quantification for within-method lift on the new disjoint artifact
   (paired/bootstrap confidence intervals over groups).
2. Build or adopt a reusable audited frozen-policy transfer script for Task K rule application.
3. Run frozen-rule transfer only with fixed rules and no retuning on the new artifact.
4. Keep cross-method entanglement caveat explicit in all summaries.

## Claim Discipline

- Do not claim cross-method verifier superiority from current evidence.
- Within-method seed reranking now has independent positive validation on a disjoint artifact.
- Keep claims conservative: effect size on the disjoint artifact is smaller than the original exploratory 1440-row run.
- Keep provider prompts gold-free; use `gold`/`exact_match` only for offline evaluation/reporting.

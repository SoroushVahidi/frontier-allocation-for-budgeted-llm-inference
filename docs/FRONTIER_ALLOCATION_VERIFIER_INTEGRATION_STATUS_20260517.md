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

## Confirmatory Uncertainty Readout (Complete, 2026-05-17)

Uncertainty analysis is complete using paired cluster bootstrap over `example_id`
(primary CI), with paired row bootstrap reported as secondary:

- Script: `scripts/analyze_within_method_reranking_uncertainty.py`
- Test: `tests/test_analyze_within_method_reranking_uncertainty.py`
- Commit: `d1b035f9`
- Output: `outputs/within_method_reranking_uncertainty_new_validation_20260517T150458Z/`

Overall independent/disjoint result (`n_groups=120`, `n_clusters=60`), 95% cluster-bootstrap CIs:

| Metric | Point | 95% cluster CI |
|---|---:|---:|
| verifier-max | 86.67% | [79.17%, 93.33%] |
| random-expected | 82.08% | [75.56%, 87.78%] |
| anti-verifier | 72.50% | [64.17%, 80.83%] |
| oracle | 95.83% | [90.83%, 100.00%] |
| verifier minus random | +4.58pp | [+0.28pp, +9.03pp] |
| verifier minus anti | +14.17pp | [+6.67pp, +21.67pp] |
| oracle minus verifier | +9.17pp | [+4.17pp, +15.00pp] |

By-method `verifier_minus_random`:
- `direct_reserve_semantic_frontier_v2`: +4.44pp, CI [-2.22pp, +11.11pp]
- `external_l1_max`: +4.72pp, CI [-1.67pp, +10.83pp]

Interpretation:
- Aggregate verifier-vs-random gain is statistically stable (cluster CI lower bound > 0).
- Per-method verifier-vs-random gains are positive but individually uncertain (CIs cross 0).
- Verifier-vs-anti is strongly positive overall and by method.
- Oracle remains a diagnostic fixed-pool upper bound, not a deployable policy.

## Current Bottlenecks / Next Work

1. Build or adopt a reusable audited frozen-policy transfer script for Task K rule application.
2. Run frozen-rule transfer only with fixed rules and no retuning on the independent artifact.
3. Prepare a paper-ready results table separating aggregate-confirmed effects from method-level uncertainty.
4. Keep cross-method entanglement caveat explicit in all summaries.

## Claim Discipline

- Do not claim cross-method verifier superiority from current evidence.
- Within-method seed reranking now has independent positive validation on a disjoint artifact.
- Keep claims conservative: effect size on the disjoint artifact is smaller than the original exploratory 1440-row run.
- Keep provider prompts gold-free; use `gold`/`exact_match` only for offline evaluation/reporting.

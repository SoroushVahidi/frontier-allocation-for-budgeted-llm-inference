# Verifier-Guided Reranking Reproducibility Appendix (2026-05-17)

## Purpose
This appendix is a reproducibility and handoff map for the RelationReady verifier integration into frontier-allocation selection/reranking.
It links claims to concrete scripts, commits, inputs, and output artifacts, and separates exploratory findings from independent/uncertainty-backed validation.

## Evidence Hierarchy

| Evidence tier | Artifact/output path | Script(s) | Commit(s) if known | n/examples/groups | Claim status | Main result | Caveats |
|---|---|---|---|---|---|---|---|
| Cross-method allocation comparison | `outputs/allocation_policy_comparison_verifier_scored_20260517T033833Z/` | `scripts/compare_allocation_policies.py` | `53f6e607` | 1440 rows, 40 examples, 720 groups (`example_id,budget,seed`) | Exploratory cross-method diagnostic | Verifier-guided cross-method pick: 72.1%, essentially tied to `external_l1_max` (72.2%) | Method entanglement: verifier chose `external_l1_max` in 97.9% of groups |
| Within-method reranking (exploratory 1440-row artifact) | `outputs/within_method_reranking_verifier_scored_20260517T040436Z/` | `scripts/compare_within_method_reranking.py` | `8bd928c6` | 1440 rows, 40 examples, 240 groups (`example_id,budget,method`) | Exploratory | `verifier_max` 75.83% vs random 66.04% (`+9.79pp`) | Same artifact used for subsequent exploratory policy mining; not independent |
| Missed-oracle audit | `outputs/within_method_reranking_missed_oracle_audit_20260517T040802Z/` | output-only audit/report from reranking artifacts | N/A (output-only) | 57 missed-oracle groups audited | Exploratory diagnostic | Characterized missed-oracle failure modes and tie/margin patterns | Diagnostic only; no independent validation claim |
| Tie-aware sweep | `outputs/within_method_tie_aware_sweep_20260517T041409Z/` | `scripts/sweep_within_method_tie_aware_reranking.py` | `dc94f4a0` | 1440 rows, 40 examples, 240 groups | Exploratory | Best overall non-oracle setting did not improve baseline globally (`+0.00pp`) | Parameter/policy selection on same exploratory artifact |
| Slice-aware policy analysis | `outputs/slice_aware_reranking_policy_analysis_20260517T041740Z/` | (analysis/report artifact; uses tie/reranking outputs) | N/A (output-only policy selection artifact) | 240 groups | Exploratory | Best constrained policy on same artifact: 80.00% vs 75.83% (`+4.17pp`) | Same-artifact policy selection; requires frozen transfer on disjoint artifact |
| Small disjoint sanity validation (15-case) | `outputs/within_method_reranking_direct_l1_15case_validation_20260517T100048Z/` | `scripts/compare_within_method_reranking.py` | `8bd928c6` | 60 rows, 15 examples, 30 groups | Sanity validation (disjoint, underpowered) | `verifier_max` 40.00% vs random 36.67% (`+3.33pp`) | Small sample; wide uncertainty expected |
| Independent Cohere validation (budget 6) | `outputs/within_method_reranking_new_multiseed_validation_20260517T144336Z/` and scoring input `outputs/verifier_scoring_new_multiseed_validation_full_20260517T144315Z/` | `scripts/score_verifier_on_frontier_candidates.py`, `scripts/compare_within_method_reranking.py` | `2e443e99`, `8bd928c6` | 720 rows, 60 examples, 120 groups | Independent validation | `verifier_max` 86.67% vs random 82.08% (`+4.58pp`) | Single provider/dataset family for this independent run |
| Uncertainty analysis on independent validation | `outputs/within_method_reranking_uncertainty_new_validation_20260517T150458Z/` | `scripts/analyze_within_method_reranking_uncertainty.py` | `d1b035f9` | 120 groups, 60 clusters, 10,000 bootstrap draws | Uncertainty-backed validation (strongest current evidence) | `verifier_minus_random = +4.58pp`, 95% cluster-bootstrap CI `[+0.28pp, +9.03pp]` | Method-level CIs for verifier-vs-random cross zero |
| Frozen slice-aware transfer (disjoint target) | `outputs/frozen_slice_aware_transfer_new_validation_20260517T152312Z/` | `scripts/apply_frozen_slice_aware_reranking.py` | `c30f1575` | 720 rows, 60 examples, 120 groups | Independent frozen-transfer check | Frozen policy equals baseline (`frozen_minus_verifier = +0.00pp`, recoveries/regressions/net = `3/3/0`) | Most learned slice rules did not overlap target slices; improvement not validated |
| Paper-ready local bundle | `outputs/paper_ready_reranking_results_20260517T151303Z/` | output packaging from existing artifacts | N/A (local output bundle) | Summary bundle | Reporting artifact (local) | Consolidated markdown/CSV/LaTeX result tables | Output directory is intentionally uncommitted |

## Script Index

- `scripts/score_verifier_on_frontier_candidates.py` (`2e443e99`): Offline verifier scoring on frontier candidates; preserves gold/exact fields only for offline evaluation metadata.
- `scripts/compare_allocation_policies.py` (`53f6e607`): Cross-method policy comparison (`direct_reserve`, `external_l1_max`, verifier-guided) and entanglement diagnostics.
- `scripts/compare_within_method_reranking.py` (`8bd928c6`): Within-method seed reranking evaluation grouped by `(example_id,budget,method)`; reports verifier/random/anti/oracle.
- `scripts/sweep_within_method_tie_aware_reranking.py` (`dc94f4a0`): Tie-aware rule sweep over within-method groups to test deterministic tie-break alternatives.
- `scripts/analyze_within_method_reranking_uncertainty.py` (`d1b035f9`): Paired and cluster bootstrap uncertainty analysis for reranking metrics.
- `scripts/apply_frozen_slice_aware_reranking.py` (`c30f1575`): Applies preselected slice rules to a disjoint scored artifact without retuning; falls back to verifier top-1 for unmatched slices.

## Conservative Claim Language

- Validated within-method claim:
  - On the independent 720-row Cohere validation artifact, verifier-guided within-method top-1 seed selection improved over random seed expectation by `+4.58pp`, with 95% cluster-bootstrap CI `[+0.28pp, +9.03pp]`.
- Cross-method caveat:
  - Raw cross-method verifier-guided selection is method-entangled and mostly reproduces `external_l1_max`; this is not evidence of general cross-method allocation superiority.
- Slice-aware caveat:
  - Slice-aware/tie-aware policies are exploratory on the development artifact, and frozen transfer to the independent budget-6 artifact was neutral (`0.00pp` vs verifier top-1).
- Oracle caveat:
  - Oracle metrics are fixed-pool diagnostic ceilings and not deployable policies.

## Running Job Note (Future Artifact)
A budget-4/8 Cohere validation generation job is currently running and should be treated as in-progress future evidence until completion and validation:

- `outputs/within_method_validation_generation_cohere_budget4_8_20260517T154236Z/`

This appendix does not treat that artifact as complete or claim-bearing yet.

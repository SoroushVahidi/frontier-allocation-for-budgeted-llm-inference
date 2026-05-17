# Frontier Allocation + Verifier Integration Status (2026-05-17)

## Scope

Compact handoff for the transition from verifier training to frontier-allocation validation.
This page is summary-only; detailed metrics remain in the original output reports.

## Completed State

- Verifier training: accepted and phase-closed for the current stage
  (see `docs/RELATION_VERIFIER_PHASE_CLOSURE_20260517.md`).
- Selected verifier: SetFit `all-mpnet-base-v2` cfg1
  (verified OOF ready F1=0.8646, PR-AUC=0.883).
- Safety baseline: verifier scoring is offline-capable with no provider calls and no gold leakage.
- Independent/disjoint within-method validation is now complete on a Cohere 720-row artifact.
- Primary remaining work is allocation-policy validation and paper/report packaging.

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

## Frozen Slice-Aware Transfer (Complete, 2026-05-17)

Frozen transfer has now been implemented and evaluated on the independent validation
artifact with no retuning:

- Script: `scripts/apply_frozen_slice_aware_reranking.py`
- Test: `tests/test_apply_frozen_slice_aware_reranking.py`
- Commit: `c30f1575`
- Output: `outputs/frozen_slice_aware_transfer_new_validation_20260517T152312Z/`
- Policy applied: `all_positive_net_slices` from
  `outputs/slice_aware_reranking_policy_analysis_20260517T041740Z/selected_slice_rules.csv`

Result on independent artifact (`n_groups=120`):

- Baseline verifier_top1 accuracy: `0.866667`
- Frozen policy accuracy: `0.866667`
- `frozen_minus_verifier`: `+0.000000`
- recoveries / regressions / net: `3 / 3 / 0`
- affected groups: `45/120` (`37.5%`)
- matched rule slice on target: `external_l1_max@6` only
- unmatched rule slices: `direct_reserve@4`, `direct_reserve@8`, `external_l1_max@4`, `external_l1_max@8`
- unmatched target slice: `direct_reserve_semantic_frontier_v2@6`

Interpretation:

- Frozen slice-aware transfer is **neutral/inconclusive** on this independent artifact.
- No improvement beyond verifier_top1 was observed under frozen-rule transfer.
- Limited rule/target slice overlap is a major reason; most learned Task K slices were
  on budgets absent from this target artifact.
- The validated claim remains verifier_top1 vs random on the independent artifact
  (`+4.58pp`, cluster-bootstrap CI `[+0.28pp, +9.03pp]`).

## Current Bottlenecks / Next Work

1. Prepare paper-ready writeup/tables that explicitly separate:
   aggregate-confirmed verifier_top1 effects vs neutral slice-aware transfer.
2. Optionally run an additional independent validation containing budget-4/8 slices
   before revisiting Task K frozen rules.
3. Keep cross-method entanglement caveat explicit in all summaries.
4. Keep provider prompts gold-free; use `gold` / `exact_match` only for offline reporting.

## Correction Addendum (2026-05-17, Budget-4/8 Cohere)

- The full budget-4/8 artifact (`outputs/within_method_validation_generation_cohere_budget4_8_20260517T154236Z/`)
  is **overlap-contaminated** and must not be treated as independent validation.
- Corrected overlap audit found `40` overlapping `example_id`s (`openai_gsm8k_0..39`) against
  `outputs/verifier_frontier_scoring_full_20260517T032713Z/scored_candidates.jsonl`.
- Root cause: preflight disjointness parsing for prior scored artifacts missed
  `metadata.example_id` (and question in `feature_text`/metadata), yielding a false-zero overlap.
- Runner/preflight hardening is now wired in (commit `c13c0256`): Cohere validation
  runner accepts repeatable `--disjointness-prior-jsonl` inputs and fails by default
  on overlap unless explicitly bypassed with `--allow-disjointness-overlap`.
- A clean derived subset
  (`.../per_example_records_nonoverlap_valid.jsonl`, 20 examples / 480 rows, balanced)
  produced weaker evidence: verifier-minus-random `+3.75pp` with 95% cluster CI crossing 0,
  and `direct_reserve_semantic_frontier_v2@8` negative vs random.
- Frozen slice-aware transfer on this filtered subset remained net negative overall
  (`frozen_minus_verifier = -2.50pp`).
- Headline independent evidence remains the budget-6 Cohere artifact:
  verifier-minus-random `+4.58pp`, 95% cluster CI `[+0.28pp, +9.03pp]`.

## Claim Discipline

- Do not claim cross-method verifier superiority from current evidence.
- Within-method seed reranking now has independent positive validation on a disjoint artifact.
- Keep claims conservative: effect size on the disjoint artifact is smaller than the original exploratory 1440-row run.
- Keep provider prompts gold-free; use `gold`/`exact_match` only for offline evaluation/reporting.

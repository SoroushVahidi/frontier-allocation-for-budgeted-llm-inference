# Frontier Allocation + Verifier Integration Status (2026-05-17)

## Scope

Compact handoff for the transition from verifier training to frontier-allocation validation.
This page is summary-only; detailed metrics remain in the original output reports.

## Completed State

- Verifier training: mostly complete and accepted for downstream testing.
- Selected verifier: SetFit `all-mpnet-base-v2` cfg1
  (verified OOF ready F1=0.8646, PR-AUC=0.883).
- Safety baseline: verifier scoring is offline-capable with no provider calls and no gold leakage.

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

## Current Bottleneck

Independent multi-seed validation data is the gating item for promotion decisions.
A new Cohere generation run is active in tmux:

- Session: `frontier_multiseed_validation_20260517_061447`
- Output root: `outputs/within_method_validation_generation_cohere_20260517T100852Z`
- Target: 60 examples × 1 budget × 6 seeds × 2 methods = 720 rows

## Safe Next Steps (post-generation)

1. Validate artifact integrity (row count, coverage, traces/answers, disjointness evidence).
2. Run offline verifier scoring (dry-run then full score).
3. Run within-method reranking on scored output.
4. Evaluate frozen Task K rules only if slices overlap; do not retune on new artifact.
5. Update status docs with validated vs exploratory labels.

## Claim Discipline

- Do not claim cross-method verifier superiority from current evidence.
- Treat within-method reranking as promising until independent validation confirms it.
- Keep provider prompts gold-free; use `gold`/`exact_match` only for offline evaluation/reporting.

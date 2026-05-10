# Artifact index update

Newest high-signal outputs for navigation and paper drafting.

## `outputs/production_equiv_v1_stage3_50_live_checkpoint_rerun_20260508T203036Z`

- **Purpose:** Stage-3 production-equivalence v1 live checkpoint rerun on fixed 50-case selection.
- **Key result:** 36/50 correct for production_equiv_v1 (feeds suite aggregator).
- **Use in paper:** yes
- **Caveat:** Live Cohere-backed artifact; cite manifest + case list; not a universal GSM8K claim.

## `outputs/external_sc6_fair_50case_live_20260508T221625Z`

- **Purpose:** Fair SC6 external baseline on matched 50 cases.
- **Key result:** 36/50 — ties production_equiv on same IDs in suite summary.
- **Use in paper:** yes
- **Caveat:** Adapted fair harness; wording should say behavior-level / fairness-contract.

## `outputs/external_pal_pot_fair_50case_live_20260508T222348Z`

- **Purpose:** PAL/PoT-style fair baseline on matched 50.
- **Key result:** 40/50 — strongest individual external on this slice.
- **Use in paper:** yes
- **Caveat:** PAL/PoT-style unless full official parity audit is completed.

## `outputs/external_full_suite_matched50_comparison_20260508T222631Z`

- **Purpose:** Aggregated matched-50 comparison across methods + oracle deltas.
- **Key result:** Main claim revision flags; PEQ −4 vs best individual external (PAL).
- **Use in paper:** yes
- **Caveat:** `no_api_calls` in JSON refers to builder metadata, not prohibition for future runs.

## `outputs/pal_pot_advantage_loss_pattern_audit_20260508T223121Z`

- **Purpose:** Pattern audit where PAL wins vs production_equiv on matched slice.
- **Key result:** Supports hybrid-selector motivation (qualitative / structural loss families).
- **Use in paper:** maybe
- **Caveat:** Interpret as hypothesis generation, not independent holdout validation.

## `outputs/pal_vs_production_equiv_casebook_live_20260508T223635Z`

- **Purpose:** Casebook run contrasting PAL vs production_equiv outcomes.
- **Key result:** Disagreement / inspection set for next PAL-aware work.
- **Use in paper:** maybe
- **Caveat:** Small n relative to full dataset; use for error analysis appendix.

## `outputs/method_maturity_stop_improvement_audit_20260508T212754Z`

- **Purpose:** Stop / maturity audit summarizing improvement attempts and plateau signals.
- **Key result:** Documents retry / patch fatigue and prioritization toward external suite honesty.
- **Use in paper:** maybe
- **Caveat:** Internal audit narrative — align claims with CLAIMS.md before citing.

## `outputs/schema_grounded_retry_v1_parsefix_5case_live_20260508T210832Z`

- **Purpose:** 5-case live probe after parse fix for schema-grounded retry.
- **Key result:** Negative viability signal for schema-grounded retry v1 as integrated path.
- **Use in paper:** no
- **Caveat:** Preserve as negative diagnostic; do not oversell n=5 scope.

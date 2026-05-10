# Stage-3 TALE/S1 50-case Pilot Readiness

## Why 50 before 245
- Provides a bounded out-of-sample checkpoint before committing 245 integrated calls.
- Keeps baseline reuse fixed and isolates integrated-method generalization signal.

## Sampling buckets
- {'pal_wrong_external_correct': 20, 'all_correct': 15, 'pal_wrong_all_external_wrong': 10, 'mixed_other': 5}
- Best-external winner mix: {'external_l1_max': 32, 'external_tale': 6, 'external_s1': 2, 'none': 10}

## Reuse and calls
- External outputs reused from all_casebook: yes.
- Estimated integrated calls: 50.
- Estimated external baseline calls: 0.

## Runner support status
- New stage3 replay runner supports dry-run replay/provenance.
- Live execution path is not implemented yet.

## Commands
- Dry-run command:
  `python scripts/run_stage3_integrated_vs_external_replay_checkpoint.py --readiness-dir outputs/stage3_tale_s1_pilot_readiness_20260508T032919Z --case-file outputs/stage3_tale_s1_pilot_readiness_20260508T032919Z/stage3_pilot_cases.csv --stage-name stage3_pilot --max-new-cohere-calls 50 --reuse-external-outputs --dry-run-only`
- Live command: not yet supported (see missing_live_components).

## Claim boundaries
- This package is no-API readiness only.
- No new model inference was executed.

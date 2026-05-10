# Stage-3 Pilot Gap Analysis

## Main recap
- Integrated: 38/50 vs best_external: 40/50 (delta -2).
- Integrated wrong count: 12; best_external-only count: 3; all-wrong count: 9.

## Best-external-only signal
- external_tale: 2 cases
- external_l1_max: 1 cases

## Integrated-wrong failure patterns
- final_target_or_extraction_mismatch: 8
- late_stage_arithmetic_or_magnitude_error: 2
- non_numeric_final_answer_format: 1
- ratio_or_fraction_setup_error: 1

## Decision guidance
- Recommended next step: `micro_pilot_best_external_only`.
- Run a focused best_external-only micro-pilot before any 245-case expansion.
- Prioritize scaffold/verifier parity work; treat full production frontier-runtime equivalence as a near-term priority.

## Caveats
- Offline label-based categorization uses heuristic pattern inference from outputs and tags.
- This pilot uses scaffolded Stage-3 runtime and should not be treated as final production-equivalent behavior.
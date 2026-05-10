# Stage-2 Validated Fixes Checkpoint Report

## What changed vs previous Stage-2
- Applied validated targeted fixes on 7 external_l1-only IDs; all other 93 cases carried previous integrated predictions.

## Calls used
- New Cohere calls: 7/10

## Results vs external_l1_max
- external_l1_correct: 85/100
- previous_integrated_correct: 86/100
- validated_fixes_correct: 92/100
- validated_fixes_minus_external_l1: 7
- validated_fixes_minus_previous_integrated: 6

## Paired breakdown
- validated_fixes_only: 8
- external_l1_only: 1
- both_correct: 84
- both_wrong: 7

## Decision framing
- If net gain over external_l1 is >0 with clean errors, evidence is stronger than directional-only and supports broader comparative checkpoints.
- Stage 3 TALE/S1 is justified once this controlled rerun remains stable under paired comparison.

## Caveats
- Still constrained to validated external_l1-only overrides, not a full router expansion.
- McNemar inputs are small-event counts; treat significance cautiously.

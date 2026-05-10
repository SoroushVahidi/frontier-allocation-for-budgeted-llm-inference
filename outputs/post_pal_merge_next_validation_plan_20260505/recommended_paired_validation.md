# Recommended next paired validation (no-API plan)

## Current best method

- `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`

## Evidence so far

- Targeted PAL corrected/replayed set: **21/28** after integration fix.
- Capped paired pilot: **PAL 40/43 vs external_l1_max 36/43**.

## Claim boundary

Current results are **promising** but still from **small/capped** runs. Treat this as directional signal, not final claim-grade evidence.

## Next recommended API experiment (after explicit approval)

Run a larger paired comparison:

- Methods: `external_l1_max` vs `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`
- Dataset: fresh GSM8K IDs only (exclude prior paired IDs)
- Pairing: strict per-example paired evaluation, complete pair tracking
- Output: paired summary + casebook + cap-usage diagnostics

## Suggested cap

- Preferred initial cap: **1000** calls
- Optional higher cap: **1500** calls (only if user explicitly approves)

Rationale: prior runs show cap-related truncation/partial pairing risk; 1000 is a conservative first escalation.

## Key risks to control

1. Cap saturation before complete paired set.
2. Partial pairing across methods (missing partner rows).
3. Repeated-case contamination from previous runs.
4. Metric consistency drift between raw and corrected/replay summaries.

## Required no-API preflight before any live batch

1. Validate method registry (`--validate-methods-only`).
2. Verify fresh-ID allowlist generation and overlap checks.
3. Dry-run cap forecast from previous average call usage.
4. Confirm output schemas/casebook materializers on synthetic or existing local artifacts.

## Operational guardrail

Keep API execution **paused** until explicit user approval, then run a single capped batch and review pairing completeness before any follow-up extension.

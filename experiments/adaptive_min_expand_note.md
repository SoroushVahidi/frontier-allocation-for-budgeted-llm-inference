# Adaptive min-expand safeguard (provisional fix)

## Why this safeguard was introduced

`pilot_diagnosis_1.md` found that the adaptive controller collapsed into a deterministic `verify -> prune` loop (`expand = 0` in the latest trustworthy API-backed run), so branches were eliminated before any search actually happened.

## Exact rule added

A new adaptive safeguard parameter was introduced:

- `min_expansions_before_prune` (integer, default `0` to preserve old behavior)

Rule:

- For each branch, while `branch_expansions < min_expansions_before_prune`, force `expand`.
- Only after that floor is met, allow normal threshold policy (`expand` / `verify` / `prune`) to run.

Implementation details:

- Added to `AdaptiveController` as a constructor/config parameter.
- Per-branch expansion counts are tracked in-run.
- Added `forced_expand` field in action trace rows for transparent diagnostics.
- Added a new method variant `adaptive_min_expand` in config + runner so old adaptive remains available for direct comparison.

## Why this is only a provisional engineering fix

This change only prevents the immediate degenerate control loop. It does **not** solve deeper research questions (score calibration, threshold learning, better verifier design, branch proposal quality, and budget allocation strategy).

So this should be treated as a guardrail to restore minimal exploration behavior, not as the final adaptive method.

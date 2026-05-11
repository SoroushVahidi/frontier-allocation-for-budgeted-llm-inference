# PAL Unresolved Pattern Taxonomy

## Bottleneck Targeted

The bottleneck is still candidate generation, gold-in-pool behavior, and frontier collapse.

The 30-case exact replay left only 17 unresolved cases. That is useful for a narrow regression check, but it is too small to support broad pattern mining on its own. The broader fully tracked failure corpus gives us a much better unresolved slice to inspect.

## Why This Corpus

We use the merged recovery-coverage audit to isolate the currently unresolved, covered PAL failures:

- `full_latest_method_failures.csv`: 215 records, 174 unique FULL failure case IDs
- `gold_absent_subpattern_analysis_20260510.csv`: 172 gold-absent cases
- PAL unresolved covered cases: 157

The unresolved PAL set is the only broad covered set that is large enough for pattern mining right now. Missing `uncertainty_retry_v1` or `diverse_anchor` coverage is not failure; it only means existing artifacts do not cover those methods broadly enough yet.

## Audit Scope

- Existing artifacts only.
- No live controller.
- No runtime behavior change.
- No paid/model API calls.
- No external-baseline claim.

## What the Taxonomy Is

This taxonomy is intentionally heuristic and artifact-based.

It does not pretend to be a ground-truth causal proof. Instead it uses transparent rules over:

- the full failure corpus,
- the gold-absent subpattern CSV,
- the direct L1 anchor patch-effect CSV,
- and the recovery-coverage audit slice.

## Decision Rule

If one or two patterns dominate, design a targeted fix for the largest actionable pattern and validate it on a small exact-replay slice first.

If the remaining metadata is too sparse for a stable causal read, collect richer traces before implementing the fix.

## Current Read

The unresolved PAL slice is large enough to mine, but it is still dominated by low-diversity, gold-absent failures.

- `frontier_collapse_low_diversity`: 155 / 157
- `wrong_supported_consensus` / `both_direct_and_frontier_wrong`: 97 / 157
- `direct_l1_anchor_potential`: 43 / 157
- `strong_direct_l1_anchor_match`: 18 / 157

The largest question-type families are:

- `money/cost/revenue`: 47
- `multi-step arithmetic`: 36
- `ratio/proportion/percentage`: 36
- `temporal/calendar`: 16
- `rate/speed/work`: 10
- `unit conversion`: 8
- `inventory/remaining quantity`: 4

Only four cases have explicit subpattern tags in the gold-absent CSV:

- premature intermediate answer
- counting/grouping off-by-factor (factor)
- counting/grouping off-by-factor (multiple)
- premature intermediate answer (copied from problem)

That means the broad taxonomy is usable, but many cases still need richer trace metadata if you want a tighter causal explanation for the tail.

## Recommended Next Step

Start with a stronger direct L1 anchor / direct seed pilot on the 43 direct-L1-anchor-potential cases, using the 18 strong patch-effect matches as the clearest exact-replay diagnostic slice.

Why this first:

- It is the cleanest high-signal subset with explicit external L1 evidence.
- It directly targets the gold-absent discovery gap.
- It is lower risk than a larger structural change.

If that pilot does not move the needle enough, the next follow-up should be a duplicate wrong-consensus penalty / branch-progress scoring pass on the broader low-diversity set.

## Suggested Exact-Replay Slice

Use the top scored cases from the taxonomy output for the next diagnostic. The current audit highlights cases such as:

- `openai_gsm8k_168`
- `openai_gsm8k_180`
- `openai_gsm8k_190`
- `openai_gsm8k_197`
- `openai_gsm8k_204`
- `openai_gsm8k_213`
- `openai_gsm8k_228`
- `openai_gsm8k_233`
- `openai_gsm8k_264`
- `openai_gsm8k_297`
- `openai_gsm8k_30`
- `openai_gsm8k_347`
- `openai_gsm8k_354`
- `openai_gsm8k_367`
- `openai_gsm8k_374`

## Limits

- Missing coverage is not failure.
- This is an existing-artifact audit only.
- No runtime behavior change was made.
- No paid/model API calls were made.
- No external-baseline claim is made.

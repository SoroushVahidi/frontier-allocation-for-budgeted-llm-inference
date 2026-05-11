# PAL 157 Deep Pattern Mining

## Bottleneck Targeted

The current bottleneck is candidate generation, gold-in-pool behavior, and frontier collapse.

If the correct answer never enters the candidate pool, selector changes cannot recover it. This pass therefore mines the 157 PAL still-failing covered cases for more concrete failure mechanisms before changing runtime behavior.

## Why the 157 PAL Cases

The 30-case exact replay left only 17 unresolved cases. That is useful for regression checks, but too small for broad pattern mining.

The merged recovery coverage audit found a larger covered unresolved set:

- 215 fully tracked failure records
- 174 unique fully tracked failure IDs
- 172 gold-absent cases
- 157 PAL still-failing covered cases

The merged PAL unresolved taxonomy showed those 157 cases are dominated by low-diversity, gold-absent failures, with 43 direct-L1-anchor-potential cases and 97 wrong-supported-consensus cases.

## Scope

This is no-API artifact analysis.

It reads existing CSV/JSONL artifacts, joins the full failure corpus, the gold-absent subpattern CSV, the direct-L1 anchor patch-effect CSV, and recovery coverage details. It does not run a live controller and does not call any model API.

## Heuristic Labels

The deeper pattern labels are transparent heuristics, not causal truth.

The miner uses:

- explicit columns such as `question_type`, `error_type`, `num_candidate_groups`, `diversity_bucket`, and `external_contrast`
- direct-L1 patch-effect columns such as `anchor_matches_l1_max` and `external_l1_exact`
- simple keyword rules over the problem text for ratio, percentage, temporal, money, unit/rate, remaining/subtraction, and multi-step mechanisms

The report explicitly separates observed facts, heuristic pattern labels, inferred likely mechanisms, and proposed targeted fixes.

## Actionability Rule

A pattern is actionable when it has:

- enough coverage count to justify a targeted diagnostic
- a plausible opt-in intervention
- manageable regression risk
- some overlap with exact replay slices
- enough metadata confidence to avoid guessing from missing data

## Decision Rule

If direct-L1-potential remains the best scored actionable slice, the next PR should implement the opt-in strong Direct L1 seed method.

If wrong-supported-consensus dominates with weak direct-L1 signal, the next PR should target duplicate consensus penalty behavior.

If metadata confidence is too low, the next PR should add richer tree logging before algorithm changes.

## Candidate Fixes Scored

The miner scores:

- stronger Direct L1 seed with independent arithmetic/unit self-check
- duplicate wrong-consensus penalty
- domain-specific money/unit ledger strengthening
- ratio/percentage base normalization anchor
- branch-progress scoring for premature intermediate answers
- richer tree logging before algorithm changes

## Diagnostic Slices

The script writes deterministic slices for the next targeted experiment:

- `direct_l1_strong_seed_15case`
- `direct_l1_strong_seed_30case`
- `wrong_supported_consensus_15case`
- `money_cost_revenue_15case`
- `ratio_percentage_15case`

These slices are diagnostic inputs, not accuracy claims.

## Claim Boundaries

- No runtime behavior change.
- No paid/model API calls.
- No live validation.
- No external-baseline claim.
- No current accuracy claim.


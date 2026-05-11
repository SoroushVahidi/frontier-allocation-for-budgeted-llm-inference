# Latest Failure Recovery Coverage Audit

## Bottleneck Targeted

Candidate generation, gold-in-pool behavior, and frontier collapse.

The point of this audit is not to rerun models. It is to measure how much of the larger fully tracked latest-method failure corpus is already covered by existing repository artifacts, so we can decide whether there is enough unresolved evidence to mine patterns from the newest method results.

## Why the 30-Case Replay Is Too Small

The 30-case exact replay left only 17 unresolved cases. That is useful for a narrow regression check, but it is too small to drive the next pattern-mining step by itself.

This audit therefore uses the broader fully tracked failure corpus:

- `docs/project_handoff_20260510/exhaustive_failure_audit/full_latest_method_failures.csv`
- `docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv`

The repository summary says the full corpus contains 215 records covering 174 unique FULL failure case IDs, and the gold-absent subset contains 172 cases.

## Audit Scope

- Existing artifacts only.
- No live controller.
- No runtime behavior change.
- No paid/model API calls.
- No external-baseline claim.

## Coverage Rule

- A case is counted as `resolved`, `still_fails`, or `unknown` only when an existing artifact row matches both the case ID and the method ID clearly.
- Missing coverage is reported as `not_covered`.
- Invalidated artifacts are excluded from coverage counts.

## Decision Rule

Proceed to pattern mining on the unresolved covered set only if that set is large enough to be meaningful.

If unresolved covered cases are sparse, use the full 174-case failure corpus with coverage labels attached, or collect a larger current-method run first.

## Notes

- This audit is a data-preparation step, not an evaluation claim.
- It should not be cited as evidence of beating an external baseline.

# Domain-Aware Regression Guard Postmortem

The regression guard was added as a conservative fallback for the domain-aware diverse-anchor method, then re-evaluated on the same exact 30-case Cohere slice.

## Result

- Baseline domain-aware diverse-anchor run: `14/30` exact, `1` regression
- Guard-enabled rerun: `10/30` exact, `2` regressions
- Guard-triggered cases: `13/30`

## Conclusion

- The guard was too aggressive in this setup.
- It harmed accuracy and introduced an extra regression.
- The current recommended default is the domain-aware diverse-anchor method **without** the regression guard.

## Recommendation

- Keep the guard implementation available behind an explicit config flag for future experiments.
- Do not enable it in the production diverse-anchor method.
- Revisit only if a more targeted guard can preserve gold-like frontier candidates without suppressing correct anchor improvements.

## Reference

- `docs/DOMAIN_AWARE_30CASE_FAILURE_TRIAGE_20260510.md`
- `docs/DOMAIN_AWARE_REGRESSION_GUARD_20260510.md`

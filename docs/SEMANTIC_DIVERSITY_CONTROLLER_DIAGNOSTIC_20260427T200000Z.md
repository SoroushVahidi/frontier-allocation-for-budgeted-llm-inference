# Semantic diversity controller diagnostic (20260427T200000Z)

## Status

Experimental / diagnostic only. A 10-case live Cohere run is **not** sufficient to support manuscript claims.

## Questions (see CSVs in output dir)

- Which variant had the best accuracy–cost tradeoff on `method_accuracy_summary.csv`?
- Do semantic maturation variants increase `semantic_family_count` vs `strict_f3` in `per_case_results.csv`?
- Do paired deltas in `paired_summary.csv` show improvement over `strict_f3` and movement toward `external_l1_max`?

## Next experiment

If a single variant is consistently better on **paired** accuracy vs `strict_f3` in two budgets, run 30 cases with `--allow-large-run` and the same case-selection policy.

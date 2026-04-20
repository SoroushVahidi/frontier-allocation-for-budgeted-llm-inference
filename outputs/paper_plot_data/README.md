# Paper plot data status note

## Status

The CSV files in this directory are **derived bounded plot inputs**, not the default current-canonical ranking surface for the repository.

They were generated for the older imported-methodology frontier evaluation path centered on:

- `outputs/imported_methodology_frontier_eval/20260417T000000Z/`

## Scope

These plot-data files reflect:
- a bounded paper-facing frontier comparison,
- single-dataset GSM8K scope,
- budgets 8 and 10,
- and the method pool used by that imported-methodology bundle.

## Safe use

These files are safe to use when you explicitly say that the figure/table is about the older bounded imported-methodology frontier surface.

They are **not** safe to use as if they were the current whole-repository ranking source.

## For current broad comparison claims use instead

- `outputs/current_full_method_comparison_bundle_20260420/`
- `docs/CURRENT_FULL_METHOD_COMPARISON_BUNDLE_STATUS_2026_04_20.md`
- `docs/CURRENT_RANKING_AND_COMPETITIVE_STATUS_2026_04_20.md`

## Important note on method values

If a method such as `program_of_thought` appears to have zero accuracy in these CSVs, that is a property of this bounded artifact surface and should not automatically be generalized to all current repository comparison surfaces.

# Commands, assumptions, and caveats

## Commands run
- `python scripts/run_current_leading_failure_case_extraction.py`

## Assumptions
- `estimated_value_if_allocate_next` is treated as the oracle/optimal one-step utility under the same artifacts.
- Leading mode is selected from `aggregate_comparison_summary.json` in the latest multistep validation directory.
- Per-seed train/test splits are reconstructed via `prepare_learning_tables` with the canonical seed and config.

## Caveats
- Support is small (21 total test states across 3 seeds), so failure rankings are diagnostic, not statistically stable.
- Full question text and branch text are not present in these artifacts; diagnosis is state/branch-ID level only.
- Method scores are linear model outputs fit in this extraction pass to mirror the multistep evaluation protocol.

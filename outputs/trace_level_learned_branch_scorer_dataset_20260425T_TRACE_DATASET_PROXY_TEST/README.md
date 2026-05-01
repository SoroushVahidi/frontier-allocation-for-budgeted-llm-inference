# Trace-level learned branch scorer dataset (20260425T_TRACE_DATASET_PROXY_TEST)

Input trace directory: `/tmp/pytest-of-sv96/pytest-26/test_trace_level_builder_proxy0/trace_pkg_proxy`

Rows are built from terminal branch/action/answer-group traces when available,
with explicit proxy fallback rows when traces are missing.

## Files
- `examples.csv`: one row per candidate branch or reconstructed answer-group candidate
- `feature_schema.json`: schema and source types
- `dataset_summary.csv`: high-level counts
- `case_coverage.csv`: per-case candidate/gold coverage diagnostics

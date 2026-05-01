# Learned branch scorer dataset (20260425T_LEARNED_SCORER_DATASET_TEST)

This package is diagnostic-only and intentionally lightweight.

## Data provenance
- Source per-example rows: `/tmp/pytest-of-sv96/pytest-26/test_dataset_builder_training_0/per_example_rows.csv`
- Candidate rows are reconstructed from method outputs.
- When answer-group candidate pools are missing, the builder falls back to method-level proxy candidates.

## Limitation
Most rows are proxy answer-group/case-level examples rather than true branch/node-level candidate traces.

## Files
- `examples.csv`: supervised rows used by training/evaluation scripts
- `feature_schema.json`: feature definitions and caveats
- `dataset_summary.csv`: aggregate counts and positive rate

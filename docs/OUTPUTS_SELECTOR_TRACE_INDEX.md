# Outputs selector trace index

This index tracks which output artifacts are usable for selector-oracle analysis. It is intentionally conservative: an artifact that contains final method rows is not necessarily usable for selector-ceiling analysis unless it also contains candidate-pool traces.

## Required selector-oracle fields

A usable artifact should provide per-example information for at least:

- example id,
- dataset,
- question if available,
- gold answer,
- method name,
- selected answer,
- normalized selected answer if available,
- exact match / correctness,
- candidate answer groups,
- normalized candidate answer per group,
- support count per group,
- candidate source such as direct reserve, frontier, or other,
- selected candidate/group id,
- actual candidate/group count,
- configured candidate/group cap,
- optional OV score,
- optional PRM score,
- optional final selector score.

## Artifact classes

| Class | Meaning | Action |
|---|---|---|
| `usable_now` | Has gold, selected answer/correctness, and candidate-pool/group information. | Run `scripts/analyze_selector_oracle_ceiling.py`. |
| `schema_adaptable` | Candidate-pool information exists but uses a different schema. | Add schema adapter/tests, then run analyzer. |
| `final_rows_only` | Has final selected answers/correctness but no candidate pool. | Not useful for selector oracle; use only for accuracy comparison. |
| `not_scored_or_empty` | No usable scored rows. | Ignore for selector ceiling. |
| `unknown_needs_manual_inspection` | Structure is unclear. | Inspect manually and classify. |

## Current known state

The repository has many datasets and result artifacts. The current blocker is not dataset absence; it is that real output artifacts have not yet been consistently confirmed to contain the candidate-pool schema required for selector-oracle analysis.

The next schema audit should produce a timestamped table like:

```text
outputs/selector_artifact_schema_audit_<timestamp>/selector_artifact_schema_audit.csv
outputs/selector_artifact_schema_audit_<timestamp>/selector_artifact_schema_audit.json
docs/SELECTOR_ARTIFACT_SCHEMA_AUDIT_<timestamp>.md
```

## Known diagnostic artifact notes

| Artifact | Current selector-oracle status | Note |
|---|---|---|
| `tests/fixtures/selector_oracle_synth/per_example_records.jsonl` | synthetic usable fixture | Exercises oracle/present-vs-absent logic; not real evidence. |
| `outputs/cohere_real_model_cost_normalized_validation_20260425T133000Z_COHERE_STAGE1_MIN/per_example_records.jsonl` | not usable from latest reported analyzer run | File existed, but the analyzer found `total_scored_examples=0`; likely not the expected paired candidate-pool schema. |

## Policy

- Do not infer that datasets are missing when a selector-oracle run returns zero scored examples.
- First check whether the artifact is a final-row artifact, a summary artifact, or a candidate-pool trace artifact.
- Prefer adapting analyzers to real schemas when candidate-pool information exists.
- If candidate-pool traces do not exist, patch metadata emission and run a tiny trace-complete smoke test before any larger experiment.
- Do not overwrite timestamped real-model folders while auditing.

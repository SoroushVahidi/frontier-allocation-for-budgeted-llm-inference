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
- support count per group or enough data to reconstruct support counts,
- candidate source such as direct reserve, frontier, or other,
- selected candidate/group id when available,
- actual candidate/group count,
- configured candidate/group cap when available,
- optional OV score,
- optional PRM score,
- optional final selector score.

## Artifact classes

| Class | Meaning | Action |
|---|---|---|
| `usable_now` | Has gold, selected answer/correctness, and candidate-pool/group information. | Run selector-oracle and offline selector analyses. |
| `schema_adaptable` | Candidate-pool information exists but uses a different schema. | Add schema adapter/tests, then run analyzer. |
| `final_rows_only` | Has final selected answers/correctness but no candidate pool. | Not useful for selector oracle; use only for accuracy comparison. |
| `not_scored_or_empty` | No usable scored rows. | Ignore for selector ceiling. |
| `unknown_needs_manual_inspection` | Structure is unclear. | Inspect manually and classify. |

## Current active selector artifact

Primary current real artifact:

```text
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/
```

Status: `usable_now` for base DR-v2 selector-oracle and offline selector analysis.

Key diagnostics:

```text
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/diagnostics/artifact_completeness_report.md
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/diagnostics/selector_oracle_ceiling_summary.json
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/diagnostics/gold_absent_coverage_summary.json
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/diagnostics/l1_loss_predictor_summary.json
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/diagnostics/offline_selector_variants/
```

Known values from the paired 30-case artifact:

| Quantity | Value |
|---|---:|
| `external_l1_max` accuracy | 0.8000 |
| current DR-v2 accuracy | 0.6333 |
| oracle selector ceiling | 0.8667 |
| corrected selector gap | 0.2333 |
| L1-correct / DR-v2-wrong cases | 7 |
| gold-present among those losses | 5 |
| gold-absent among those losses | 2 |
| candidate_count mean/median/max | 2 / 2 / 2 |
| answer_group_count mean/median/max | 1.6 / 2 / 2 |

Interpretation:

- This artifact is sufficient for selector-oracle and offline selector analysis.
- OV/PRM score selectors are skipped on this artifact because base DR-v2 rows do not include OV/PRM scores.
- Simple deployable offline selectors did not improve net accuracy.
- The next artifact-level work should focus on conservative verifier-style override patterns over the existing casebook.

## Historical / non-current artifact notes

| Artifact | Current selector-oracle status | Note |
|---|---|---|
| `tests/fixtures/selector_oracle_synth/per_example_records.jsonl` | synthetic usable fixture | Exercises oracle/present-vs-absent logic; not real evidence. |
| `outputs/cohere_real_model_cost_normalized_validation_20260425T133000Z_COHERE_STAGE1_MIN/per_example_records.jsonl` | not usable from reported analyzer run | File existed, but the analyzer found `total_scored_examples=0`; likely not the expected paired candidate-pool schema. |
| `outputs/cohere_real_model_cost_normalized_validation_20260430T_COVERAGE_REPAIR_50CASE_COHERE/per_example_records.jsonl` | partial / not paired trace-complete | Reported to contain only `external_l1_max` rows; DR-v2 absent. Preserve as provenance, not current evidence. |

## Policy

- Do not infer that datasets are missing when a selector-oracle run returns zero scored examples.
- First check whether the artifact is a final-row artifact, a summary artifact, or a candidate-pool trace artifact.
- Prefer adapting analyzers to real schemas when candidate-pool information exists.
- Use the 30-case trace-complete artifact above for immediate offline selector/verifier analysis.
- Do not overwrite timestamped real-model folders while auditing.
- Do not launch a new API run until an offline selector/verifier rule shows positive net gain on the current real artifact.

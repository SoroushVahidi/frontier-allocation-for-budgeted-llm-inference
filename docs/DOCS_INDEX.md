# Documentation index

This index separates current interpretation documents from diagnostic and historical provenance. Do not delete dated documents merely because they are old; classify them here or in a more specific index.

## Start here

| Document | Role |
|---|---|
| `README.md` | Short repository entry point. |
| `docs/CURRENT_PROJECT_STATUS.md` | Current day-to-day project status and next action. |
| `docs/CANONICAL_START_HERE.md` | Reviewer/collaborator canonical orientation. |
| `docs/REPO_MAP.md` | Directory roles and repository structure. |
| `docs/PAPER_SOURCE_OF_TRUTH.md` | Claim-eligible evidence hierarchy. |
| `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md` | Safe/supportive/unsafe claim map. |
| `docs/PAPER_OPEN_GAPS_AND_RISKS.md` | Known evidence gaps and risks. |

## Current selector / L1-defeat track

| Document | Role |
|---|---|
| `docs/SELECTOR_START_HERE.md` | Entry point for selector-first work. |
| `docs/OUTCOME_VERIFIER_SELECTOR_ROADMAP.md` | Current conservative outcome-verifier override roadmap. |
| `docs/SELECTOR_CATALOG.md` | Selector methods and diagnostic selectors. |
| `docs/OUTPUTS_SELECTOR_TRACE_INDEX.md` | Selector trace artifact usability index. |
| `docs/SELECTOR_AND_COVERAGE_CONTROLLER_ROADMAP_20260429.md` | Older ordered selector-vs-coverage roadmap; preserve as provenance. |
| `docs/FINAL_ADAPTIVE_LLM_INFERENCE_TRANSFER_AUDIT_20260430T034801Z.md` | Final audit of ideas transferred from the older binary-routing repository. |
| `docs/METHOD_REGISTRY_CANONICAL_20260429.md` | Method status and live-runnable/diagnostic distinctions. |

## Current real diagnostic artifact

Primary selector artifact:

```text
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/
```

Important diagnostic subfolder:

```text
outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE/diagnostics/offline_selector_variants/
```

Use this artifact for offline selector and conservative outcome-verifier override work before launching new API runs.

## Current runnable/reproduction docs

| Document | Role |
|---|---|
| `docs/CANONICAL_INSTALL_AND_DEV.md` | Installation and local development. |
| `docs/REVIEWER_10_MINUTE_REPRODUCTION.md` | Fast reviewer reproduction path. |
| `docs/REVIEWER_REPRO_AND_SCOPE_GUIDE.md` | Reviewer reproduction and scope boundaries. |
| `scripts/CANONICAL_START_HERE.md` | Script-level entry points. |
| `scripts/README.md` | Script inventory and usage notes. |

## Paper-facing artifact docs

| Document | Role |
|---|---|
| `docs/NEURIPS_PAPER_ARTIFACTS.md` | NeurIPS artifact orientation. |
| `docs/PAPER_ARTIFACTS_README.md` | Paper artifact usage. |
| `docs/RESULTS_GUIDE.md` | Results interpretation guide. |
| `docs/RESULTS_AND_ARTIFACTS_GUIDE.md` | Canonical/diagnostic/provenance artifact policy. |
| `docs/OUTPUTS_ARTIFACT_INDEX.md` | Output-folder provenance and timestamp notes. |

## Diagnostic evidence docs

Diagnostic docs are useful for engineering and appendices, but are not automatically headline claim evidence.

Examples include:

- real-model validation status documents,
- method-specific failure summaries,
- loss casebooks,
- selector artifact schema audits,
- Cohere/OpenAI run handoff notes,
- mock-backed verifier provenance notes,
- offline selector/risk-predictor analyses.

When using a diagnostic doc in manuscript text, first check `docs/PAPER_SOURCE_OF_TRUTH.md` and `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`.

## Historical / provenance docs

Dated documents from earlier method phases should usually be preserved. If they are superseded, mark them as superseded in a current index rather than deleting them. They may still explain why a method was abandoned or why a claim is unsafe.

The old `-adaptive-llm-inference` project has now been mined for transferable ideas. Do not keep returning to it unless a specific new loss pattern justifies doing so.

## Cleanup policy

- Prefer indexing, labeling, and cross-linking over deletion.
- Do not remove outputs or dated docs unless a current cleanup document explicitly classifies them as disposable.
- Do not rewrite historical conclusions to match current results.
- Do not promote diagnostic artifacts to paper-facing evidence without updating the source-of-truth and claim map.

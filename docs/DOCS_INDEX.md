# Documentation index

This index separates current interpretation documents from diagnostic and historical provenance. Do not delete dated documents merely because they are old; classify them here or in a more specific index.

## Start here

| Document | Role |
|---|---|
| `README.md` | Short repository entry point. |
| `docs/CURRENT_PROJECT_STATUS.md` | Current day-to-day project status and next action. |
| `docs/REPO_MAP.md` | Directory roles and repository structure. |
| `docs/CANONICAL_START_HERE.md` | Reviewer/collaborator canonical orientation. |
| `docs/FAST_SELECTOR_EXECUTION_POLICY.md` | Cost-aware execution rules for selector work. |
| `docs/PAPER_SOURCE_OF_TRUTH.md` | Claim-eligible evidence hierarchy. |
| `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md` | Safe/supportive/unsafe claim map. |
| `docs/PAPER_OPEN_GAPS_AND_RISKS.md` | Known evidence gaps and risks. |

## Current selector / L1-defeat track

| Document | Role |
|---|---|
| `docs/SELECTOR_START_HERE.md` | Entry point for selector-first work. |
| `docs/SELECTOR_WORK_START_HERE_20260501.md` | Selector artifact front door; partly superseded by newer trace-recovery/unified-evidence work. |
| `docs/SELECTOR_CHOOSING_PLAYBOOK_20260501.md` | Decision checklist for choosing the next selector family and promotion criteria. |
| `docs/SELECTOR_EVIDENCE_RETENTION_POLICY_20260501.md` | What selector evidence packages should commit vs omit. |
| `docs/OUTCOME_VERIFIER_SELECTOR_ROADMAP.md` | Outcome-verifier selector roadmap. |
| `docs/FAST_SELECTOR_EXECUTION_POLICY.md` | API-cost-control and fast selector execution policy. |
| `docs/SELECTOR_CATALOG.md` | Selector methods and diagnostic selectors. |
| `docs/OUTPUTS_SELECTOR_TRACE_INDEX.md` | Selector trace artifact usability index. |
| `docs/ARTIFACT_INDEX_20260501.md` | Selector artifact index after Wulver transfer. |
| `docs/FOCUSED33_TRACE_ENRICHMENT_RESULT_20260501T000906Z.md` | Historical focused33 trace-enrichment result. |
| `docs/SELECTOR_AND_COVERAGE_CONTROLLER_ROADMAP_20260429.md` | Older ordered selector-vs-coverage roadmap; preserve as provenance. |
| `docs/FINAL_ADAPTIVE_LLM_INFERENCE_TRANSFER_AUDIT_20260430T034801Z.md` | Final audit of ideas transferred from the older binary-routing repository. |
| `docs/METHOD_REGISTRY_CANONICAL_20260429.md` | Method status and live-runnable/diagnostic distinctions. |

## Current selector evidence artifacts

Use these as engineering artifacts, not paper-facing claims by themselves.

| Artifact family | Status |
|---|---|
| `outputs/selector_evidence_package_*/` | Present-not-selected / absent-from-tree / current-correct-risk casebooks. |
| `outputs/selector_evidence_trace_recovery_20260501T023200Z/` | Reports 50 trace-recovered cases and 142 traced candidates, but the committed `candidate_trace_enriched.jsonl` has empty candidate lists. Needs source-package fix before unified use. |
| `outputs/conservative_trace_support_selector_20260501T025615Z/` | Negative non-API baseline: 0 overrides and 0/46 recovery on the 50-case recovery benchmark. |
| `outputs/unified_selector_evidence_*/` | Builder/scaffold and diagnostic packages. Current merged new-cap100 provenance contributes 0 candidate nodes, so not yet canonical selector input. |
| `outputs/focused33_trace_enriched_20260501T000906Z/focused33_trace_enriched.jsonl` | Older focused33 traced selector evidence. Useful but lower gold-terminal coverage. |

## Current real diagnostic artifact

Older compact selector tournament artifact:

```text
outputs/selector_tournament_compact_export_20260430T_SELECTOR_TOURNAMENT_50CASE_COHERE/
```

Associated paid real run:

```text
outputs/cohere_real_model_cost_normalized_validation_20260430T_SELECTOR_TOURNAMENT_50CASE_COHERE/
```

Important diagnostic subfolder:

```text
outputs/selector_tournament_compact_export_20260430T_SELECTOR_TOURNAMENT_50CASE_COHERE/diagnostics/selector_tournament/
```

Use compact/trace-enriched artifacts for offline selector development before launching paid runs, but check the current status doc before treating any package as canonical.

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
- Do not run paid APIs before a dry-run call count and cost-aware execution plan.

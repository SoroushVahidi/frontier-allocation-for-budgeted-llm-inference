# Frontier Allocation for Budgeted LLM Inference

This repository studies **frontier allocation for budgeted LLM inference** under explicit compute/action-budget contracts.

The project asks how to allocate limited inference compute across active reasoning/candidate paths and how to choose the final answer from the explored frontier. It is **not** the older binary cheap-vs-revise routing story.

## Current status

The active engineering goal is to turn discovered candidate-answer headroom into a reliable final-answer selector.

Recent selector work produced:

- present-not-selected selector-evidence packages;
- a 50-case trace-recovery benchmark with reported 142 traced candidate nodes;
- a deterministic no-API baseline, `conservative_trace_support_selector_v1`;
- unified selector-evidence tooling.

The key current result is a **negative baseline**: `conservative_trace_support_selector_v1` made zero overrides and recovered zero of the 46 trace-terminal recoverable cases in the 50-case recovery benchmark. This motivates an outcome-verifier selector rather than more support/source/trace-count heuristics.

The key current blocker is evidence retention/schema consistency: merged unified-evidence packages currently show `new_cap100_trace_recovery` contributing zero candidate nodes even though the trace-recovery summary reports 142 traced candidates. Fix the source trace-recovery JSONL before treating unified selector evidence as canonical input for outcome-verifier experiments.

Do **not** claim robust or broad superiority over `external_l1_max` unless a completed claim-safe evaluation document supports it.

## Start here

| Need | Read |
|---|---|
| Current project state | `docs/CURRENT_PROJECT_STATUS.md` |
| Full documentation map | `docs/DOCS_INDEX.md` |
| Reviewer/collaborator orientation | `docs/CANONICAL_START_HERE.md` |
| Repository structure | `docs/REPO_MAP.md` |
| Current selector artifact front door | `docs/SELECTOR_WORK_START_HERE_20260501.md` |
| Selector choosing checklist | `docs/SELECTOR_CHOOSING_PLAYBOOK_20260501.md` |
| Selector evidence retention policy | `docs/SELECTOR_EVIDENCE_RETENTION_POLICY_20260501.md` |
| Fast selector execution policy | `docs/FAST_SELECTOR_EXECUTION_POLICY.md` |
| Wulver artifact index | `docs/ARTIFACT_INDEX_20260501.md` |
| Focused33 trace-enrichment result | `docs/FOCUSED33_TRACE_ENRICHMENT_RESULT_20260501T000906Z.md` |
| Cleanup policy | `docs/REPOSITORY_CLEANUP_POLICY_20260501.md` |
| Outcome-verifier selector roadmap | `docs/OUTCOME_VERIFIER_SELECTOR_ROADMAP.md` |
| Selector trace artifact usability | `docs/OUTPUTS_SELECTOR_TRACE_INDEX.md` |
| Paper evidence rules | `docs/PAPER_SOURCE_OF_TRUTH.md` |
| Safe vs unsafe claims | `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md` |
| Open gaps and risks | `docs/PAPER_OPEN_GAPS_AND_RISKS.md` |

## Current selector artifacts

Important selector-evidence families:

- `outputs/selector_evidence_package_*/` — present-not-selected / absent-from-tree / current-correct-risk casebooks and summaries.
- `outputs/selector_evidence_trace_recovery_*/` — trace-recovery packages for selector cases. Verify that `candidate_trace_enriched.jsonl` actually contains candidate nodes before use.
- `outputs/conservative_trace_support_selector_*/` — deterministic non-API selector baseline outputs.
- `outputs/unified_selector_evidence_*/` — unified evidence packages. Current merged packages are diagnostic until the new-cap100 candidate-node retention issue is corrected.
- `outputs/focused33_trace_enriched_20260501T000906Z/focused33_trace_enriched.jsonl` — older focused33 traced selector evidence.

Historical Wulver selector artifacts also include:

- `outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_trace_complete.csv` — 47 aggregate trace-complete external-loss casebook rows.
- Focused subset from that casebook — 33 rows where `trace_available == gold_present_in_candidate_groups == oracle_selector_would_fix == 1`.
- `outputs/trace_complete_external_losses_retry_20260430T204900Z/cohere_real_model_cost_normalized_validation_20260430T204900Z/per_case_trace_index.csv` — raw trace index with more traced method/example rows than the 47-row external-loss casebook.

Use `docs/SELECTOR_WORK_START_HERE_20260501.md`, `docs/SELECTOR_CHOOSING_PLAYBOOK_20260501.md`, and `docs/ARTIFACT_INDEX_20260501.md` before running or interpreting selector experiments.

## API-cost rule

Paid API calls are allowed only when the next call directly produces a selector result and the expected call count is known.

For selector work:

1. Use existing candidate pools first.
2. Dry-run verifier-call count before paid scoring.
3. Cache every verifier score.
4. Do not regenerate answers just to test selectors.
5. After any paid run, immediately export a compact selector artifact and run the relevant selector evaluation.

See `docs/FAST_SELECTOR_EXECUTION_POLICY.md`.

## Current selector-track commands

Run the focused selector regression subset:

```bash
make selector-test
```

Run reviewer-safe checks:

```bash
make health
make reviewer-test
```

Run the conservative selector on a candidate-trace input:

```bash
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
python scripts/run_conservative_trace_support_selector.py \
  --input outputs/selector_evidence_trace_recovery_20260501T023200Z/candidate_trace_enriched.jsonl \
  --output-dir outputs/conservative_trace_support_selector_${STAMP} \
  --selector-name conservative_trace_support_selector_v1 \
  --min-support-margin 1 \
  --require-trace-for-override \
  --prefer-source-diversity \
  --no-gold-features
```

Inventory current trace artifacts:

```bash
python scripts/inventory_trace_artifacts.py \
  --roots outputs archive logs \
  --output-dir outputs/trace_artifact_inventory_$(date -u +%Y%m%dT%H%M%SZ)
```

Run the canonical paper artifact builder:

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## Canonical paper-facing artifacts

Canonical paper-facing evidence is generated by:

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Canonical output roots:

- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`

These are claim-eligible only when interpreted through `docs/PAPER_SOURCE_OF_TRUTH.md` and `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`.

## Current L1-defeat focus

The selector track asks:

> Given candidate answers already found by DR-v2, can an outcome verifier estimate which candidate answer is correct more safely than support/source/consistency heuristics?

The next offline step is to correct the trace-recovery JSONL retention issue, rebuild unified selector evidence, and then run an outcome-verifier selector with dry-run call accounting before any paid scoring.

## Method-surface distinction

Keep this distinction explicit:

- manuscript-facing matched-surface representative: `strict_f3`;
- broader operational default on a different surface: `strict_gate1_cap_k6`;
- DR-v2 / OV / PRM / verifier-selector variants are active L1-defeat development methods, not automatically promoted paper winners.

## What not to claim yet

- Do **not** claim robust/universal superiority over external baselines.
- Do **not** claim DR-v2, OV rerank, PRM rerank, or verifier-selector variants beat `external_l1_max` without completed paired rows.
- Do **not** treat mock-backed verifier runs as real verifier evidence.
- Do **not** present diagnostic variants as final methods unless validated and promoted by canonical docs.
- Do **not** assume historical runs have complete trace coverage.
- Do **not** treat current unified packages as fully trace-aware for new-cap100 until candidate-node retention is fixed.

## Repository organization

Important directories:

- `docs/` — interpretation, status, policy, and provenance documents.
- `experiments/` — reusable implementation modules.
- `scripts/` — runnable entry points and orchestration scripts.
- `scripts/paper/` — canonical paper artifact builders.
- `tests/` — regression and correctness tests.
- `outputs/` — generated artifacts; not authoritative by themselves.
- `neurips2026_anonymous_artifact/` — anonymous artifact staging area.
- `batch/` and `jobs/` — cluster/scheduler scripts.

See `docs/REPO_MAP.md` for the detailed map.

## Artifact safety

Timestamped real-model outputs are evidence/provenance. Do not delete, overwrite, or repurpose them casually. Prefer indexing and labeling over deletion. Use `docs/ARTIFACT_INDEX_20260501.md`, `docs/OUTPUTS_ARTIFACT_INDEX.md`, and `docs/OUTPUTS_SELECTOR_TRACE_INDEX.md` when interpreting output folders.

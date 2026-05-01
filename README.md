# Frontier Allocation for Budgeted LLM Inference

This repository studies **frontier allocation for budgeted LLM inference** under explicit compute/action-budget contracts.

The project asks how to allocate limited inference compute across active reasoning/candidate paths and how to select the final answer from the explored frontier. It is **not** the older binary cheap-vs-revise routing story.

## Current status

The repository is in a **selector-validation, baseline-comparison, and bottleneck-diagnosis phase**.

The recovery-track selector-choosing milestone is closed. The current selected working selector is:

```text
outcome_verifier_answer_group_selector_v1
scorer_mode = cached_jsonl
min_verifier_margin = 0.0
require_trace_for_override = true
dedupe_verifier_items = true
no_gold_features = true
```

Canonical selector config:

```text
configs/selected_selector_current.json
```

The selector was chosen because it produced the best audited result on the recovery selector-evidence package:

| Selector | Cases | Overrides | Fixes | Breaks | Net | Accuracy | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| `conservative_trace_support_selector_v1` | 47 | 0 | 0 | 0 | 0 | 0.0000 | rejected fallback |
| outcome verifier + `trace_quality_heuristic` | 47 | 36 | 20 | 0 | +20 | 0.4255 | runner-up |
| outcome verifier + Cohere `cached_jsonl` | 47 | 42 | 21 | 0 | +21 | 0.4468 | selected |

A selected-selector audit passed after correcting a stale selector-casebook pointer. The latest audit confirms reproducibility, cache joining, leakage checks, prompt hygiene, and scope wording for the recovery-track decision.

Important scope boundary: this is a **working selector for the recovery/selector-evidence phase**, not a runtime promotion and not an `external_l1_max` defeat claim.

## Current evidence ledger

Before using any output folder as evidence, read:

```text
docs/CURRENT_EVIDENCE_LEDGER_20260501.md
```

The ledger classifies recent artifacts as claim-eligible, diagnostic, scaffold/tooling, blocked/non-evidence, or historical provenance.

Current bottom line:

- The 47-case recovery selector result is audited and useful within its scope.
- Self-consistency is the cleanest implemented literature selector baseline.
- CMV self-verification is implemented as a literature-baseline scaffold, but not evidence-complete.
- `outputs/cohere_100case_ours_vs_external_20260501T000000Z/` is a dry-run/scaffold package with zero real calls; do not cite as results.
- `outputs/l1_loss_decomposition_best_selector_20260501T023500Z/` is a one-paired-case diagnostic; it validates plumbing but does not answer the L1-loss bottleneck question.
- The repository does not yet contain a full 100-case real-Cohere L1-loss decomposition for the best selected method.

## Current external-baseline and literature-baseline status

A cache-limited 100-case GSM8K comparison against `external_l1_max` exists in:

```text
outputs/best_selector_vs_external_l1_comparison_*/
```

That run is diagnostic rather than definitive, because most paired-set candidates did not have verifier scores and therefore the selected verifier selector mostly fell back to the original DR-v2 answer. The next claim-safe verifier-selector comparison is a **fully scored paired pilot** or larger fully scored comparison where missing selector scores are zero.

A literature-faithful self-consistency majority-vote baseline has also been added. It is useful as a no-API selector baseline over the same existing candidate pools, but it is not a new method contribution and should be compared on the same paired slices as the verifier selector.

A literature-faithful self-verification / condition-mask-verification scaffold has been added. It should remain a documented baseline scaffold unless a future bounded full-coverage run produces real comparison evidence.

## Start here

| Need | Read |
|---|---|
| Current project state | `docs/CURRENT_PROJECT_STATUS.md` |
| Current evidence ledger | `docs/CURRENT_EVIDENCE_LEDGER_20260501.md` |
| Clean navigation / organization guide | `docs/REPO_ORGANIZATION_GUIDE_20260501.md` |
| Current selector decision | `docs/CURRENT_SELECTOR_DECISION.md` |
| Full documentation map | `docs/DOCS_INDEX.md` |
| Reviewer/collaborator orientation | `docs/CANONICAL_START_HERE.md` |
| Repository structure | `docs/REPO_MAP.md` |
| Literature selector baselines | `docs/LITERATURE_SELECTOR_BASELINES.md` |
| L1-loss decomposition status | `docs/L1_LOSS_DECOMPOSITION_BEST_SELECTOR_RESULT.md` |
| Selector artifact front door | `docs/SELECTOR_WORK_START_HERE_20260501.md` |
| Selector choosing checklist | `docs/SELECTOR_CHOOSING_PLAYBOOK_20260501.md` |
| Fast selector execution policy | `docs/FAST_SELECTOR_EXECUTION_POLICY.md` |
| Paper evidence rules | `docs/PAPER_SOURCE_OF_TRUTH.md` |
| Safe vs unsafe claims | `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md` |
| Open gaps and risks | `docs/PAPER_OPEN_GAPS_AND_RISKS.md` |

## Current selector artifacts

Important selector-evidence families:

- `outputs/unified_selector_evidence_20260501T145906Z/` — corrected unified selector-evidence package used for the final recovery-track selector decision.
- `outputs/outcome_verifier_answer_group_selector_20260501T152447Z/` — dry-run verifier call plan and call-plan summary.
- `outputs/outcome_verifier_scores_cohere_smoke10_20260501T162328Z/` — completed Cohere verifier score cache for the recovery selector-evidence call plan.
- `outputs/outcome_verifier_answer_group_selector_repro_linkage_20260501T181534Z/` — regenerated selected-selector output matching the selected config.
- `outputs/selected_selector_audit_20260501T181608Z/` — passing selected-selector audit package.
- `outputs/final_selector_decision_20260501T175547Z/` — canonical final selector decision package.
- `outputs/best_selector_vs_external_l1_comparison_*/` — bounded external-baseline comparison artifacts; treat cache-limited comparisons as diagnostic unless full score coverage is recorded.
- `outputs/self_consistency_*` — self-consistency baseline outputs; treat as literature-baseline evidence and compare only with matching data slices.
- `outputs/self_verification_cmv_*` — CMV/self-verification baseline tooling and pilot outputs; do not treat as performance evidence unless full CMV coverage exists.
- `outputs/l1_loss_decomposition_best_selector_*` — L1-loss decomposition tooling outputs; only larger paired real-Cohere runs answer the bottleneck question.

Historical selector artifacts and earlier negative baselines remain useful for provenance, but should not override `configs/selected_selector_current.json`, `docs/CURRENT_SELECTOR_DECISION.md`, or `docs/CURRENT_EVIDENCE_LEDGER_20260501.md`.

## API-cost rule

Paid API calls are allowed only when the next call directly produces a selector or comparison result and the expected call count is known.

For selector and L1-loss-decomposition work:

1. Use existing candidate pools first.
2. Dry-run verifier-call count before paid scoring.
3. Cache every verifier score.
4. Do not regenerate answers merely to test selectors.
5. Keep verifier inputs gold/oracle/evaluation-only free.
6. After paid scoring, immediately run the paired evaluation and export compact artifacts.
7. If a run is blocked or cap-limited, label it diagnostic/non-evidence rather than writing fake accuracy rows.

See `docs/FAST_SELECTOR_EXECUTION_POLICY.md`.

## Current commands

Run focused selector tests:

```bash
make selector-test
```

Run reviewer-safe checks:

```bash
make health
make reviewer-test
```

Run the selected outcome-verifier selector on the recovery evidence with the cached scores:

```bash
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
python scripts/run_outcome_verifier_answer_group_selector.py \
  --input outputs/unified_selector_evidence_20260501T145906Z/unified_candidate_trace_enriched.jsonl \
  --output-dir outputs/outcome_verifier_answer_group_selector_selected_${STAMP} \
  --selector-name outcome_verifier_answer_group_selector_v1 \
  --scorer-mode cached_jsonl \
  --score-cache outputs/outcome_verifier_scores_cohere_smoke10_20260501T162328Z/verifier_scores.jsonl \
  --min-verifier-margin 0.0 \
  --require-trace-for-override \
  --dedupe-verifier-items \
  --no-gold-features
```

Run the external-baseline comparison script on an existing paired source:

```bash
python scripts/apply_selected_selector_to_paired_validation.py --help
```

Run the self-consistency literature baseline:

```bash
python scripts/run_self_consistency_majority_selector.py --help
```

Run the L1-loss-decomposition wrapper:

```bash
python scripts/run_l1_loss_decomposition_for_best_selector.py --help
```

Run the canonical paper artifact builder:

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## What to do next

The immediate engineering priority is **not another recovery-selector choice**. The current selector is selected and audited for the recovery track.

Next useful experiments:

1. Complete a paired L1-loss-decomposition run at the largest feasible real-Cohere case count, preferably 100 paired cases.
2. Run a fully scored paired selector comparison against `external_l1_max` with zero missing selector scores.
3. Compare self-consistency and the Cohere outcome-verifier selector on the same paired cases.
4. If fully scored comparisons show selector errors are no longer dominant, move effort to discovery/coverage: getting gold answers into the candidate tree.

## Canonical paper-facing artifacts

Canonical paper-facing evidence is generated by:

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Canonical output roots:

- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`

These are claim-eligible only when interpreted through `docs/PAPER_SOURCE_OF_TRUTH.md`, `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`, and `docs/CURRENT_EVIDENCE_LEDGER_20260501.md`.

## Method-surface distinction

Keep this distinction explicit:

- manuscript-facing matched-surface representative: `strict_f3`;
- broader operational default on a different surface: `strict_gate1_cap_k6`;
- DR-v2 / OV / PRM / verifier-selector variants are active L1-defeat development methods, not automatically promoted paper winners.

## What not to claim yet

- Do **not** claim robust/universal superiority over external baselines.
- Do **not** claim the selected selector is runtime-promoted.
- Do **not** present cache-limited comparisons as fully scored selector comparisons.
- Do **not** treat mock-backed verifier runs as real verifier evidence.
- Do **not** present diagnostic variants as final methods unless validated and promoted by canonical docs.
- Do **not** treat dry-run/scaffold Cohere packages as results.
- Do **not** treat the 1-case L1-loss-decomposition diagnostic as an answer to the bottleneck question.
- Do **not** assume historical runs have complete trace or score coverage.

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

See `docs/REPO_MAP.md` for the detailed map and `docs/REPO_ORGANIZATION_GUIDE_20260501.md` for cleanup/organization rules.

## Artifact safety

Timestamped real-model outputs are evidence/provenance. Do not delete, overwrite, or repurpose them casually. Prefer indexing and labeling over deletion. Use the relevant docs and manifests when interpreting output folders.

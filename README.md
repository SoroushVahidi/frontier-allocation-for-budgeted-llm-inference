# Frontier Allocation for Budgeted LLM Inference

Studies **how to allocate a fixed inference budget** across reasoning branches and **how to pick a final answer** from an explored frontier under explicit contracts.

Active work now separates two questions:

1. **discovery/coverage:** did the correct answer enter the explored candidate pool?
2. **selection/replay:** if it did, can a runtime-legal selector surface it?

Do not reinterpret the project as legacy binary cheap-vs-revise routing.

---

## Fast path

| Order | Doc | Purpose |
|------:|-----|---------|
| 0 | [`REVIEWER_FIRST.md`](REVIEWER_FIRST.md) | Minimal reviewer setup, checks, and reproduction path |
| 1 | [`docs/CURRENT_RESEARCH_HANDOFF_20260507.md`](docs/CURRENT_RESEARCH_HANDOFF_20260507.md) | **Frontier iteration 2 — read this first:** PAL+retry vs externals, failure mining, Track B/A bottlenecks |
| 2 | [`START_HERE_CURRENT.md`](START_HERE_CURRENT.md) | Short entry pointer + curated artifact links |
| 3 | [`docs/CURRENT_APPROACHES_STATUS_20260505.md`](docs/CURRENT_APPROACHES_STATUS_20260505.md) | Method-by-method status (May 2025 snapshot; cross-check with handoff doc) |
| 4 | [`docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md`](docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md) | Guardrails to avoid old-method/API-waste mistakes |
| 5 | [`docs/CLAIMS.md`](docs/CLAIMS.md) | Short claim-scope guide: safe claims, unsafe claims, evidence posture |
| 6 | [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md) | Detailed current research/engineering status |
| 7 | [`docs/CURRENT_EXTERNAL_BASELINE_GAP.md`](docs/CURRENT_EXTERNAL_BASELINE_GAP.md) | Latest bounded diagnostics vs **`external_l1_max`** |
| 8 | [`docs/REPO_MAP.md`](docs/REPO_MAP.md) | Directory map and artifact-navigation guide |

**Paper claim rules:** [`docs/PAPER_SOURCE_OF_TRUTH.md`](docs/PAPER_SOURCE_OF_TRUTH.md) · [`docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`](docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md)

**Structured indexes:** [`docs/CURRENT_METHOD_STATUS_20260507.md`](docs/CURRENT_METHOD_STATUS_20260507.md) · [`docs/CURRENT_ARTIFACTS_INDEX_20260507.md`](docs/CURRENT_ARTIFACTS_INDEX_20260507.md) · [`docs/METHOD_STATUS_TABLE.md`](docs/METHOD_STATUS_TABLE.md) · [`docs/ARTIFACT_STATUS_TABLE.md`](docs/ARTIFACT_STATUS_TABLE.md) · [`docs/DOCS_INDEX.md`](docs/DOCS_INDEX.md) · [`scripts/CURRENT_RUNBOOK.md`](scripts/CURRENT_RUNBOOK.md)

---

## Current method target for new external-baseline diagnostics

`external_l1_max` remains the strong external comparator.

For **frontier iteration 2** real-model diagnostics, the active engineered internal line is **PAL + retry / guarded PAL**:

```text
direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal
```

The tie-break stack **without** PAL integration remains a useful reference but is **not** the headline PAL line:

```text
direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak
```

The merged guarded base remains:

```text
direct_reserve_diverse_root_frontier_v1_guarded
```

Reference anchors only:

```text
strict_f3
strict_gate1_cap_k6
strict_f2
```

`strict_f3` remains a manuscript-facing matched-surface representative, but it is not the current-best target for new real-model L1-gap experiments.

---

## Current evidence posture

Read **`docs/CURRENT_RESEARCH_HANDOFF_20260507.md`** for the **300-case paired PAL+retry vs `external_l1_max`** headline and **failure-mining** status (May 2026).

Older **10-case cached-vs-live** folders (e.g. `outputs/cohere_external_l1_cached_vs_k1_frontier4_frontier_tiebreak_10case_20260505T004535Z/`) remain **historical small-slice diagnostics** for the non-PAL tie-break line—not a substitute for the PAL+retry bundles.

The audited working selector **`outcome_verifier_answer_group_selector_v1`** with **`scorer_mode = cached_jsonl`** remains selected for the **recovery / selector-evidence track only**. Machine config:

```text
configs/selected_selector_current.json
```

Human narrative + comparator tables → [`docs/CURRENT_SELECTOR_DECISION.md`](docs/CURRENT_SELECTOR_DECISION.md).

---

## Avoid this old-script trap

The following script is old-scope and should not be used as the decisive newest-method comparison:

```text
scripts/run_cohere_gsm8k_strict_f3_vs_external_l1_max_diagnostic.py
```

It is useful for historical strict-F3 reference diagnostics only. For new paid/API work, first produce a no-API dry-run following [`docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md`](docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md).

---

## Reviewer-safe commands

```bash
make health
make reviewer-test
make selector-test
```

Paper artifact regeneration:

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Full operational patterns, cluster batch names, reruns, and pitfalls → [`scripts/CURRENT_RUNBOOK.md`](scripts/CURRENT_RUNBOOK.md).

---

## What never to invent without canonical promotion

| Do not claim | Why |
|--------------|-----|
| Broad superiority over **`external_l1_max`** | Requires matched surfaces + canonical paper-source uplift |
| Runtime promotion of verifier selector | Current evidence is recovery-track only |
| Old strict-F3 results as current diverse-root results | Different method target |
| Finalguard or numeric-leaf success | Latest no-API/API checks showed no accuracy gain on target artifacts |
| Path-gap proxies as causal gold-path counts | Diagnostics carry explicit caveat fields |
| Slurm summaries without reading **`manifest.json`** | **`outputs/`** are provenance, not standalone authority |

Timestamped **`outputs/`** folders stay put. Prefer indexing, classification, and canonical interpretation over deletion.

---

## API cost

Paid APIs only under explicit manifests and [`docs/FAST_SELECTOR_EXECUTION_POLICY.md`](docs/FAST_SELECTOR_EXECUTION_POLICY.md). A paid comparison must state exact methods, case set, model, output directory, and call budget before it starts.

---

## Repo layout sketch

`experiments/` · `scripts/` · `configs/` · `outputs/` · `tests/` · `batch/` · `docs/`

Full tree → [`docs/REPO_MAP.md`](docs/REPO_MAP.md).

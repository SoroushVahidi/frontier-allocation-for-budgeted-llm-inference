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
| 1 | [`START_HERE_CURRENT.md`](START_HERE_CURRENT.md) | Current front door: merged state, current target method, external baseline, and next experiment pattern |
| 2 | [`docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md`](docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md) | Guardrails to avoid old-method/API-waste mistakes |
| 3 | [`docs/CLAIMS.md`](docs/CLAIMS.md) | Short claim-scope guide: safe claims, unsafe claims, evidence posture |
| 4 | [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md) | Detailed current research/engineering status |
| 5 | [`docs/CURRENT_EXTERNAL_BASELINE_GAP.md`](docs/CURRENT_EXTERNAL_BASELINE_GAP.md) | Latest bounded diagnostics vs **`external_l1_max`** |
| 6 | [`docs/REPO_MAP.md`](docs/REPO_MAP.md) | Directory map and artifact-navigation guide |

**Paper claim rules:** [`docs/PAPER_SOURCE_OF_TRUTH.md`](docs/PAPER_SOURCE_OF_TRUTH.md) · [`docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`](docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md)

**Structured indexes:** [`docs/METHOD_STATUS_TABLE.md`](docs/METHOD_STATUS_TABLE.md) · [`docs/ARTIFACT_STATUS_TABLE.md`](docs/ARTIFACT_STATUS_TABLE.md) · [`docs/DOCS_INDEX.md`](docs/DOCS_INDEX.md) · [`scripts/CURRENT_RUNBOOK.md`](scripts/CURRENT_RUNBOOK.md)

---

## Current method target for new external-baseline diagnostics

`external_l1_max` remains the strong external comparator. Recent real-model diagnostics show a large gap for older strict methods, but those diagnostics do **not** test the newly merged diverse-root guarded stack.

For any fresh fair comparison against `external_l1_max`, the current internal target is:

```text
direct_reserve_diverse_root_frontier_v1_guarded
```

Optional support target:

```text
direct_reserve_diverse_root_frontier_v1
```

Optional selector diagnostic:

```text
guarded + cached verifier selector replay, tau ~= 0.05, only when score coverage is complete and runtime-legal
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

The audited working selector is **`outcome_verifier_answer_group_selector_v1`** with **`scorer_mode = cached_jsonl`**. Machine config:

```text
configs/selected_selector_current.json
```

Human narrative + comparator tables → [`docs/CURRENT_SELECTOR_DECISION.md`](docs/CURRENT_SELECTOR_DECISION.md).

**Hard boundary:** this selector is selected for the **recovery / selector-evidence track only**. It is **not runtime-promoted** and is **not** an **`external_l1_max`** defeat claim.

The current external-baseline story is diagnostic: `external_l1_max` remains the strong comparator to beat, while recent loss-slice diagnostics indicate that **discovery/coverage** is often the dominant bottleneck.

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

# Frontier Allocation for Budgeted LLM Inference

Studies **how to allocate a fixed inference budget** across reasoning branches and **how to pick a final answer** from an explored frontier under explicit contracts. Active work emphasizes **selection from existing candidate pools** and **discovery/coverage diagnostics** — not legacy binary cheap-vs-revise routing.

---

## Fast path

| Order | Doc | Purpose |
|------:|-----|---------|
| 0 | [`REVIEWER_FIRST.md`](REVIEWER_FIRST.md) | Minimal reviewer setup, checks, and reproduction path |
| 1 | [`docs/CLAIMS.md`](docs/CLAIMS.md) | Short claim-scope guide: safe claims, unsafe claims, evidence posture |
| 2 | [`START_HERE_CURRENT.md`](START_HERE_CURRENT.md) | Current project status, baselines, bottleneck, and next commands |
| 3 | [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md) | Detailed current research/engineering status |
| 4 | [`docs/CURRENT_EXTERNAL_BASELINE_GAP.md`](docs/CURRENT_EXTERNAL_BASELINE_GAP.md) | Latest bounded diagnostics vs **`external_l1_max`** |
| 5 | [`docs/REPO_MAP.md`](docs/REPO_MAP.md) | Directory map and artifact-navigation guide |

**Paper claim rules:** [`docs/PAPER_SOURCE_OF_TRUTH.md`](docs/PAPER_SOURCE_OF_TRUTH.md) · [`docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`](docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md)

**Structured indexes:** [`docs/METHOD_STATUS_TABLE.md`](docs/METHOD_STATUS_TABLE.md) · [`docs/ARTIFACT_STATUS_TABLE.md`](docs/ARTIFACT_STATUS_TABLE.md) · [`docs/DOCS_INDEX.md`](docs/DOCS_INDEX.md) · [`scripts/CURRENT_RUNBOOK.md`](scripts/CURRENT_RUNBOOK.md)

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

## Recent audit breadcrumbs

| Doc | Contents |
|-----|----------|
| [`docs/LAST_10_WULVER_JOBS_AUDIT_20260502.md`](docs/LAST_10_WULVER_JOBS_AUDIT_20260502.md) | Bounded Slurm ↔ artifact mapping + post-freeze addenda |
| [`docs/FULL_SCORE_COMPLETION_88_EXTERNAL_LOSSES_20260502.md`](docs/FULL_SCORE_COMPLETION_88_EXTERNAL_LOSSES_20260502.md) | **`1018248`** zero-missing score merge story |
| [`docs/REPOSITORY_HYGIENE_AUDIT_20260502.md`](docs/REPOSITORY_HYGIENE_AUDIT_20260502.md) | Earlier navigation tidy; **no provenance deleted** |

---

## What never to invent without canonical promotion

| Do not claim | Why |
|--------------|-----|
| Broad superiority over **`external_l1_max`** | Requires matched surfaces + canonical paper-source uplift |
| Runtime promotion of verifier selector | Current evidence is recovery-track only |
| Path-gap proxies as causal gold-path counts | Diagnostics carry explicit caveat fields |
| Slurm summaries without reading **`manifest.json`** | **`outputs/`** are provenance, not standalone authority |

Timestamped **`outputs/`** folders stay put. Prefer indexing, classification, and canonical interpretation over deletion.

---

## API cost

Paid APIs only under explicit manifests and [`docs/FAST_SELECTOR_EXECUTION_POLICY.md`](docs/FAST_SELECTOR_EXECUTION_POLICY.md).

---

## Repo layout sketch

`experiments/` · `scripts/` · `configs/` · `outputs/` · `tests/` · `batch/` · `docs/`

Full tree → [`docs/REPO_MAP.md`](docs/REPO_MAP.md).

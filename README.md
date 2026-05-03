# Frontier Allocation for Budgeted LLM Inference

Studies **how to allocate a fixed inference budget** across reasoning branches and **how to pick a final answer** from an explored frontier under explicit contracts. Active work emphasizes **selection from existing candidate pools** and **discovery/coverage diagnostics** — not legacy binary cheap-vs‑revise routing.

---

## Interpretation hierarchy (start here)

| Order | Doc | Role |
|------:|-----|------|
| 0 | [`REVIEWER_FIRST.md`](REVIEWER_FIRST.md) | Shortest reviewer-facing reproduction and claim-scope guide |
| 1 | [`START_HERE_CURRENT.md`](START_HERE_CURRENT.md) | Shortest safe front door: baselines, scope, bottleneck, commands |
| 2 | [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md) | Detailed current research/engineering status |
| 3 | [`docs/CURRENT_EXTERNAL_BASELINE_GAP.md`](docs/CURRENT_EXTERNAL_BASELINE_GAP.md) | Latest narrow harness vs **`external_l1_max`** (**1018203**) |
| 4 | [`docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md`](docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md) | Negative / superseded / cache‑limited indexing |
| 5 | [`docs/DISCOVERY_FAILURE_TAXONOMY.md`](docs/DISCOVERY_FAILURE_TAXONOMY.md) | Discovery vs selector decomposition vocabulary |
| 6 | [`docs/OUTPUT_RETENTION_POLICY_CURRENT.md`](docs/OUTPUT_RETENTION_POLICY_CURRENT.md) | What belongs in Git vs local-only |

**Structured indexes:** [`docs/METHOD_STATUS_TABLE.md`](docs/METHOD_STATUS_TABLE.md) · [`docs/ARTIFACT_STATUS_TABLE.md`](docs/ARTIFACT_STATUS_TABLE.md) · [`scripts/CURRENT_RUNBOOK.md`](scripts/CURRENT_RUNBOOK.md) · [`docs/DOCS_INDEX.md`](docs/DOCS_INDEX.md)

**Paper claim rules:** [`docs/PAPER_SOURCE_OF_TRUTH.md`](docs/PAPER_SOURCE_OF_TRUTH.md) · [`docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`](docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md)

---

## Selected selector — recovery track only (`external_l1_max`‑agnostic)

The audited working selector is **`outcome_verifier_answer_group_selector_v1`** with **`scorer_mode = cached_jsonl`**. Machine config:

```text
configs/selected_selector_current.json
```

Human narrative + comparator tables → **`docs/CURRENT_SELECTOR_DECISION.md`**.

**Hard boundary:** **not runtime‑promoted** and **not** an **`external_l1_max`** defeat claim.

---

## Health / reviewer commands

```bash
make health
make reviewer-test
make selector-test
```

Full operational patterns (recovery rerun, cluster batch names, pitfalls) → **[`scripts/CURRENT_RUNBOOK.md`](scripts/CURRENT_RUNBOOK.md)**.

Paper artifact regeneration:

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

---

## Recent Wulver / audit breadcrumbs

| Doc | Contents |
|-----|----------|
| [`docs/LAST_10_WULVER_JOBS_AUDIT_20260502.md`](docs/LAST_10_WULVER_JOBS_AUDIT_20260502.md) | Bounded Slurm ↔ artifact mapping + post-freeze addenda |
| [`docs/FULL_SCORE_COMPLETION_88_EXTERNAL_LOSSES_20260502.md`](docs/FULL_SCORE_COMPLETION_88_EXTERNAL_LOSSES_20260502.md) | **`1018248`** zero-missing score merge story |
| [`docs/REPOSITORY_HYGIENE_AUDIT_20260502.md`](docs/REPOSITORY_HYGIENE_AUDIT_20260502.md) | Earlier navigation tidy; **no provenance deleted** |

---

## What never to invent without canonical promotion

| Don’t claim | Why |
|-------------|-----|
| Broad superiority over **`external_l1_max`** | Requires matched surfaces + **`PAPER_*`** uplift |
| Runtime promotion of verifier selector | Recovery-track evidence scope only |
| Path-gap proxies as causal gold‑path counts | Diagnostics carry explicit caveat fields |
| Slurm summaries without reading **`manifest.json`** contract | **`outputs/`** are provenance—not solo authority |

Timestamped **`outputs/`** folders stay put—**prefer indexing**, not deletion (**[`docs/REPO_MAP.md`](docs/REPO_MAP.md)** · **[`docs/REPO_ORGANIZATION_GUIDE_20260501.md`](docs/REPO_ORGANIZATION_GUIDE_20260501.md)**).

---

## API cost

Paid APIs only under explicit manifests + **`docs/FAST_SELECTOR_EXECUTION_POLICY.md`**.

---

## Repo layout sketch

**`experiments/`** · **`scripts/`** · **`configs/`** · **`outputs/`** · **`tests/`** · **`batch/`** · **`docs/`** interpretation layer

Full tree → **`docs/REPO_MAP.md`**.

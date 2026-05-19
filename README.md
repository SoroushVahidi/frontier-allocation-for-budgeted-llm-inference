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
| 1 | [`docs/CURRENT_STATE_SUMMARY_20260511.md`](docs/CURRENT_STATE_SUMMARY_20260511.md) | Canonical current-state summary: main evidence hierarchy, method roles, artifact map, replay status, and safe claims |
| 2 | [`START_HERE_CURRENT.md`](START_HERE_CURRENT.md) | Current front door: merged state, current target method, external baseline, and next experiment pattern |
| 3 | [`docs/CURRENT_APPROACHES_STATUS_20260505.md`](docs/CURRENT_APPROACHES_STATUS_20260505.md) | Latest method-by-method status: tested, parked, active, and next hopeful lines |
| 4 | [`docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md`](docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md) | Guardrails to avoid old-method/API-waste mistakes |
| 5 | [`docs/CLAIMS.md`](docs/CLAIMS.md) | Short claim-scope guide: safe claims, unsafe claims, evidence posture |
| 6 | [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md) | Detailed current research/engineering status |
| 7 | [`docs/CURRENT_EXTERNAL_BASELINE_GAP.md`](docs/CURRENT_EXTERNAL_BASELINE_GAP.md) | Separate strict-method diagnostic vs **`external_l1_max`** |
| 8 | [`docs/REPO_MAP.md`](docs/REPO_MAP.md) | Directory map and artifact-navigation guide |

**Latest results checkpoint:** [`docs/LATEST_RESULTS_AND_CLAIMS.md`](docs/LATEST_RESULTS_AND_CLAIMS.md) — current numbers, safe/unsafe claims, next step

**Verifier-guided reranking navigation:** [`docs/FRONTIER_ALLOCATION_VERIFIER_INTEGRATION_STATUS_20260517.md`](docs/FRONTIER_ALLOCATION_VERIFIER_INTEGRATION_STATUS_20260517.md) · [`docs/PAPER_DRAFT_VERIFIER_GUIDED_WITHIN_METHOD_RERANKING_20260517.md`](docs/PAPER_DRAFT_VERIFIER_GUIDED_WITHIN_METHOD_RERANKING_20260517.md)

**Stage-2 calibrated gate:** [`docs/STAGE2_CALIBRATED_GATE_STATUS_20260518.md`](docs/STAGE2_CALIBRATED_GATE_STATUS_20260518.md) · [`docs/STAGE2_BASELINE_GATED_HYBRID_ALLOCATOR_PLAN_20260517.md`](docs/STAGE2_BASELINE_GATED_HYBRID_ALLOCATOR_PLAN_20260517.md) · [`docs/TARGETED_COHERE_FAILURE_COLLECTION_PLAN_20260518.md`](docs/TARGETED_COHERE_FAILURE_COLLECTION_PLAN_20260518.md)

**Current Stage-2 checkpoint:** see [`docs/LATEST_RESULTS_AND_CLAIMS.md`](docs/LATEST_RESULTS_AND_CLAIMS.md) and [`docs/STAGE2_CALIBRATED_GATE_STATUS_20260518.md`](docs/STAGE2_CALIBRATED_GATE_STATUS_20260518.md). No final promoted cross-method allocation policy is claimed yet.

**Paper claim rules:** [`docs/PAPER_SOURCE_OF_TRUTH.md`](docs/PAPER_SOURCE_OF_TRUTH.md) · [`docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`](docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md)

**Structured indexes:** [`docs/METHOD_STATUS_TABLE.md`](docs/METHOD_STATUS_TABLE.md) · [`docs/ARTIFACT_STATUS_TABLE.md`](docs/ARTIFACT_STATUS_TABLE.md) · [`docs/DOCS_INDEX.md`](docs/DOCS_INDEX.md) · [`scripts/CURRENT_RUNBOOK.md`](scripts/CURRENT_RUNBOOK.md)

---

## Current evidence hierarchy

The hierarchy is stable and should be read in this order:

1. `300-case PAL+retry vs external_l1_max` is the main external-baseline evidence.
2. The `30-case` four-way Cohere pilot is diagnostic caution only.
3. The `15-case` Direct L1 strong-seed run is a targeted mixed / negative follow-up diagnostic.
4. `pal_frontier_structural_target_replay_v1` is an offline, no-API replay experiment. It is useful for structural analysis and logging, but it is not runtime promotion evidence.

## Current method target for new external-baseline diagnostics

`external_l1_max` remains the strong external comparator. Recent real-model diagnostics show a large gap for older strict methods, but those diagnostics do **not** test the newly merged diverse-root guarded stack.

The main external-baseline evidence for the current PAL line is the paired 300-case Cohere bundle:

- PAL+retry / guarded PAL: `252/300`
- `external_l1_max`: `244/300`
- paired gap: `+8` cases / `+2.67 pp`
- McNemar `p≈0.322`
- bootstrap paired-diff CI: `[-2.00 pp, +7.33 pp]`

Use that bundle as the headline comparison. Do **not** replace it with the newer 15-case Direct L1 strong-seed diagnostic.

The latest offline structural-target replay lives here:

- `outputs/gsm8k_structural_validator_eval_20260507/pal_frontier_structural_target_replay_v1_20260511T222238Z/`
- this is no-API replay only, with candidate-level structural fields and selector ablations
- do not promote runtime defaults from it

For any fresh fair comparison against `external_l1_max`, the current active internal line is:

```text
direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal
```

This is the live diagnostic/development method for the PAL line, not a paper-promoted default. The smaller k1 frontier tiebreak line remains a useful debug sidecar:

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

The current best small same-case live diagnostic is:

```text
outputs/cohere_external_l1_cached_vs_k1_frontier4_frontier_tiebreak_10case_20260505T004535Z/
```

It reports cached `external_l1_max` at **8/10** and live `k1_frontier4_frontier_tiebreak` at **6/10** on the same 10 cases. This is a small diagnostic signal only.

Current targeted diagnostics, in order of evidentiary importance:

1. The 300-case PAL+retry vs `external_l1_max` bundle is the main evidence.
2. The 30-case PAL vs three external baselines pilot is diagnostic only.
3. The 15-case Direct L1 strong-seed run is a mixed follow-up diagnostic and is not promoted.

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
| Promoted calibrated gate or gate-beats-external claim | Gate is output-only; safe-gate holdout gain neutral (`+0.00pp`); near-neighbor regressions unresolved; no disjoint promotion-grade validation yet |

Timestamped **`outputs/`** folders stay put. Prefer indexing, classification, and canonical interpretation over deletion.

---

## API cost

Paid APIs only under explicit manifests and [`docs/FAST_SELECTOR_EXECUTION_POLICY.md`](docs/FAST_SELECTOR_EXECUTION_POLICY.md). A paid comparison must state exact methods, case set, model, output directory, and call budget before it starts.

---

## Repo layout sketch

`experiments/` · `scripts/` · `configs/` · `outputs/` · `tests/` · `batch/` · `docs/`

Full tree → [`docs/REPO_MAP.md`](docs/REPO_MAP.md).

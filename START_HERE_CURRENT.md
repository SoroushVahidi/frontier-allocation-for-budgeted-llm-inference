# Start here — current front door (2026-05-04)

Short orientation for humans and agents. Historical and timestamped material stays in place; this file points to **current** interpretation and safe next actions.

**Focused notes:** [`docs/CURRENT_EXTERNAL_BASELINE_GAP.md`](docs/CURRENT_EXTERNAL_BASELINE_GAP.md) · [`docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md`](docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md) · [`docs/DISCOVERY_FAILURE_TAXONOMY.md`](docs/DISCOVERY_FAILURE_TAXONOMY.md) · [`docs/OUTPUT_RETENTION_POLICY_CURRENT.md`](docs/OUTPUT_RETENTION_POLICY_CURRENT.md) · [`docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md`](docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md)

## Current project question

Under explicit inference budgets, how should compute be allocated across reasoning paths, and how should the **final answer** be chosen from the explored frontier? The active emphasis is now two-track:

1. **discovery/coverage:** getting the correct answer into the explored candidate pool;
2. **selection/replay:** choosing among existing candidate groups without gold leakage.

Do not revert to the older binary cheap-vs-revise routing story.

## Current best external baseline

**`external_l1_max`** is the primary strong external comparator on real-model GSM8K-style slices referenced throughout the repo. Do **not** claim broad defeat of this baseline without a fully scored, matched contract and canonical doc promotion.

Related: **`external_l1_exact`** is a literature-style L1 exact-target-length variant; it appears in fairness/manuscript comparisons, but it is not a substitute for `external_l1_max` as the headline comparator.

## Current merged method/tooling state

Recent merged branches changed the live repository state:

| PR | Status | What changed |
|----|--------|--------------|
| #351 | merged | Adds `direct_reserve_diverse_root_frontier_v1`, `direct_reserve_diverse_root_frontier_v1_guarded`, guarded held-out GSM8K eval, API JSON parsing hardening, and candidate diagnostics. |
| #353 | merged | Adds cached verifier selector replay tooling and tests. No default runtime selector promotion. |

For new real-model comparisons against `external_l1_max`, the current internal method target is therefore:

```text
direct_reserve_diverse_root_frontier_v1_guarded
```

Optional supporting method:

```text
direct_reserve_diverse_root_frontier_v1
```

Optional selector diagnostic:

```text
guarded + cached verifier selector replay, tau ~= 0.05, only if score coverage is complete and runtime-legal
```

## Old-reference methods versus current target

| Method | Current role |
|--------|--------------|
| `strict_f3` | Manuscript-facing matched-surface representative and old real-model reference anchor. Not the current best-method target for new L1-gap experiments. |
| `strict_gate1_cap_k6` | Broader operational strict-phased default on a distinct surface; useful reference, not the current diverse-root target. |
| `strict_f2` | Internal comparator/reference only. |
| `direct_reserve_diverse_root_frontier_v1_guarded` | Current newest guarded diverse-root target for fresh fair comparisons. |

## Known script trap

The script below is intentionally old-scope:

```text
scripts/run_cohere_gsm8k_strict_f3_vs_external_l1_max_diagnostic.py
```

It is hardwired around `strict_f3`, `external_l1_max`, and optionally `strict_gate1_cap_k6`. Do **not** use it as the decisive current-best comparison.

For diverse-root guarded work:

```text
scripts/run_gsm8k_held_out_dr_comparison.py                  # simulator/no paid API
scripts/run_diverse_root_frontier_v1_66_eval_with_guarded.py # supports real Cohere generation
scripts/run_cached_verifier_selector_replay.py               # offline cached verifier replay
```

Before any paid run, read [`docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md`](docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md).

## Current selected selector (recovery track only)

**`outcome_verifier_answer_group_selector_v1`** with Cohere **`cached_jsonl`** scores remains selected for the recovery / selector-evidence track only. It is not automatically runtime-promoted and is not an `external_l1_max` defeat claim.

Canonical config:

```text
configs/selected_selector_current.json
```

Human-readable decision: [`docs/CURRENT_SELECTOR_DECISION.md`](docs/CURRENT_SELECTOR_DECISION.md).

## Current status vs `external_l1_max`

- Real-model and cost-normalized bundles under `outputs/cohere_real_model_cost_normalized_validation_*` are **diagnostic** unless a promotion doc says otherwise.
- The 1018203 bounded main3-vs-best3 rerun (`outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/`) reports `external_l1_max = 0.92`, curated best old internal `strict_gate1_cap_k6 = 0.57`, gap about `-0.35` on a narrow 100-case GSM8K diagnostic.
- That result is a serious warning, but it does **not** test the newly merged diverse-root guarded method.
- Fresh comparisons should therefore target `external_l1_max` versus `direct_reserve_diverse_root_frontier_v1_guarded` on the same cases, model, budget, and evaluator.

## Current bottleneck interpretation

Current evidence still points to **discovery/coverage** as the large gap against `external_l1_max`. Selector/verifier replay has shown useful signal on some slices, but not enough to close a large external-baseline gap by itself.

Working interpretation:

```text
If gold is absent from the candidate pool, no selector can recover it.
Use verifier replay to quantify selection headroom, but prioritize coverage/direct-solver-strength when the external gap remains large.
```

## Safe claims

- Audited recovery-track verifier selector evidence exists, but it is not runtime-promotion evidence.
- `external_l1_max` remains the baseline to beat on many real-model comparisons.
- Timestamped `outputs/` folders are provenance; interpretation requires manifests, summaries, and docs.
- New diverse-root guarded tooling is merged and can be used for corrected dry-run planning.

## Unsafe claims

- Robust or universal superiority over `external_l1_max`.
- Treating `strict_f3` reruns as current-best diverse-root results.
- Runtime promotion of verifier selector from replay/recovery evidence alone.
- Headline conclusions from cache-limited verifier runs, mock verifier backends, or selected external-loss slices.

## Read next

| Order | File |
|------:|------|
| 1 | `docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md` |
| 2 | `docs/CURRENT_PROJECT_STATUS.md` |
| 3 | `docs/CURRENT_EXTERNAL_BASELINE_GAP.md` |
| 4 | `docs/PAPER_SOURCE_OF_TRUTH.md` |
| 5 | `docs/CURRENT_SELECTOR_DECISION.md` |
| 6 | `docs/METHOD_STATUS_TABLE.md` |
| 7 | `docs/ARTIFACT_STATUS_TABLE.md` |
| 8 | `docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md` |
| 9 | `docs/DISCOVERY_FAILURE_TAXONOMY.md` |
| 10 | `docs/OUTPUT_RETENTION_POLICY_CURRENT.md` |

## Reviewer-safe checks

```bash
make health
make reviewer-test
make selector-test
```

Paper artifact regeneration:

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## Next experiment pattern

The next paid/API experiment should start with a **no-API dry-run** that compares:

```text
external_l1_max
vs direct_reserve_diverse_root_frontier_v1_guarded
```

The dry-run must state the case set, model, budget, exact commands, reusable completed outputs, and new Cohere call count. Paid calls require explicit approval.

## Provenance warning

Timestamped directories under `outputs/` are scientific provenance. Do not delete or reinterpret numeric folders without reading their manifests, summary JSON/MD, and docs classification. Older runs may be mock-backed, cache-limited, old-method-only, or superseded.

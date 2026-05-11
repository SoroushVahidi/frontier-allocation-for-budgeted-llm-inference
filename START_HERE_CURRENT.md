# Start here — current front door (2026-05-11)

Short orientation for humans and agents. Historical and timestamped material stays in place; this file points to **current** interpretation and safe next actions.

## Canonical Summary

Read [`docs/CURRENT_STATE_SUMMARY_20260511.md`](docs/CURRENT_STATE_SUMMARY_20260511.md) first after this file. It is the canonical handoff for the current evidence hierarchy, method status, and replay status.

## Current evidence at a glance

- Main evidence: [outputs/pal_retry_300case_analysis_20260506/report.md](/home/soroush/frontier-allocation-for-budgeted-llm-inference/outputs/pal_retry_300case_analysis_20260506/report.md)
  - PAL+retry / guarded PAL: `252/300`
  - `external_l1_max`: `244/300`
  - gap: `+8` cases / `+2.67 pp`
  - McNemar `p≈0.322`
  - bootstrap paired-diff CI: `[-2.00 pp, +7.33 pp]`
- Diagnostic caution: [outputs/cohere_pal_retry_vs_3_external_baselines_30case_20260507T152735Z/report.md](/home/soroush/frontier-allocation-for-budgeted-llm-inference/outputs/cohere_pal_retry_vs_3_external_baselines_30case_20260507T152735Z/report.md)
  - PAL `17/30`
  - `external_l1_max` `21/30`
  - `external_tale_prompt_budgeting` `20/30`
  - `external_s1_budget_forcing` `20/30`
  - diagnostic only; not headline ranking evidence
- Latest targeted follow-up: [docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_20260511T202624Z.md](/home/soroush/frontier-allocation-for-budgeted-llm-inference/docs/COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_20260511T202624Z.md)
  - baseline `direct_hybrid` vs treatment `direct_l1_strong_seed_v1`
  - seed `11`: `5/15 -> 6/15`
  - seed `23`: `6/15 -> 5/15`
  - combined exact: `11/30` for both methods
  - gold-in-tree proxy moved `15/30 -> 11/30`
  - not promoted

- Latest offline structural-target replay: `outputs/gsm8k_structural_validator_eval_20260507/pal_frontier_structural_target_replay_v1_20260511T222238Z/`
  - candidate-level structural feature layer
  - selector variants: baseline, target check, anti-intermediate filter, unit/entity ledger proxy, wrong-consensus penalty, combined structural selector
  - replay-ready primary slice: `58/158`
  - focus slice replay-ready: `0/100`
  - offline only; not runtime promotion evidence

**LATEST HANDOFF:** [`docs/CODEX_WEB_HANDOFF_20260510.md`](docs/CODEX_WEB_HANDOFF_20260510.md)

**Focused notes:** [`docs/CURRENT_APPROACHES_STATUS_20260505.md`](docs/CURRENT_APPROACHES_STATUS_20260505.md) · [`docs/CURRENT_EXTERNAL_BASELINE_GAP.md`](docs/CURRENT_EXTERNAL_BASELINE_GAP.md) · [`docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md`](docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md) · [`docs/DISCOVERY_FAILURE_TAXONOMY.md`](docs/DISCOVERY_FAILURE_TAXONOMY.md) · [`docs/OUTPUT_RETENTION_POLICY_CURRENT.md`](docs/OUTPUT_RETENTION_POLICY_CURRENT.md) · [`docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md`](docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md)

## Current project question

Under explicit inference budgets, how should compute be allocated across reasoning paths, and how should the **final answer** be chosen from the explored frontier? The active emphasis remains two-track:

1. **discovery/coverage:** getting the correct answer into the explored candidate pool;
2. **selection/replay:** choosing among existing candidate groups without gold leakage.

Do not revert to the older binary cheap-vs-revise routing story.

## Current best external baseline

**`external_l1_max`** is the primary strong external comparator on real-model GSM8K-style slices referenced throughout the repo. Do **not** claim broad defeat of this baseline without a fully scored, matched contract and canonical doc promotion.

Related: **`external_l1_exact`** is a literature-style L1 exact-target-length variant; it appears in fairness/manuscript comparisons, but it is not a substitute for `external_l1_max` as the headline comparator.

## Current active internal line

Current best engineered line:

```text
direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal
```

Small same-case diagnostic line from recent debugging:

```text
direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak
```

Key same-case 10-case diagnostic:

```text
outputs/cohere_external_l1_cached_vs_k1_frontier4_frontier_tiebreak_10case_20260505T004535Z/
```

Headline:

| Method | Exact |
|---|---:|
| cached `external_l1_max` | 8/10 = 80% |
| live `k1_frontier4_frontier_tiebreak` | 6/10 = 60% |
| gap | 20 percentage points |

This is the best current small-slice progress signal. It is **not** a broad claim of defeating `external_l1_max`.

## Current method/tooling context

| PR / line | Status | What changed |
|----|--------|--------------|
| #351 | merged | Adds `direct_reserve_diverse_root_frontier_v1`, `direct_reserve_diverse_root_frontier_v1_guarded`, guarded held-out GSM8K eval, API JSON parsing hardening, and candidate diagnostics. |
| #353 | merged | Adds cached verifier selector replay tooling and tests. No default runtime selector promotion. |
| #373 | merged | Adds **Direct L1 Anchor** support to combat frontier collapse. |
| #374 | merged | Audits Direct L1 Anchor effect; diversity increased in 100% of cases. |
| `direct_l1_strong_seed_v1` | opt-in experimental | Stronger direct seed prompt; latest 15-case live run was mixed and is not promoted. |
| `k1_frontier4_frontier_tiebreak` | active diagnostic line | Fixes much of the selection/commit issue after surfacing repairs. |
| `finalguard` | parked | No offline gain on the key 10-case artifact. |
| `numeric_leaf` | parked for now | Mechanical fields populated, but 118/800 stayed wrong. |

For details, read [`docs/CURRENT_APPROACHES_STATUS_20260505.md`](docs/CURRENT_APPROACHES_STATUS_20260505.md).

## Old-reference methods versus current target

| Method | Current role |
|--------|--------------|
| `strict_f3` | Manuscript-facing matched-surface representative and old real-model reference anchor. Not the current best-method target for new L1-gap experiments. |
| `strict_gate1_cap_k6` | Broader operational strict-phased default on a distinct surface; useful reference, not the current diverse-root target. |
| `strict_f2` | Internal comparator/reference only. |
| `direct_reserve_diverse_root_frontier_v1_guarded` | Merged guarded base; superseded by k1/tiebreak variants for active live debugging. |

## Known script trap

The script below is intentionally old-scope:

```text
scripts/run_cohere_gsm8k_strict_f3_vs_external_l1_max_diagnostic.py
```

It is hardwired around `strict_f3`, `external_l1_max`, and optionally `strict_gate1_cap_k6`. Do **not** use it as the decisive current-best comparison.

Before any paid run, read [`docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md`](docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md).

## Current selected selector (recovery track only)

**`outcome_verifier_answer_group_selector_v1`** with Cohere **`cached_jsonl`** scores remains selected for the recovery / selector-evidence track only. It is not automatically runtime-promoted and is not an `external_l1_max` defeat claim.

Canonical config:

```text
configs/selected_selector_current.json
```

Human-readable decision: [`docs/CURRENT_SELECTOR_DECISION.md`](docs/CURRENT_SELECTOR_DECISION.md).

## Current bottleneck interpretation

The bottleneck moved over time:

1. **Adapter / surfacing bugs**: fixed enough to measure live methods.
2. **Frontier budget starvation**: k1/frontier split improved this.
3. **Selection / commit**: frontier tiebreak helped substantially.
4. **Current remaining problem**: reasoning-path quality / gold-absent cases, especially where `external_l1_max` solves directly but the frontier tree does not expose the gold answer.

Working interpretation:

```text
If gold is absent from the candidate pool, no selector can recover it.
If gold is present, the frontier tiebreak is currently the best simple commit rule on the small slice.
Next useful work should improve candidate generation / direct-seed strength before another selector-only patch.
```

## Current failure mechanism hypothesis

- Main bottleneck class: gold-absent / frontier collapse / low diversity.
- Likely submechanisms: wrong target, premature intermediate answer, wrong entity-unit-state, wrong operation relation, and wrong-supported consensus.
- Counts to keep in mind: `157/157` gold-absent, `155/157` frontier collapse / low diversity, `155/157` direct-seed wrong-or-missing, `97/157` wrong-supported-consensus, `43/157` direct-L1-anchor-potential.
- Do not claim the 97 cases are solved; the labels are still incomplete and heuristic.

## Latest offline replay work

- Work item: `pal_frontier_structural_target_replay_v1`
- Output path: `outputs/gsm8k_structural_validator_eval_20260507/pal_frontier_structural_target_replay_v1_20260511T222238Z/`
- Key files: `replay_report.md`, `replay_summary.json`, `candidate_feature_rows.csv`
- New candidate-level fields: `target_tuple`, `entity_unit_ledger_proxy`, `final_answer_role`, `last_operation_family`, `target_alignment_score`, `intermediate_answer_penalty`, `duplicate_wrong_signature`, `structural_selector_score`
- Status: deterministic no-API replay only; not runtime promotion

## Safe claims

- PAL+retry / guarded PAL is directionally competitive on the 300-case paired bundle against `external_l1_max`.
- The 10-case `k1_frontier4_frontier_tiebreak` diagnostic improved the internal method from 3/10 to 6/10 against a cached 8/10 `external_l1_max` comparator.
- Audited recovery-track verifier selector evidence exists, but it is not runtime-promotion evidence.
- `external_l1_max` remains the baseline to beat on real-model comparisons.
- Timestamped `outputs/` folders are provenance; interpretation requires manifests, summaries, and docs.

## Unsafe claims

- Robust or universal superiority over `external_l1_max`.
- Treating the 15-case Direct L1 strong-seed run as the main external-baseline result.
- Treating `strict_f3` reruns as current-best diverse-root results.
- Treating finalguard or numeric-leaf variants as successful accuracy improvements; they did not improve the target artifacts.
- Runtime promotion of verifier selector from replay/recovery evidence alone.
- Headline conclusions from cache-limited verifier runs, mock verifier backends, or selected external-loss slices.

## Read next

| Order | File |
|------:|------|
| 1 | `docs/CURRENT_STATE_SUMMARY_20260511.md` |
| 2 | `docs/CURRENT_METHOD_STATUS_20260511.md` |
| 3 | `docs/CURRENT_ARTIFACTS_INDEX_20260511.md` |
| 4 | `docs/CURRENT_APPROACHES_STATUS_20260505.md` |
| 5 | `docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md` |
| 6 | `docs/CURRENT_PROJECT_STATUS.md` |
| 7 | `docs/CURRENT_EXTERNAL_BASELINE_GAP.md` |
| 8 | `docs/PAPER_SOURCE_OF_TRUTH.md` |
| 9 | `docs/CURRENT_SELECTOR_DECISION.md` |
| 10 | `docs/METHOD_STATUS_TABLE.md` |
| 11 | `docs/ARTIFACT_STATUS_TABLE.md` |
| 12 | `docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md` |
| 13 | `docs/DISCOVERY_FAILURE_TAXONOMY.md` |
| 14 | `docs/OUTPUT_RETENTION_POLICY_CURRENT.md` |

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

The next paid/API experiment should start with a **no-API dry-run**. It must state the exact method ID, case set, model, budget, output directory, reusable completed outputs, and new Cohere call count. Paid calls require explicit approval.

Current recommended next research direction is not another finalguard/numeric-leaf broad rerun. Prefer a stronger direct seed / direct+frontier hybrid or a loss-case dataset focused on examples where cached `external_l1_max` is correct and k1/tiebreak is wrong.

## Provenance warning

Timestamped directories under `outputs/` are scientific provenance. Do not delete or reinterpret numeric folders without reading their manifests, summary JSON/MD, and docs classification. Older runs may be mock-backed, cache-limited, old-method-only, or superseded.

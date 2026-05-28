# Start here — current front door (updated 2026-05-27)

Short orientation for humans and agents. Historical and timestamped material stays in place; this file points to **current** interpretation and safe next actions.

> **Note:** Content below this line dated "2026-05-11" is historical background. See canonical current state below.

---

## Canonical current state (2026-05-27)

**Read first:** [`docs/CURRENT_CANONICAL_STATE_20260527.md`](docs/CURRENT_CANONICAL_STATE_20260527.md)
**Full results:** [`docs/LATEST_RESULTS_AND_CLAIMS.md`](docs/LATEST_RESULTS_AND_CLAIMS.md)

### Current verified evidence at a glance

**Canonical paper result — FTA / FIX-2+FIX-4 (Failure-Trace Allocator):**
- Final-300 (seed=71, Cohere × GSM8K, budget=6): **86.67%** (260/300) — independently verified
- Aggregate-720 (seeds 41+61+71): **80.69%** (581/720) — source-stratified CI lo > 0 vs all externals
- Gate: FIX-2=63, FIX-4=3, no-gate=234; FIX-4 causes 0 regressions
- Leakage audit: PASS — gate features gold-free at runtime; 0 post-generation model calls
- Implementation: `experiments/support_aware_selector.py`

**Supporting evidence — D9 gated selector:**
- 5-fold grouped CV: **50.18% ± 2.52%** vs frontier 34.36% (+15.82pp)
- Gate: 0 false overrides across all tested thresholds
- D6 standalone is negative; D9 gate is required for a positive outcome

**Required paper disclosures:**
1. CI vs pooled ensemble includes zero — do not claim statistical superiority over pooled ensembles
2. Full pool generation = 4×B=6 = 24 logical calls per example
3. Evaluation: Cohere × GSM8K only; do not extrapolate to MATH-500
4. Seed=61 (59.17%) in aggregate-720 is failure-enriched, not typical

### Current project question

Under explicit inference budgets, how should compute be allocated across reasoning paths, and how should the **final answer** be chosen from the explored frontier? Active work separates:

1. **discovery/coverage:** getting the correct answer into the explored candidate pool
2. **selection/replay:** choosing among existing candidates without gold leakage

Do not revert to the older binary cheap-vs-revise routing story.

### Current best external baselines

- **`external_l1_max`** (L1): 83.00% on Final-300; 77.64% on Agg-720
- **`external_s1_budget_forcing`** (S1): 82.00% on Final-300; 77.08% on Agg-720
- **`external_tale_prompt_budgeting`** (TALE): 78.33% on Final-300; 75.14% on Agg-720
- **Pooled ensemble** (frontier+L1+S1+TALE majority): 84.33% on Final-300; 79.86% on Agg-720

FTA beats all individual externals with positive CI lower bounds. FTA leads the pooled ensemble by point estimate only (CI includes zero — must disclose).

### Current priority: paper finalization

**No API calls needed.** All canonical numbers are verified. Write the manuscript using FTA as the main result and D9 as supporting multi-provider evidence.

For D9/D6 expansion work (secondary): see `docs/CURRENT_CANONICAL_STATE_20260527.md` Section 7.

---

## Historical front door content (2026-05-11, kept for provenance)

The content below is from the 2026-05-11 handoff. It is preserved for provenance only. The PAL+retry results (252/300 vs 244/300) and old internal lines referenced below are historical background and are **superseded** by the FTA canonical result (260/300 = 86.67%).

**HISTORICAL HANDOFF:** [`docs/CODEX_WEB_HANDOFF_20260510.md`](docs/CODEX_WEB_HANDOFF_20260510.md)

Historical notes: [`docs/CURRENT_APPROACHES_STATUS_20260505.md`](docs/CURRENT_APPROACHES_STATUS_20260505.md) · [`docs/CURRENT_EXTERNAL_BASELINE_GAP.md`](docs/CURRENT_EXTERNAL_BASELINE_GAP.md) · [`docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md`](docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md) · [`docs/DISCOVERY_FAILURE_TAXONOMY.md`](docs/DISCOVERY_FAILURE_TAXONOMY.md) · [`docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md`](docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md)

Historical evidence (2026-05-11, superseded):
- PAL+retry: 252/300, external_l1_max: 244/300, gap +2.67pp, McNemar p≈0.322 — historical only
- Structural-target replay: offline diagnostic only, not runtime promotion evidence

Historical best internal line (2026-05-11, superseded by FTA):
```text
direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal
```

**These historical numbers do not override the FTA canonical result. See `docs/CURRENT_CANONICAL_STATE_20260527.md`.**

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

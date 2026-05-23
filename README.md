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
| 1 | [`docs/LATEST_RESULTS_AND_CLAIMS.md`](docs/LATEST_RESULTS_AND_CLAIMS.md) | **Canonical current results**: FIX-2+FIX-4 final-300 and aggregate-720 evidence, safe/unsafe claims, all FIX-1..8 outcomes, decision records |
| 2 | [`START_HERE_CURRENT.md`](START_HERE_CURRENT.md) | Current front door: merged state, current target method, external baseline, and next experiment pattern |
| 3 | [`docs/CURRENT_APPROACHES_STATUS_20260505.md`](docs/CURRENT_APPROACHES_STATUS_20260505.md) | Latest method-by-method status: tested, parked, active, and next hopeful lines |
| 4 | [`docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md`](docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md) | Guardrails to avoid old-method/API-waste mistakes |
| 5 | [`docs/CLAIMS.md`](docs/CLAIMS.md) | Short claim-scope guide: safe claims, unsafe claims, evidence posture |
| 6 | [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md) | Detailed current research/engineering status |
| 7 | [`docs/CURRENT_EXTERNAL_BASELINE_GAP.md`](docs/CURRENT_EXTERNAL_BASELINE_GAP.md) | Separate strict-method diagnostic vs **`external_l1_max`** |
| 8 | [`docs/REPO_MAP.md`](docs/REPO_MAP.md) | Directory map and artifact-navigation guide |
| — | [`docs/CURRENT_STATE_SUMMARY_20260511.md`](docs/CURRENT_STATE_SUMMARY_20260511.md) | Historical background only (pre-FIX series, as of 2026-05-11); superseded by `docs/LATEST_RESULTS_AND_CLAIMS.md` |

**Verifier-guided reranking navigation:** [`docs/FRONTIER_ALLOCATION_VERIFIER_INTEGRATION_STATUS_20260517.md`](docs/FRONTIER_ALLOCATION_VERIFIER_INTEGRATION_STATUS_20260517.md) · [`docs/PAPER_DRAFT_VERIFIER_GUIDED_WITHIN_METHOD_RERANKING_20260517.md`](docs/PAPER_DRAFT_VERIFIER_GUIDED_WITHIN_METHOD_RERANKING_20260517.md)

**Stage-2 calibrated gate:** [`docs/STAGE2_CALIBRATED_GATE_STATUS_20260518.md`](docs/STAGE2_CALIBRATED_GATE_STATUS_20260518.md) · [`docs/STAGE2_BASELINE_GATED_HYBRID_ALLOCATOR_PLAN_20260517.md`](docs/STAGE2_BASELINE_GATED_HYBRID_ALLOCATOR_PLAN_20260517.md) · [`docs/TARGETED_COHERE_FAILURE_COLLECTION_PLAN_20260518.md`](docs/TARGETED_COHERE_FAILURE_COLLECTION_PLAN_20260518.md)

**Frozen agreement-only validation:** [`docs/FROZEN_AGREEMENT_ONLY_2OF3_VALIDATION_PLAN_20260523.md`](docs/FROZEN_AGREEMENT_ONLY_2OF3_VALIDATION_PLAN_20260523.md) · [`docs/LIVE_VALIDATION_HARDENING_FOR_FROZEN_AGREEMENT_POLICY_20260523.md`](docs/LIVE_VALIDATION_HARDENING_FOR_FROZEN_AGREEMENT_POLICY_20260523.md) · [`docs/OFFLINE_POLICY_SEARCH_FOR_IMPROVED_DEFERRAL_20260523.md`](docs/OFFLINE_POLICY_SEARCH_FOR_IMPROVED_DEFERRAL_20260523.md)

**Current Stage-2 checkpoint:** see [`docs/LATEST_RESULTS_AND_CLAIMS.md`](docs/LATEST_RESULTS_AND_CLAIMS.md) and [`docs/STAGE2_CALIBRATED_GATE_STATUS_20260518.md`](docs/STAGE2_CALIBRATED_GATE_STATUS_20260518.md). **FIX-2+FIX-4 is the promoted policy.** Calibrated gate was evaluated and not promoted (safe-gate holdout gain neutral).

**Current operational policy checkpoint (2026-05-20):**
- Promoted policy: **FIX-2+FIX-4** (Combined Failure-Trace-Guided Allocator).
- Final-300 (seed 71, budget 6): FIX-2+FIX-4 **260/300 (86.67%)** vs L1 249/300 (83.00%) vs S1 246/300 (82.00%) vs TALE 235/300 (78.33%).
- Aggregate-720 (3 disjoint sources): FIX-2+FIX-4 **581/720 (80.69%)** vs L1 559/720 (77.64%) vs S1 555/720 (77.08%) vs TALE 541/720 (75.14%); all paired CI lower bounds > 0; Decision A recorded.
- **FIX-5** (TALE-default router): not promoted — 0 switches on final-300.
- **FIX-6 / LoVEC extra-action**: not promoted after independent stage-2 relaunch (net negative).
- **FIX-7** (cluster selector): offline prototype only, not promoted.
- **FIX-8** (robust parser): 0 recoveries on both final-300 and aggregate-720, not promoted.

---

## Recent validation and diagnostics (2026-05-23)

**Current state summary:**

- **Cohere canonical Final-300 (contract-matched):** Integrity PASS. Exact 300-ID match to `canonical_final300_exact_cases.jsonl`. Pooled-4 with fallback is strongest at **257/300 = 85.67%**; agreement-only = 247/300 = 82.33%; pooled-4 beats agreement-only by +3.33 pp (bootstrap CI [+0.0133, +0.0533], significant).
- **Mistral GSM8K Final-300:** S1 dominates at **269/300 = 89.67%**. Agreement-only = 256/300 = 85.33%. Pooled-4 = 251/300 = 83.67%. S1 superiority is explained by extreme competence heterogeneity (S1=89.7%, TALE=63.0%), not L1+TALE correlation.
- **Correlation/diversity analysis:** Pairwise phi coefficients are higher on Cohere than Mistral across all source pairs. The correct explanation is competence balance on Cohere vs competence heterogeneity on Mistral. `provider_prior_selector_cv5fold` matches the best-per-provider outcome on both (Cohere=85.67%, Mistral=89.67%).
- **Algorithmic insight — regime-dependent selection:**
  - Near-peer regime (balanced source accuracies) → pooled-4 dominates
  - Dominant-source regime (one source far above others) → provider-prior / best-source
  - Correlated-family regime → source-family voting or correlation-discounted weighting
- **Cerebras:** job (PID 2195513) was active at last check; left untouched.

**Key reports:**

| Document | Summary |
|---|---|
| [`docs/COHERE_CANONICAL_FINAL300_FROZEN_AGREEMENT_LIVE_RESULT_20260523.md`](docs/COHERE_CANONICAL_FINAL300_FROZEN_AGREEMENT_LIVE_RESULT_20260523.md) | Cohere canonical Final-300 integrity, exact ID match, full accuracy table, pooled-4 result, bootstrap CIs, old vs new comparison, algorithm recommendation |
| [`docs/ERROR_CORRELATION_AND_ENSEMBLE_DIVERSITY_DIAGNOSTIC_20260523.md`](docs/ERROR_CORRELATION_AND_ENSEMBLE_DIVERSITY_DIAGNOSTIC_20260523.md) | Pairwise phi/Q/double-fault matrices for both providers; why pooled-4 works on Cohere; why S1 dominates on Mistral; weighted voting variant evaluation; algorithm candidate decision table |
| [`docs/MISTRAL_GSM8K_FROZEN_AGREEMENT_RESULT_20260523.md`](docs/MISTRAL_GSM8K_FROZEN_AGREEMENT_RESULT_20260523.md) | Mistral final-300 frozen agreement-only and pooled-4 live results |
| [`docs/MISTRAL_S1_DOMINANCE_DIAGNOSTIC_20260523.md`](docs/MISTRAL_S1_DOMINANCE_DIAGNOSTIC_20260523.md) | Why S1 dominates on Mistral; source accuracy heterogeneity analysis |
| [`docs/MISTRAL_S1_ALGORITHM_IMPROVEMENT_DIAGNOSTIC_20260523.md`](docs/MISTRAL_S1_ALGORITHM_IMPROVEMENT_DIAGNOSTIC_20260523.md) | Mistral-derived correlation-aware rules and algorithm improvement candidates |
| [`docs/MISTRAL_CASE_ANALYSIS_AGREEMENT_LOSES_TO_S1_20260523.md`](docs/MISTRAL_CASE_ANALYSIS_AGREEMENT_LOSES_TO_S1_20260523.md) | Case-level analysis of examples where agreement-only loses to S1 on Mistral |
| [`docs/MISTRAL_L1_TALE_CORRELATED_ERROR_DIAGNOSTIC_20260523.md`](docs/MISTRAL_L1_TALE_CORRELATED_ERROR_DIAGNOSTIC_20260523.md) | L1+TALE correlated error analysis: bad majority patterns, independence tests |
| [`docs/CORRELATION_AWARE_TRANSFER_RISK_DIAGNOSTIC_20260523.md`](docs/CORRELATION_AWARE_TRANSFER_RISK_DIAGNOSTIC_20260523.md) | Transfer-risk evaluation of Mistral-derived correlation-aware rules on Cohere |
| [`docs/COHERE_CEREBRAS_HEALTH_STATUS_20260523.md`](docs/COHERE_CEREBRAS_HEALTH_STATUS_20260523.md) | Non-invasive health check for both active jobs on 2026-05-23 |

**Paper claim rules:** [`docs/PAPER_SOURCE_OF_TRUTH.md`](docs/PAPER_SOURCE_OF_TRUTH.md) · [`docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`](docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md)

**Structured indexes:** [`docs/METHOD_STATUS_TABLE.md`](docs/METHOD_STATUS_TABLE.md) · [`docs/ARTIFACT_STATUS_TABLE.md`](docs/ARTIFACT_STATUS_TABLE.md) · [`docs/DOCS_INDEX.md`](docs/DOCS_INDEX.md) · [`scripts/CURRENT_RUNBOOK.md`](scripts/CURRENT_RUNBOOK.md)

---

## Current evidence hierarchy

The hierarchy is stable; read in this order:

1. **Aggregate-720 — primary promotion-grade evidence.** FIX-2+FIX-4 vs all baselines across 3 disjoint 240-case runs (seeds 41, 61, 71): 581/720 (80.69%) vs L1 559/720 (77.64%) vs S1 555/720 (77.08%) vs TALE 541/720 (75.14%). Source-stratified bootstrap 5 000 resamples; all paired CI lower bounds > 0; p(delta>0) ≥ 0.995 vs best external. Decision A recorded. Full detail: [`docs/LATEST_RESULTS_AND_CLAIMS.md`](docs/LATEST_RESULTS_AND_CLAIMS.md).
2. **Final-300 (seed 71, budget 6) — supporting evidence.** FIX-2+FIX-4 260/300 (86.67%) vs L1 249/300 (83.00%); consistent with aggregate-720.
3. **PAL+retry vs external_l1_max (300-case, seed 41) — historical, superseded.** 252/300 vs 244/300 (+2.67pp, McNemar p≈0.322, CI [−2.00pp, +7.33pp]). Not statistically decisive; context only.
4. **RelationReady verifier within-method reranking — closed phase.** +4.58pp vs random seed, cluster-CI lower bound +0.28pp. Within-method only; cross-method routing was method-entangled and not promoted.

## Current promoted method

`direct_reserve_semantic_frontier_v2` with **FIX-2+FIX-4** gates is the promoted policy. Do not use or report results for the superseded `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal` line as the headline comparison.

---

## Current evidence posture

Primary evidence: aggregate-720 with FIX-2+FIX-4. All baselines (L1, S1, TALE) are beaten with source-stratified CI lower bounds > 0. Project is now in write-up phase.

PAL+retry diagnostics (300-case, 30-case, 15-case) are historical context. Do not use them as the headline comparison in any new analysis, paper draft, or agent response. See [`docs/LATEST_RESULTS_AND_CLAIMS.md`](docs/LATEST_RESULTS_AND_CLAIMS.md) for the complete evidence record.

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
| PAL+retry bundle as current headline result | Superseded by FIX-2+FIX-4 aggregate-720 evidence; was not statistically decisive |
| Cross-method verifier routing superiority | Verifier cross-method routing was method-entangled; within-method reranking only is valid |
| Old strict-F3 results as current diverse-root results | Different method target |
| FIX-5/6/7/8 improvements | All tested and not promoted; see `docs/LATEST_RESULTS_AND_CLAIMS.md` §FIX-5 through §FIX-8 |
| Path-gap proxies as causal gold-path counts | Diagnostics carry explicit caveat fields |
| Slurm summaries without reading **`manifest.json`** | **`outputs/`** are provenance, not standalone authority |
| Promoted calibrated gate or gate-beats-external claim | Gate evaluated; safe-gate holdout gain neutral (`+0.00pp`); not promoted |

Timestamped **`outputs/`** folders stay put. Prefer indexing, classification, and canonical interpretation over deletion.

---

## API cost

Paid APIs only under explicit manifests and [`docs/FAST_SELECTOR_EXECUTION_POLICY.md`](docs/FAST_SELECTOR_EXECUTION_POLICY.md). A paid comparison must state exact methods, case set, model, output directory, and call budget before it starts.

---

## Repo layout sketch

`experiments/` · `scripts/` · `configs/` · `outputs/` · `tests/` · `batch/` · `docs/`

Full tree → [`docs/REPO_MAP.md`](docs/REPO_MAP.md).

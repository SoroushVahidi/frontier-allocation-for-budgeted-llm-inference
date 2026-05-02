# Start here — current front door (2026-05-02)

Short orientation for humans and agents. Historical and timestamped material stays in place; this file only points to **current** interpretation.

## Current project question

Under explicit inference budgets, how should compute be allocated across reasoning paths, and how should the **final answer** be chosen from the explored frontier? The active emphasis is **selection from existing candidate pools** and **selector baselines**, with discovery/coverage work driven by evidence—not the older binary cheap-vs-revise routing story.

## Current best external baseline

**`external_l1_max`** — treat as the primary strong external comparator on real-model GSM8K-style slices referenced throughout the repo. Do **not** claim broad defeat of this baseline without a fully scored, matched contract and canonical doc promotion.

Related: **`external_l1_exact`** — literature-style L1 “exact target length” variant; appears in fairness/manuscript comparisons, not a substitute for `external_l1_max` as the headline comparator.

## Current selected selector (recovery track only)

**`outcome_verifier_answer_group_selector_v1`** with Cohere **`cached_jsonl`** scores, **`min_verifier_margin = 0.0`**, trace required for override, deduped verifier items, **no gold features** in prompts/decisions.

- **Canonical machine config:** `configs/selected_selector_current.json`
- **Human-readable decision:** `docs/CURRENT_SELECTOR_DECISION.md`

**Critical:** This selector is **chosen for the recovery / selector-evidence track**. It is **not** automatically **runtime-promoted** and is **not** an `external_l1_max` defeat claim.

## Current best full method / active internal family (canonical docs)

- **Manuscript-facing matched-surface internal representative:** **`strict_f3`** (see `docs/PAPER_SOURCE_OF_TRUTH.md`).
- **Broader operational strict-phased default on a different surface:** **`strict_gate1_cap_k6`**.
- **Active development / generator family for L1-defeat and real-model diagnostics:** **`direct_reserve_semantic_frontier_v2`** and attached rerank/selector variants (outcome-verifier rerank, PRM step rerank, etc.).

**`direct_reserve_semantic_frontier_v2`** is central to current engineering, but **canonical evidence does not support broad superiority over `external_l1_max`** on completed diagnostic slices.

## Current status vs `external_l1_max`

- Real-model and cost-normalized bundles under `outputs/cohere_real_model_cost_normalized_validation_*` are **diagnostic** unless a promotion doc says otherwise (`docs/PAPER_SOURCE_OF_TRUTH.md`).
- **1018203 bounded main3-vs-best3 rerun** (`outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/`): artifacts report **`external_l1_max` = 0.92**, curated best internal **`strict_gate1_cap_k6` = 0.57**, gap **≈ −0.35**, **narrow 100-case GSM8K** (seed **`20260501`**, budget **6**). **Subset-only** headline — reinforces internal-vs-external **`external_l1_max` lag** narrative without universality claim.
- Bounded selector-vs-`external_l1_max` comparisons exist (e.g. `outputs/best_selector_vs_external_l1_comparison_*/`) but **cache-limited** verifier coverage has forced fallbacks—treat as **diagnostic**, not headline defeat evidence, until missing score and fallback counts are zero.

## Current bottleneck (88 external-loss subset)

On the **selected 88-case external-loss slice** (`outputs/best_methods_on_external_losses_20260430T195200Z/`, summarized in `docs/BEST_METHODS_ON_EXTERNAL_LOSS_CASES_100_20260430T195659Z.md`), **discovery/coverage failure dominates** over selector recoverability (order-of-magnitude: **~66 gold-absent** vs **~22 selector-recoverable** on that slice definition). Job **1018248** completed a **zero-missing-score**, **zero-fallback** verifier merge and selector rerun on those 88 cases; **`comparison_vs_previous_run.json` reports no correctness changes** versus the cache-limited pre-merge run (**1018219**) — bottleneck evidence still points **away from verifier-score gaps**.

**Latest Wulver job audit:** `docs/LAST_10_WULVER_JOBS_AUDIT_20260502.md` plus `outputs/last_10_wulver_jobs_audit_20260502T220857Z/` (CSV/JSON and `artifact_summary.md`). **Preferred gold-absent path-gap proxy bundle:** `outputs/gold_absent_path_gap_diagnostic_20260502T215957Z/` (**1018287**; supersedes the looser heuristic in **`...215820Z/`**, **1018285**).

**Post-audit update:** **`summary.json`** for **1018203** finalized (`status:"ok"`); **`1018304`** strategy-seeded **66-case** diagnostic bundle summarizes a **semantic-diversity-frontier pilot** — interpret only with manifests + caveat that **baseline alignment / implementation QA** remains open.

Canonical audit tying untracked vs ignored artifacts: **`docs/UNCOMMITTED_RECENT_ARTIFACTS_AUDIT_20260502.md`**.

Details and score-completion runbook links: `docs/FULL_SCORE_COMPLETION_88_EXTERNAL_LOSSES_20260502.md`.

## Safe claims (short list)

- Audited **recovery-track** selected verifier selector; beats conservative and trace-quality baselines **on that evidence package**.
- **`external_l1_max`** is the baseline to beat on many real-model comparisons; repository explicitly guards against over-claiming.
- Self-consistency majority vote exists as a **literature** selector baseline (no API), for **matched-slice** comparison only.
- Timestamped `outputs/` folders are **provenance**; interpretation requires docs and manifests.

## Unsafe claims (do not make without new evidence + doc updates)

- Robust or universal **superiority over `external_l1_max`**.
- **Runtime promotion** of the outcome-verifier answer-group selector from recovery-track evidence alone.
- Headline conclusions from **cache-limited** verifier runs or **mock** verifier backends as if they were full Cohere verifier evidence.
- Broad paper wins from **selected external-loss** or **recovery** slices alone.

## Read next (exact files)

| Order | File |
|------|------|
| 1 | `docs/CURRENT_PROJECT_STATUS.md` |
| 2 | `docs/PAPER_SOURCE_OF_TRUTH.md` |
| 3 | `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md` |
| 4 | `docs/CURRENT_SELECTOR_DECISION.md` |
| 5 | `docs/METHOD_STATUS_TABLE.md` |
| 6 | `docs/ARTIFACT_STATUS_TABLE.md` |
| 7 | `docs/REPO_ORGANIZATION_GUIDE_20260501.md` |

## Commands — health and reviewer-safe checks

```bash
make health
make reviewer-test
make selector-test   # selector/L1-defeat focused pytest subset
```

## Commands — selected selector rerun (recovery package)

See `scripts/CURRENT_RUNBOOK.md` for the exact invocation; canonical pattern matches `README.md` (same flags as `configs/selected_selector_current.json`).

## Commands — next experiments (from canonical status)

1. **Fully scored paired pilot vs `external_l1_max`:** zero missing verifier scores, zero fallback-to-incumbent due to missing scores (`docs/CURRENT_PROJECT_STATUS.md`).
2. **Self-consistency vs verifier selector** on the **same paired slice:** `python scripts/run_self_consistency_majority_selector.py --help`
3. **88-case external-loss diagnostics (cluster):** `batch/run_full_pipeline_best_selector_on_88_external_losses_wulver.sbatch`, score completion: `batch/run_full_score_completion_on_88_external_losses_wulver.sbatch` (read `docs/FULL_SCORE_COMPLETION_88_EXTERNAL_LOSSES_20260502.md` first).

No paid API calls are implied by this document; follow `docs/FAST_SELECTOR_EXECUTION_POLICY.md` before any scoring run.

## Provenance warning

**Timestamped directories under `outputs/` are scientific provenance.** Do not reinterpret numeric folders without reading the linked **manifests, summary JSON/MD, and `docs/` classification**. Older runs may be mock-backed, cache-limited, or superseded—see `docs/ARTIFACT_STATUS_TABLE.md` and `docs/PAPER_SOURCE_OF_TRUTH.md`.

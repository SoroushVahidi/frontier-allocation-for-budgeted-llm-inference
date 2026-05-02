# Failed, negative, superseded, and diagnostic-limited runs — index

This index catalogs **runs that must not be overclaimed**, while preserving **scientific provenance**. Timestamped `outputs/` trees are **not deleted**; they stay as evidence. Use this doc to steer readers toward **current** interpretation docs:

- **`docs/CURRENT_PROJECT_STATUS.md`** — detailed operational status
- **`docs/CURRENT_EXTERNAL_BASELINE_GAP.md`** — headline vs **`external_l1_max`**
- **`docs/ARTIFACT_STATUS_TABLE.md`** — output-family classifications
- **`docs/OUTPUT_RETENTION_POLICY_CURRENT.md`** — commit vs local-only policy

---

## Why negative results are preserved

Incomplete runs, cache-limited selector paths, superseded diagnostics, and pilot regressions explain **engineering and claim boundaries**. Omitting them would invite **silent overfitting of narrative**. Treat them like lab notebooks: cite with **scope**, not as universal truth.

---

## Cache-limited / fallback-limited runs

| Item | Summary | Risk if overclaimed |
|------|---------|---------------------|
| **`outputs/best_selector_vs_external_l1_comparison_*/`** | Selected verifier selector comparisons where **paired candidates lack verifier scores** | Headline selected-selector behaviour without reporting missing scores / fallbacks |
| **1018219 — full pipeline on 88 external-loss slice** (`outputs/full_pipeline_best_selector_on_88_external_losses_20260502T210610Z/`) | Pre–score-completion: **`missing_score_count`** and **`fallback_due_to_missing_score_count`** were large (paired with verifier cache gaps; see manifests / `LAST_10` audit) | Misreading as zero-fallback final selector behaviour |
| **1018248 supersession** | **1018248** merged scores and reran selector with **`missing_score_count = 0`**, **`fallback_due_to_missing_score_count = 0`** (**`comparison_vs_previous_run`** unchanged correctness) — see below | Cherry-picking **1018219** without **1018248** |

---

## Superseded diagnostics

| Supersedes | By | Notes |
|------------|---|-------|
| **1018285** — `outputs/gold_absent_path_gap_diagnostic_20260502T215820Z/` | **1018287** — `outputs/gold_absent_path_gap_diagnostic_20260502T215957Z/` | Tighter premature-commit heuristic; counts **shift** materially—quote **8287** for current proxy labels |
| Older “last‑10 audit freeze” wording on **1018203 RUNNING** | Post-freeze **`summary.json`** + committed summaries | Canonical numbers: **`docs/CURRENT_EXTERNAL_BASELINE_GAP.md`**, bundle `outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/` |

---

## Strategy-seeded discovery pilot (**1018304**)

**Output:** `outputs/strategy_seeded_discovery_on_66_gold_absent_20260502T222129Z/`

**Method:** **`strategy_seeded_semantic_diversity_frontier_v1`** on intentional **66** gold-absent diagnostic slice vs cached DR‑v2 baseline. **`discovery_summary.json`:** **`baseline_gold_present_count = 49`**, **`new_gold_present_count = 42`** (Δ **−7**), **`discovery_recovered_count = 1`**.

**Interpretation:** **Diagnostic pilot.** **Implementation / baseline-alignment QA** remains open—**do not** treat Δ as final scientific rejection of the direction until **final audit / rerun** completes (see `outputs/strategy_seeded_discovery_final_check_*` curated audit stubs and **`direct_reserve_strategy_seeded_semantic_frontier_v2_final`** in **`docs/METHOD_STATUS_TABLE.md`**).

---

## External-baseline gap diagnostics (narrow harness)

**1018203 — main3-vs-best3 100‑case GSM8K:**

- Completed **`status:"ok"`**; **`external_l1_max` ≈ 0.92**, best curated internal **`strict_gate1_cap_k6` ≈ 0.57**, gap ≈ **−0.35** (seed **`20260501`**, budget **6**).
- **Negative for internal-vs-external headline** **on this narrow slice only** — **not** a universal GSM8K or cross-provider theorem. Detail: **`docs/CURRENT_EXTERNAL_BASELINE_GAP.md`**.

---

## Zero-missing-score 88-loss rerun (**1018248**) — still mostly wrong

Artifact: **`outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/`** (`summary.json`):

- **`evaluated_cases` = 88**, **`correct_count` = 19**, **`still_lost_count` / `wrong_count` = 69**
- **`missing_score_count` = 0**, **`fallback_due_to_missing_score_count` = 0**, **`selected_candidate_not_in_pool_count` = 0**
- **`selector_recoverable_count` = 22**, **`discovery_failure_count` / `gold_absent_count` = 66**, **`gold_present_but_not_selected_count` = 22**

**Negative result shape:** verifier coverage gaps were **eliminated**, yet **discovery/coverage** still dominates decomposition—**subset-only** framing.

---

## Failed / incomplete Slurm jobs (**1017716**, etc.)

| JobID | Issue | Guidance |
|-------|-------|----------|
| **1017716** | **FAILED** rapid exit; incomplete provenance linkage in-repo | **Do not cite** unpublished metrics tied solely to ID until stdout/stderr or `outputs/` mapping is recovered (`docs/LAST_10_WULVER_JOBS_AUDIT_20260502.md`) |

---

## What not to cite as a headline claim

Without explicit promotion in **`docs/PAPER_SOURCE_OF_TRUTH.md`**:

- **`external_l1_max` superiority** beyond **matched**, **fully scored** slices
- **Runtime promotion** of recovery-track selected selector
- **Path-gap CSV/JSON** as **literal missing gold-path edge counts** (proxy / estimate only unless gold path observed)
- **`1018304` pilot Δ** as final rejection absent alignment audit
- **88-loss** aggregates as headline paper wins **outside documented subset contract**

---

See also **`docs/UNCOMMITTED_RECENT_ARTIFACTS_AUDIT_20260502.md`** for Git ignore / local-only artifact hygiene.

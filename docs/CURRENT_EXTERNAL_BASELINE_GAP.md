# Current gap vs **`external_l1_max`**

Single-page note tying **narrow real-model diagnostics** to the headline external comparator **`external_l1_max`**. This is **not** a dominance claim sheet; read **`docs/PAPER_SOURCE_OF_TRUTH.md`** and **`docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`** before any manuscript wording.

Related: **`docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md`**, **`docs/DISCOVERY_FAILURE_TAXONOMY.md`**, **`START_HERE_CURRENT.md`**.

---

## May 2026 frontier-iteration update

This page still records the older narrow main3-vs-external gap below. For the current PAL+retry line, use `START_HERE_CURRENT.md`, `docs/CURRENT_RESEARCH_HANDOFF_20260507.md`, and `docs/MIGRATION_TRANSFER_INDEX_20260509.md`.

Current claim-safe PAL+retry evidence:

- `outputs/pal_retry_300case_analysis_20260506/`: PAL+retry `252/300` vs `external_l1_max` `244/300`; directionally positive / competitive, but not statistically decisive.
- `outputs/external_full_suite_matched50_comparison_20260508T222631Z/`: `production_equiv_v1` `36/50`, `external_pal_pot_fair_v1` `40/50`, and `external_self_consistency_6_fair_v1` `36/50`; do not claim production-equivalent beats every individual external baseline.

---

## Latest bounded main harness — Slurm **1018203**

**Primary bundle:** `outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/` (`summary.json`, `comparison_table.csv`, `manifest.json`; sidecars `command.sh`, `monitor_log.txt`).

| Field | Value |
|-------|-------|
| **Status** | `ok` |
| **Dataset** | **`openai/gsm8k`** |
| **Design** | **100** scored rows per listed method (**100 cases / method**) |
| **Seed** | **`20260501`** |
| **Budget** | **`6`** (action budget contract in runner) |
| **Provider / model** (from committed invocation) | **Cohere** `command-a-03-2025` (`command.sh`; confirm `manifest.json` for any rerun drift) |
| **External methods** | **`external_l1_max`**, **`tale`**, **`s1`** |
| **Internal methods** | **`strict_f3`**, **`strict_gate1_cap_k6`**, **`strict_f2`** |
| **Best external (accuracy headline)** | **`external_l1_max` ≈ 0.92** |
| **Best internal headline (table)** | **`strict_gate1_cap_k6` ≈ 0.57** |
| **Gap (`best_internal − best_external`)** | ≈ **−0.35** |

### What this **supports**

- **Narrow diagnostic wording:** curated **internal** headline methods **trail `external_l1_max`** under this **`openai/gsm8k`** slice, **`seed`, budget, provider** pairing as persisted in manifests.
- **Alignment with guarded repo narrative:** **do not casual‑invert into “we beat L1 externally”** absent matched, broader evidence.

### What this **does not** support

- Universal conclusions across **all datasets**, budgets, seeds, or providers
- Substitution for **paper-canonical matched-surface** claims (`strict_f3` contract—see **`PAPER_SOURCE_OF_TRUTH`**)
- Implicit **selector** story (this harness is generator / external‑vs‑internal **accuracy comparison**, distinct from verifier-selector fallback diagnostics)

---

## Relation to **88‑case external-loss** diagnostics (**1018248**)

**Fully scored selector rerun:** `outputs/full_score_completed_best_selector_on_88_external_losses_20260502T213834Z/` — **`missing_score_count = 0`**, **`fallback_due_to_missing_score_count = 0`**.

**Residual failure shape** on that intentional slice: **`discovery_failure_count` / `gold_absent_count` = 66** vs **`gold_present_but_not_selected_count` = `selector_recoverable_count` = 22** — selectors can fix many **gold-visible** omissions, yet **overall** bottleneck remains **discovery/coverage-heavy** versus **narrow main3-vs-external GSM8k gap** framing above.

Interpret together: **`external_l1_max` remains a stiff external comparator** while **coverage** dominates selected loss slices—not a contradiction if slice contracts differ.

---

## Current research framing (engineering)

Improve **discovery** so internal generators recover **near direct-solver strength** (“direct-solution” competitive band) **while preserving useful exploration semantics** — then re-evaluate under **explicit matched contracts**.

---

## Cross-links

- **Slurm job audit breadcrumbs:** **`docs/LAST_10_WULVER_JOBS_AUDIT_20260502.md`** (addendum references **1018203** completion)
- **Artifact row:** **`docs/ARTIFACT_STATUS_TABLE.md`** → `outputs/main3_external_vs_best3_internal_100case_20260502T203851Z/`
- **Retention policy:** **`docs/OUTPUT_RETENTION_POLICY_CURRENT.md`**

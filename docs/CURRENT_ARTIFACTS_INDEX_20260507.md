# Current artifacts index (2026-05-07)

Tracks **canonical curated outputs** vs **local-only / heavy** artifacts for the frontier-iteration-2 line. Do not cite raw JSONL paths as paper evidence without reading manifests and summaries.

**Legend — tracked:** whether the directory (or representative files) is **currently git-tracked** on `research-next-frontier-iteration-2` as of this handoff pass.

---

## 1. `outputs/pal_retry_300case_analysis_20260506/`

| Field | Value |
|-------|--------|
| **Tracked** | Yes (representative summaries + `report.md`). |
| **Purpose** | Offline analysis package for **300-case paired PAL+retry vs `external_l1_max`**. |
| **Case count** | 300 paired. |
| **Methods** | PAL+retry (`…frontier_tiebreak_pal`) vs `external_l1_max`. |
| **Headline** | PAL **252/300** vs L1 **244/300**; paired gap **+8** cases (~**+2.67 pp**); McNemar *p*≈**0.322**; bootstrap CI crosses zero. |
| **Claim eligibility** | Directional paired improvement **only**—not decisive superiority. |
| **Caveats** | Single bundle/seed/budget—check folder `manifest.json` / `report.md` if present. |
| **Heavy / local-only** | Any duplicated raw logs—prefer **`report.md`** for sharing. |
| **Safe to commit** | `report.md`, small CSV summaries if curated. |

---

## 2. `outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/`

| Field | Value |
|-------|--------|
| **Tracked** | Partially (historical paired bundle referenced from main-line docs). Confirm with `git ls-files`. |
| **Purpose** | **Canonical paired-run artifact** backing 300-case headline (PAL retry vs external L1). |
| **Case count** | 300. |
| **Methods** | PAL+retry vs `external_l1_max`. |
| **Headline** | Same as §1—use **one** canonical summary to avoid double-counting. |
| **Heavy / local-only** | Full `*.jsonl` rows—keep local or object storage; cite aggregates only. |

---

## 3. `outputs/failure_case_corpus_20260507/`

| Field | Value |
|-------|--------|
| **Tracked** | Yes (`failure_cases.jsonl`, `failure_cases.csv`, summaries—verify with `git status`). |
| **Purpose** | **48-case** structured failure corpus from PAL-loss mining + pattern seeds + integration notes. |
| **Case count** | 48 book + follow-up markdown (`integrated_30case_4way_followup.md`). |
| **Methods** | PAL line vs externals (see corpus columns). |
| **Headline** | Taxonomy counts (external-only vs both-wrong vs gold-absent)—see `pattern_seed_report.md`. |
| **Claim eligibility** | Diagnostic / mining only. |
| **Heavy / local-only** | Large CSV duplication—prefer tracked summaries. |
| **Safe to commit** | `case_index.md`, `pattern_seed_report.md`, `feature_summary.json`, curated checklist MD. |

---

## 4. `outputs/cohere_pal_retry_vs_3_external_baselines_30case_20260507T152735Z/`

| Field | Value |
|-------|--------|
| **Tracked** | **No** (untracked in current worktree—local bundle). |
| **Purpose** | **30-case 4-way** pilot: PAL vs **`external_l1_max`**, **`external_tale_prompt_budgeting`**, **`external_s1_budget_forcing`**. |
| **Case count** | 30. |
| **Headline** | PAL **17/30**; each external **20–21/30** on same slice (see bundle summary). |
| **Claim eligibility** | Pilot-only—small *n*, not headline ranking of PAL vs world. |
| **Heavy / local-only** | Raw traces—keep local; commit only **`summary.md` / JSON** if curated. |

---

## 5. `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/`

| Field | Value |
|-------|--------|
| **Tracked** | **No** (untracked bundle locally). |
| **Purpose** | **45-case** selected failure collection + **247-ID** 4-way scoring exports + mining/replay. |
| **Case count** | 45 selected failures; **247** evaluated IDs for 4-way table. |
| **Methods** | PAL+retry vs three externals (see `failure_collection_summary.json`). |
| **Headline** | PAL **189/247**; externals **175–184/247–245**; outcome buckets (**183** both correct, **34** external-only, etc.). |
| **Claim eligibility** | Failure taxonomy + replay diagnostics—**not** a headline win claim. |
| **Heavy / local-only** | **`per_example_records.jsonl`**, **`all_results.jsonl`**—do **not** bulk-commit. |
| **Safe to commit (selective)** | `failure_collection_summary.json`, `failure_pattern_mining_report.md`, `present_not_selected_replay_report.md`, `counterfactual_policy_summary.csv`, `track_b_commitment_design_contract.md`. |

---

## 6. Older outputs (reference only)

Many **`outputs/cohere_real_model_cost_normalized_validation_*`** folders exist for historical strict-phase vs external diagnostics. Use **`docs/METHOD_STATUS_TABLE.md`** and **`docs/CURRENT_METHOD_STATUS_20260507.md`** to avoid confusing **`strict_f3` / `strict_gate1_cap_k6`** slices with **PAL+retry** slices.

---

## Reading order for artifacts

1. **`docs/CURRENT_RESEARCH_HANDOFF_20260507.md`** (narrative).  
2. **`outputs/pal_retry_300case_analysis_20260506/report.md`** (300-case paired story).  
3. **`outputs/failure_case_corpus_20260507/pattern_seed_report.md`** (failure taxonomy seeds).  
4. **`outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/`** summaries (if present locally).  

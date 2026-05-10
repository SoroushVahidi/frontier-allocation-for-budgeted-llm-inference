# Integrated follow-up: 30-case 4-way pilot + 48-case failure corpus + TRCE checklist

Offline synthesis only (no code changes, no API calls). Sources: `pilot_failure_pattern_analysis.md`, `pal_loss_external_win_cases.csv`, `failure_cases.csv`, `selected_discovery_hypothesis_checklist.md`, `trce_offline_validation_report.md`, `trce_offline_validation_ledger.csv`, PAL-retry 300-case summaries, and raw `results.jsonl` from the pilot bundle.

---

## A. Summary of new 30-case evidence

- **Design:** Four Cohere methods on **`openai_gsm8k_50`–`79`** (disjoint from the earlier **300-case** paired cohort starting near **`772`**).
- **PAL gap:** **17/30** vs **best external 24/30** (**−23.33 pp** vs best-of-three externals).
- **PAL wrong & ≥1 external correct:** **7** cases — **`54`, `55`, `57`, `58`, `63`, `67`, `70`**.
- **PAL beats all three externals:** **0 / 30**.
- **Offline PAL-path taxonomy (7-case subset):**
  - **`gold_absent_discovery`:** **3** — **`54`, `58`, `67`**
  - **`present_not_selected`:** **4** — **`55`, `57`, `63`, `70`**
- **Three-way externals are heterogeneous** (e.g. **`58`**: only `external_l1_max` hits gold; **`57`**: only `external_s1_budget_forcing`; **`70`**: only `external_tale_prompt_budgeting`).
- **Overlap with 48-case corpus IDs:** **none** for these seven (indices **`50–79`** vs corpus **`773+`** band).

---

## B. Combined failure-mode table (55 rows)

**Legend**

- **300-case failure corpus:** rows built from `failure_cases.csv` (PAL-vs-**`external_l1_max`** paired harness used for that study). **`ext_l1`** = whether that paired external baseline matched gold (**`1`/`0`**). **`ext_tale` / `ext_s1`:** **`n/a`** (not evaluated in that bundle).
- **30-case pilot:** **`ext_l1` / `ext_tale` / `ext_s1`** from `pal_loss_external_win_cases.csv` / `results.jsonl`.
- **`trce_note`:** qualitative applicability (see §D). Corpus rows reference the TRCE checklist generically; pilot rows use **`yes` / `partial`** from pilot tagging.

| source | case_id | overlap_w_other_set | outcome | failure_stage_or_pilot_type | ops_tags | cand_div | gold_location_summary | ext_l1 | ext_tale | ext_s1 | trce_note |
|--------|---------|---------------------|---------|------------------------------|----------|----------|-------------------------|--------|----------|--------|-----------|
| 300case_failure_corpus | `openai_gsm8k_773` | — | external_only | gold_absent_everywhere_detectable | temporal_change | 2 | absent_everywhere | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_778` | — | both_wrong | gold_absent_everywhere_detectable | rate_ratio | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_780` | — | both_wrong | gold_in_selector_pool | rate_ratio/percent/temporal_change | 2 | in_selector_pool | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_781` | — | both_wrong | gold_absent_everywhere_detectable | product | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_787` | — | external_only | gold_in_trace_candidates | total_sum/difference | 2 | in_trace | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_794` | — | both_wrong | gold_absent_everywhere_detectable | temporal_change | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_812` | — | both_wrong | gold_absent_everywhere_detectable | rate_ratio/temporal_change | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_814` | — | external_only | gold_absent_everywhere_detectable | rate_ratio/temporal_change | 2 | absent_everywhere | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_818` | — | external_only | gold_in_trace_candidates | rate_ratio/difference | 2 | in_trace | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_819` | — | both_wrong | gold_absent_everywhere_detectable | rate_ratio | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_820` | — | both_wrong | gold_in_trace_candidates | rate_ratio/difference | 2 | in_trace | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_829` | — | external_only | gold_absent_everywhere_detectable | none | 2 | absent_everywhere | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_832` | — | both_wrong | gold_absent_everywhere_detectable | none | 1 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_841` | — | external_only | gold_absent_everywhere_detectable | none | 2 | absent_everywhere | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_851` | — | external_only | gold_absent_everywhere_detectable | product/temporal_change | 3 | absent_everywhere | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_864` | — | external_only | gold_in_trace_candidates | none | 2 | in_trace | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_865` | — | both_wrong | gold_absent_everywhere_detectable | difference/product/division_share | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_875` | — | external_only | gold_absent_everywhere_detectable | none | 3 | absent_everywhere | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_878` | — | both_wrong | gold_absent_everywhere_detectable | rate_ratio | 3 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_897` | — | both_wrong | gold_absent_everywhere_detectable | rate_ratio | 1 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_898` | — | both_wrong | gold_absent_everywhere_detectable | temporal_change | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_905` | — | external_only | gold_in_selector_pool | total_sum/difference | 2 | in_selector_pool | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_906` | — | external_only | gold_absent_everywhere_detectable | total_sum | 2 | absent_everywhere | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_917` | — | both_wrong | gold_absent_everywhere_detectable | rate_ratio/product | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_929` | — | both_wrong | gold_absent_everywhere_detectable | rate_ratio/division_share/temporal_change | 1 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_931` | — | external_only | gold_in_trace_candidates | temporal_change | 2 | in_trace | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_934` | — | both_wrong | gold_absent_everywhere_detectable | rate_ratio/total_sum/temporal_change | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_944` | — | both_wrong | gold_absent_everywhere_detectable | rate_ratio | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_951` | — | both_wrong | gold_in_trace_candidates | product | 3 | in_trace | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_953` | — | both_wrong | gold_absent_everywhere_detectable | rate_ratio | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_970` | — | external_only | gold_in_trace_candidates | difference | 2 | in_trace | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_974` | — | both_wrong | gold_absent_everywhere_detectable | product | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_976` | — | both_wrong | gold_absent_everywhere_detectable | total_sum | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_979` | — | both_wrong | gold_absent_everywhere_detectable | rate_ratio | 1 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_984` | — | external_only | gold_in_selector_pool | rate_ratio | 2 | in_selector_pool | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_995` | — | external_only | gold_absent_everywhere_detectable | product/temporal_change | 2 | absent_everywhere | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_1003` | — | external_only | gold_absent_everywhere_detectable | product/temporal_change | 2 | absent_everywhere | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_1006` | — | external_only | gold_absent_everywhere_detectable | rate_ratio/total_sum | 3 | absent_everywhere | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_1013` | — | both_wrong | gold_in_trace_candidates | rate_ratio | 2 | in_trace | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_1019` | — | external_only | gold_in_trace_candidates | total_sum/difference | 2 | in_trace | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_1021` | — | both_wrong | gold_absent_everywhere_detectable | difference/temporal_change | 1 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_1025` | — | both_wrong | gold_absent_everywhere_detectable | rate_ratio/temporal_change | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_1027` | — | external_only | gold_absent_everywhere_detectable | rate_ratio | 2 | absent_everywhere | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_1029` | — | external_only | gold_absent_everywhere_detectable | temporal_change | 2 | absent_everywhere | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_1035` | — | both_wrong | gold_absent_everywhere_detectable | percent/difference/temporal_change | 3 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_1039` | — | both_wrong | gold_in_selector_pool | difference/temporal_change | 2 | in_selector_pool | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_1045` | — | external_only | gold_in_trace_candidates | none | 2 | in_trace | 1 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 300case_failure_corpus | `openai_gsm8k_1069` | — | both_wrong | gold_absent_everywhere_detectable | rate_ratio | 2 | absent_everywhere | 0 (paired ext) | n/a | n/a | see corpus TRCE checklist |
| 30case_4way_pilot | `openai_gsm8k_54` | no | PAL_loss_ext_win | gold_absent_discovery | temporal_change | — | see pilot analysis | 1 | 1 | 1 | yes |
| 30case_4way_pilot | `openai_gsm8k_55` | no | PAL_loss_ext_win | present_not_selected | — | — | see pilot analysis | 1 | 0 | 1 | partial |
| 30case_4way_pilot | `openai_gsm8k_57` | no | PAL_loss_ext_win | present_not_selected | — | — | see pilot analysis | 0 | 0 | 1 | partial |
| 30case_4way_pilot | `openai_gsm8k_58` | no | PAL_loss_ext_win | gold_absent_discovery | temporal_change | — | see pilot analysis | 1 | 0 | 0 | yes |
| 30case_4way_pilot | `openai_gsm8k_63` | no | PAL_loss_ext_win | present_not_selected | temporal_change | — | see pilot analysis | 1 | 0 | 1 | partial |
| 30case_4way_pilot | `openai_gsm8k_67` | no | PAL_loss_ext_win | gold_absent_discovery | temporal_change | — | see pilot analysis | 1 | 1 | 1 | yes |
| 30case_4way_pilot | `openai_gsm8k_70` | no | PAL_loss_ext_win | present_not_selected | — | — | see pilot analysis | 0 | 1 | 0 | partial |

---

## C. Discovery vs present-not-selected balance (quantified “mass”)

**C.1 — 48-case corpus (`failure_stage` facts)**

| Stage | Count | Share |
|-------|------:|------:|
| `gold_absent_everywhere_detectable` | 34 | **70.8%** |
| `gold_in_trace_candidates` | 10 | 20.8% |
| `gold_in_selector_pool` | 4 | 8.3% |

Interpretation for buckets **A–D** (approximate mapping):

- **A — discovery / gold-absent-everywhere:** **34 / 48** rows (**70.8%**).
- **B — gold visibly present before final selection (trace or selector pool):** **14 / 48** (**29.2%** = 10 + 4).
- **C — code / PAL execution / safety:** not atomically encoded in `failure_cases.csv`; the **300-case** taxonomy (`external_only_failure_summary.md`, `both_wrong_summary.md`) shows non-trivial **`code_absent_empty`**, **`blocked_or_exec_fail`**, etc., concentrated in the **300-case** study—not re-derived row-by-row here for all **48**.
- **D — unknown / mixed:** residual cases where stage labels under-determine PAL-side taxonomy without `failure_cases.jsonl` deep flags.

**C.2 — Seven pilot PAL-loss / external-win rows**

| Bucket | Count | Share of 7 |
|--------|------:|-----------:|
| **A′ — `gold_absent_discovery` (pilot PAL-path heuristic)** | **3** | **42.9%** |
| **B′ — `present_not_selected` (pilot PAL-path heuristic)** | **4** | **57.1%** |

**C.3 — 300-case PAL-side taxonomy (context only)**

- External-only losses (21 rows): **`gold_absent_discovery` dominates (15/21)**.
- Both-wrong (27 rows): **`gold_absent_discovery` (21/27)** with rare **`present_not_selected` (1/27)**.

**Synthesis:** The **48-case** distribution and **300-case** taxonomies emphasize **discovery/gold-absent** as the bulk phenomenon. The **30-case pilot’s PAL-loss slice** flips emphasis toward **commitment / selection** (**4/7**), because this slice was defined by **PAL vs external success**, not by mining gold-absent rows only. **Do not** treat **4/7** as a universal rate—it is **conditional on “externals rescued the item.”**

---

## D. TRCE applicability

**TRCE scope (from `selected_discovery_hypothesis_checklist.md` + `trce_offline_validation_report.md`):** temporal/rate-style **`external_only`** losses where gold is **absent from PAL-visible discovery**, addressed via a **bounded discovery lane** that avoids **selector-visible pool injection by default**.

**Fit:**

- **Strong:** Pilot **`54`, `58`, `67`** — **`gold_absent_discovery`** + **`temporal_change`** hints → align with TRCE **targets**.
- **Partial / orthogonal:** **`55`, `57`, `63`, `70`** — **`present_not_selected`** → primarily **track B** (commitment / tie-break / surfacing), **not** pure TRCE discovery expansion.

**Corpus consistency:** **34/48** rows are **`gold_absent_everywhere_detectable`** — consistent with TRCE’s primary narrative. **14/48** already show gold somewhere in PAL artifacts (**trace or selector pool**) — TRCE-style coverage expansion **alone** is an awkward fit; those rows resemble **selector-recovery** problems documented in gate-anchor regressions (`trce_offline_validation_report.md` §E).

**Verdict:** TRCE remains **valid as a hypothesis for a large fraction of aggregate failures**, but **insufficient as the only development thread** given **(i)** pilot PAL-loss evidence splitting **43% / 57%** between discovery vs commitment among externals-rescued cases, and **(ii)** **29%** of the **48-case** corpus already in **gold-visible** stages.

### D.1 Pilot gold-absent exemplars (`54`, `58`, `67`) — TRCE target candidates

| Case | TRCE profile | External structural clue | PAL path | Retry serialized (`pal_empty_code_retry`) |
|------|----------------|---------------------------|----------|-----|
| **54** | Strong — units / rotations / months→years | All three externals reach **`6`** | **`pal_seed`** commits **`34560000`**; **`6`** absent from final pool | **No** |
| **58** | Strong — epidemic recurrence | Only **`external_l1_max`** reaches **`3430`**; tale/s1 align with **`2160`** | PAL stuck on **`2160`** | **No** |
| **67** | Strong — multi-day itinerary sum | All externals reach **`3140`** | PAL **`2960`**; gold absent from pool | **No** |

**Notebook / ledger:** These IDs are **not** in the **48-case** TRCE ledger but are strong **candidate TRCE targets** once reproduced in the replay harness. Do **not** add to regression **`must_not_change`** lists until baselines are pinned.

---

## E. Present-not-selected audit findings (`55`, `57`, `63`, `70`)

Artifacts: **`results.jsonl`** PAL rows (`result_metadata_full`, `final_nodes`, `selector_candidate_pool`, tie-break flags).

| Case | Gold | PAL output | Where gold appears | Selected group / tie-break | Offline commit counterfactual |
|------|------|------------|--------------------|-----------------------------|------------------------------|
| **55** | `12` | `-28` | Multiple **`12`** entries in augmented **final_nodes**; selector pool = **`10`** (`direct_reserve_0`) vs **`-28`** (`pal_seed_0`). **`12`** not in the **two-member** pool. | **`selected_group = -28`**, **`frontier_tiebreak_triggered = False`** | Choosing **`direct_reserve_0`** (`10`) still misses gold **`12`**. No **oracle-free** one-line rule guarantees **`12`** without richer reasoning; failure mixes **unit modeling** and **candidate-set truncation**. |
| **57** | `1` | `2` | Augmented nodes include **`1`** and **`2`**; pool = **`3`** vs **`2`**. | **`selected_group = 2`**, **`frontier_tiebreak_triggered = True`** | Counterfactual **“pick `1` when present”** would hit gold **only if** that node were eligible to win—needs scorer/tie-break audit. |
| **63** | `200` | `1200` | Augmented nodes repeatedly include **`200`**; pool shows **`1200`** for **both** branches (**`direct_reserve_0`**, **`pal_seed_0`**). | **`selected_group = 1200`**, tie-break **False** | Both top-level candidates agree on the **wrong** final numeric—**gold appears deeper in the tree than the final pool**. Fixing requires **re-opening commitment** or **additional expansion**, not a trivial rank tweak on two identical finals. |
| **70** | `18` | `15` | Pool = **`18`** (`direct_reserve_0`, matches gold) vs **`15`** (`pal_seed_0`). | **`selected_group = 15`**, **`frontier_tiebreak_triggered = True`** | **Pure selector issue:** an offline rule **preferring `direct_reserve_0` when its numeric matches a high-confidence direct parse** would recover gold **without new LLM calls**—but that is a **policy change** (risky if over-generalized). |

**Relation to earlier selector issues:** Same family as **gate / exploration-log anchor regressions** (pool shape perturbs final commit) but here observed on **clean pilot defaults**—suggests **intrinsic coupling** between **`direct_reserve`** vs **`pal_seed`** competition, not only failed experiments.

**Selector-visible / risky?** Any change that **re-ranks** final answers or **alters tie-break** is **selector-visible by definition**. **Offline replay** can simulate policies **without** API calls; **shipping** a fix requires the **guardrails** in §G.

---

## F. Recommended priority order

1. **Adopt an explicit two-track plan:**
   - **Track A — TRCE:** discovery-coverage expansion for **`gold_absent`** / temporal-rate-shaped failures (aligned with checklist + offline TRCE report).
   - **Track B — Commitment audit:** offline replay & policy experiments for **`present_not_selected`**-typed failures (**pilot `55`–`70` subset + corpus `gold_in_*` stages**).

2. **Should TRCE remain the immediate first implementation target?**  
   **Yes for Track A execution** (the largest staged failure mass + pre-existing investment), **but not exclusively:** Track B must advance **in parallel at the specification / replay level**.

3. **Should present-not-selected audit precede TRCE coding?**  
   **Not strictly sequential.** Offline audit is **mandatory before any selector/tie-break code change**, but TRCE’s **design** (non-selector-visible diagnostics lane) can proceed **concurrently**.

4. **Can commitment issues be handled offline-only without selector-visible pools?**  
   **Diagnosis — yes** (replay traces). **Resolution — partial:** cases like **`70`** admit **deterministic counterfactuals**; **`63`** needs **new candidates**, which overlaps TRCE-like expansion but risks **pool coupling** unless isolated per **`trce_offline_validation_report.md`**.

5. **Would TRCE implemented naïvely worsen present-not-selected cases?**  
   **Yes** if implemented as **undisciplined pool injection**—historical gate experiments already regressed anchors. **Mitigation:** TRCE checklist guardrails + **zero regressions** with feature **off**.

---

## G. Guardrails before any implementation

From **`trce_offline_validation_report.md`** / checklist (summarized):

- **Default-off** feature flags; **no selector-visible injection** in diagnostic-only modes.
- **Separate budget lane** for discovery expansion; **no normal-path budget theft** for logging.
- **Frozen anchor suites** (`rate_ratio` gate, conservative gate, isolated exploration-log anchors) — **prediction unchanged** when TRCE disabled.
- **Hard stops:** `prediction_changed_count > 0` with TRCE off → fail; **no unexplained action-budget deltas** on baseline replay.

Add **pilot-specific commitments:**

- Treat **`70`**-style failures as **tie-break regression tests** if tie-break logic changes.
- Treat **`63`** as a **warning** that **final-node agreement** can mask **correct intermediate answers** deeper in the tree.

---

## H. Whether API is needed now

**No.** Remaining work is **offline replay specification**, **policy simulation**, and **anchor bookkeeping**—consistent with **`API is not needed now`** in the TRCE report.

---

## I. Exact next action

Produce a **single offline replay checklist** (artifact-only) that, for each ID in **`gold_in_trace_candidates` ∪ `gold_in_selector_pool` ∪ {pilot **`55`,`57`,`63`,`70`**}**, records: **branch IDs**, **final pool snapshot**, **`selected_group`**, **tie-break flags**, and **counterfactual eligibility** of gold—**without** modifying source code. Then reconcile outputs with TRCE **Track A** design doc before any implementation ticket.

---

### Answers to priority-order prompts (task 3)

| Question | Answer |
|----------|--------|
| TRCE alone as next target? | **No — use two tracks.** |
| Present-not-selected audit before TRCE? | **Parallel offline audit before any selector change; TRCE design can proceed in parallel.** |
| Offline-only fix for commitment without pool touch? | **Diagnose yes; fix partially — policy/ranking changes are selector-touching.** |
| TRCE-first risk to commitment cases? | **Yes if naive pool injection — guardrails required.** |
| Guardrails? | **§G / TRCE offline report + pilot regression tests.** |

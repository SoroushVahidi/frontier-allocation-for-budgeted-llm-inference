# Failure-pattern mining report: 45-case corpus vs prior evidence

Offline analysis only — no API calls, no source edits, no new methods.

**Inputs:** `manifest.json`, `failure_collection_summary.json`, `case_overlap_report.json`, `all_results.jsonl`, `all_casebook.csv`, `selected_failure_cases.jsonl`, `per_example_records.jsonl` (PAL traces), plus prior bundles under `outputs/failure_case_corpus_20260507/`, `outputs/cohere_pal_retry_vs_3_external_baselines_30case_20260507T152735Z/`, `outputs/pal_retry_300case_analysis_20260506/`.

---

## 1. Collection validation

| Check | Value |
|--------|--------|
| IDs touched (evaluated index band) | **247** (`openai_gsm8k_1072` … `1318`) |
| Complete **4-way scored** cases | **245** |
| Incomplete cases | **`openai_gsm8k_1101`**, **`openai_gsm8k_1102`** — `external_l1_max` rows **`failed`** with **Cohere read timeout** (`RuntimeError: … timed out`). PAL, TALE, S1 scored for those IDs. |
| Logical calls (sum `cohere_logical_api_calls`) | **1893** / cap **3000** (`cap_respected`: yes) |
| Preferred failures (PAL wrong ∧ ≥1 external correct), pool | **34** |
| Secondary failures (PAL wrong ∧ all externals wrong), pool | **23** |
| Selected corpus | **45** = **34 preferred + 11 secondary** |
| Overlap prior **300-case** band (772–1071) | **none** (`case_overlap_report.json`) |
| Overlap **30-case** pilot (50–79) | **none** |
| Overlap **48-case** corpus | **none** |
| Selected rows include **method_records** for PAL + 3 externals | **yes** (`selected_failure_cases.jsonl`) |
| Preferred satisfy PAL wrong ∧ ≥1 external correct | **yes** (validated on `exact_match`) |
| Secondary satisfy PAL wrong ∧ all externals wrong | **yes** |

---

## 2. Metrics recomputation vs `failure_collection_summary.json`

Recomputed from `all_results.jsonl` on cases where all four methods have `scored=1` (**n = 245**).

### PAL vs best external (complete 4-way)

| Bucket | Count |
|--------|------:|
| both_correct | 183 |
| external_only | **34** |
| pal_only | 5 |
| both_wrong | 23 |

**Discrepancy check:** Matches `failure_collection_summary.json` → `pal_vs_best_external_counts` exactly.

### Pairwise PAL vs each external (n = 245)

| vs | both_correct | pal_only | external_only | both_wrong |
|----|-------------:|---------:|--------------:|-----------:|
| `external_l1_max` | 159 | 29 | **23** | 34 |
| `external_tale_prompt_budgeting` | 149 | 39 | **24** | 33 |
| `external_s1_budget_forcing` | 158 | 30 | **24** | 33 |

### Per-method accuracy (scored rows)

Method row counts: PAL **247**, each external **247** rows in JSONL; **`external_l1_max`** has **2** failed rows → accuracy denominators **247 / 247 / 247 / 247** for PAL/TALE/S1 and **245** scored L1 rows if failures excluded — **Summary file uses:** PAL 247, L1 **245**, TALE 247, S1 247. Recomputed accuracies match summary within rounding.

**Note:** Any analysis restricted to “complete 4-way” should use **245** cases for joint contingency tables; per-method marginals may still use 247 when including partial slices.

---

## 3. Deep mine — **34 preferred** failures

### 3.1 Failure-type taxonomy (PAL row: `failure_tag`, `gold_in_tree`)

Classification rule (aligned with pilot doc):

- **`present_not_selected`:** `gold_in_tree == 1` **or** `failure_tag` indicates correct answer present but not selected.
- **`gold_absent_discovery`:** `gold_in_tree == 0` **or** tag “absent from explored tree”.
- **`parse_surfacing`:** `parse_extraction_failure == 1` (none observed in preferred set).

| Failure type | Count (of 34) | Share |
|----------------|---------------:|-------|
| **present_not_selected** | **23** | **68%** |
| **gold_absent_discovery** | **11** | **32%** |

**Distribution vs pilot 7 PAL-loss/external-win cases:** Pilot split was **3 gold_absent / 4 present_not_selected** (~43% / ~57%). On the **34 preferred** slice here, **gold_absent is a smaller fraction** and **present_not_selected is the clear majority**.

### 3.2 PAL `failure_tag` strings (preferred)

- **`correct answer present but not selected`:** 23 cases (matches present_not_selected).
- **`correct answer absent from explored tree`:** 11 cases (matches gold_absent_discovery).

No preferred rows used `parse_extraction_failure` as primary signal; PAL execution traces are populated (`direct_reserve_attempts` present; multi-step expand traces common).

### 3.3 Which externals won?

Among **34** preferred failures:

| # externals correct | Count |
|--------------------|------:|
| 3 (all) | 13 |
| 2 | 11 |
| 1 | 10 |

**Heterogeneity remains high** — consistent with the 30-case pilot note that baselines are not interchangeable.

Top combination patterns (short names): all-three wins (13 rows); L1+S1 without tale (4); tale+S1 without L1 (4); tale-only (4); L1+tale (3); S1-only (3); L1-only (3).

### 3.4 Operation tags (from `all_casebook.csv` heuristics)

Among **34** preferred:

| Tag (subset) | Count |
|----------------|------:|
| **temporal_change** | 12 |
| **rate_ratio** | 6 |
| **difference** | 3 |
| (empty / none) | several |

Compared to **48-case corpus** `feature_summary.json` top hints (**rate_ratio** 21, **temporal_change** 17): the **same qualitative families** appear, but **rate_ratio is less dominant** on this high-index slice — still compatible with “multi-step story problems,” not a brand-new tag vocabulary.

### 3.5 Gold presence / commitment lens

- **23 / 34** have evaluator **`gold_in_tree == 1`** → commitment / selector / surfacing stress tests dominate **preferred** external-win failures.
- **11 / 34** have **`gold_in_tree == 0`** → discovery / coverage expansion (TRCE-shaped) remains material but **not majority** among **external-win** failures.

### 3.6 PAL execution / retry / tie-break

- **`frontier_tiebreak_triggered`:** mixed True/False across preferred rows — tie-break fires on some present-not-selected cases but is **not sufficient** for correctness.
- **`pal_retry_nonempty`:** sparse in cluster summary; retry is **not** the dominant visible lever in this JSON dump (consistent with pilot: retry often empty).
- **PAL traces:** `direct_reserve_attempts` consistently show structured expand steps — failures are **not** dominated by “no code emitted” in this slice.

---

## 4. Eleven **secondary** (PAL wrong, all externals wrong)

### 4.1 Failure-type split

| Type | Count |
|------|------:|
| **gold_absent_discovery** | **10** |
| **present_not_selected** | **1** |

Secondary set is **deliberately** “rich trace” padded from the **all-wrong** pool — it **over-represents discovery absence** vs preferred.

### 4.2 Contrast value

- **Shared modes:** Most secondaries are **gold absent** — same **discovery** bottleneck as **11** preferred gold-absent rows, but **externals also fail**, so they isolate **hard decomposition** without confounding “external got lucky.”
- **Usefulness:** Strong for **stress-testing discovery** and **calibrating when TRCE-style expansion would help everyone** vs when **all models collapse**.
- **Weaknesses not visible in external-win cases:** **Hard negative** cases where **no** baseline solves — important for ** ceiling analysis** and **dataset error / ambiguity** review.

---

## 5. Comparison to prior corpora

### 5.1 48-case corpus (`failure_case_corpus_20260507`)

- **Membership overlap:** **0** IDs ( disjoint bands by construction ).
- **Outcome motif:** Corpus emphasized **`external_only`** (21) + **`gold_absent_everywhere_detectable`** (34 of 48 rows per feature summary) — **discovery-stage** language.
- **New 45 preferred:** **68% present-not-selected** among **external-win** failures → shifts emphasis toward **commitment** vs corpus’s heavier **gold-absent** staging counts (corpus mixes staging labels; not 1:1 with our binary).

**Interpretation:** Narratives are **compatible**: corpus catalogued **where** gold sits (trace vs pool); new slice shows that when externals **win**, PAL often **already had gold in-tree** — **selector/commitment** may have been **under-weighted** in headline corpus counts.

### 5.2 30-case pilot — 7 PAL-loss / external-win

Pilot split: **3 gold_absent_discovery / 4 present_not_selected**.

**New 34 preferred:** **11 / 23** gold_absent / present_not_selected — **gold_absent share drops**, **present_not_selected share rises** vs pilot seven.

**Verdict:** Pilot **under-sampled** present-not-selected among external-win rows (small n); **new evidence strengthens Track B** relative to pilot’s TRCE-heavy split.

### 5.3 300-case analysis (`external_only_failure_summary.md`)

Reported external-only taxonomy (PAL-side heuristic): **gold_absent_discovery 15**, **code_absent_empty 3**, etc., **n=21**.

Our **preferred** taxonomy differs (no empty-code bucket surfaced in the 34) — consistent with **PAL+retry front producing traces**; **selection** dominates now.

---

## 6. Cluster summaries

See **`failure_cluster_summary.csv`** — one row per selected case with: tier, failure_type, correctness triple, winner pattern, tags, `gold_in_tree`, tie-break, retry flag, richness proxy.

**Clusters:**

- **By failure type:** present_not_selected **23+1** (preferred+secondary) vs gold_absent_discovery **11+10**.
- **By external pattern:** 3-way wins vs 1–2 externals (heterogeneity documented above).
- **By tags:** temporal_change > rate_ratio > difference (sparse tags ≠ easy problems).

---

## 7. TRCE vs present-not-selected vs “new track”

### TRCE (Track A — temporal/rate coverage expansion)

- **Strength:** Still explains **11 / 34 preferred** + bulk of **secondary gold-absent** rows — **discovery** remains real.
- **Narrowing:** Among **PAL wrong ∧ external correct**, **only ~32%** are gold-absent vs **~68%** present-not-selected → TRCE is **narrower as a universal explanation** for **external-win** failures than a naive reading of the 48-case corpus suggested.
- **Verdict:** **Not weakened** as a **partial** lever — **narrowed** in scope for **external-win** cases.

### Present-not-selected / replay (Track B)

- **Strengthened:** **23 / 34 preferred** — **primary** bottleneck for “externals beat PAL.”
- **Verdict:** Should be **at least equal priority** to TRCE for implementation sequencing on **this failure mode**; pilot already argued pairing — new data **raises Track B**.

### New Track C?

- **Integration under heterogeneity:** Many rows have **only one external** correct → interventions must avoid **assuming** “external monolith.”
- **Optional Track C:** **“heterogeneous external consensus”** diagnostics + **tie-break / overlay** audits when **`gold_in_tree==1`** — not necessarily a new algorithm here, but a **distinct evaluation axis**.

---

## 8. More API collection?

- **Not required** for the conclusions above — artifacts are sufficient.
- **Optional:** Retry **`external_l1_max`** for **1101/1102** (timeouts) to restore **full 4-way** rows; **extend ID range** beyond `1318` if more **preferred** rows are needed.

---

## 9. Exact next offline actions (before code changes)

1. **Replay selector sensitivity** on the **23** present-not-selected preferred IDs (reuse corpus replay pipeline where applicable).
2. **Align staging labels** with 48-case corpus (`gold_in_trace` vs pool) for the **34** IDs — harmonize terminology across reports.
3. **Freeze a “Track B shortlist”** (10–15 IDs) from **`top_manual_inspection_cases.md`** for design reviews.
4. **Only then** prototype: **selector-safe** replay vs **TRCE expansion** — **separate experiments**, pre-registered buckets.

---

## 10. Outputs

| File | Role |
|------|------|
| `failure_cluster_summary.csv` | Per-case cluster features |
| `failure_pattern_mining_report.md` | This document |
| `top_manual_inspection_cases.md` | Ranked manual inspection queue |

---

## Caveats

- Tags are **heuristic** on question text; staging labels come from **evaluator/harness** — neither is semantic ground truth.
- **n=34** preferred failures — descriptive statistics only.
- **Three externals disagree often** — aggregate “external” behavior is **not** one method.

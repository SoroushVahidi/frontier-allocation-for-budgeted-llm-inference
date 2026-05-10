# Pilot failure-pattern analysis: 30-case 4-way Cohere run vs 48-case corpus

Offline analysis only (no API calls, no code changes). Slice: `openai_gsm8k_50`–`openai_gsm8k_79`, disjoint from the earlier 300-case PAL+retry paired run (`overlap_with_300_case_run_count = 0` in `manifest.json`).

---

## A. Pilot validation summary

### Artifact checks

| Check | Result |
|-------|--------|
| Methods present in `results.jsonl` | **4** — `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`, `external_l1_max`, `external_tale_prompt_budgeting`, `external_s1_budget_forcing` |
| Rows per method | **30** each |
| Total scored rows | **120** (= 30 × 4) |
| Row `status` field | **120 × `scored`** (no failed/skipped rows in `results.jsonl`) |
| `raw/failures.jsonl` | **Empty / absent failures** (no API/runtime failures recorded) |
| Logical Cohere calls (sum of `cohere_logical_api_calls`) | **224** (hard cap **900** in `call_plan.json`; actual matches recomputation) |
| Case IDs | Exactly **30** IDs listed in `manifest.json` (`openai_gsm8k_50` … `79`) |
| Overlap with 300-case run | **0** (manifest + disjoint index range vs `772+` block) |
| Key outputs present | `manifest.json`, `call_plan.json`, `results.jsonl`, `paired_casebook.csv`, `method_summary.csv`, `pairwise_summary.json`, `case_matrix.md`, `failure_notes.md`, `report.md`, `per_example_records.jsonl`, `live_run.log`, `allowed_example_ids.jsonl` |

### Minor notes

- `incomplete_slices.csv` is effectively empty beyond headers because every slice reached its target (`slice_summary.csv`: `incomplete_reason = target_reached` for all four methods).
- Harness artifacts such as `pairwise_comparisons.csv` / `claim_safety_table.csv` still reference legacy strict-frontier comparisons and are **not** used for this pilot’s metrics.

---

## B. Recomputed 4-way accuracy and pairwise metrics

Recomputed from `paired_casebook.csv` / `results.jsonl`. **No discrepancies** vs `pairwise_summary.json` on integer contingencies, summed discordants, or accuracy gaps (floating-point pp matches within numerical tolerance).

### Per-method accuracy (n = 30)

| Method | Correct | Accuracy |
|--------|---------|----------|
| PAL (`…frontier_tiebreak_pal`) | 17 | **56.67%** |
| `external_l1_max` | 21 | **70.00%** |
| `external_tale_prompt_budgeting` | 20 | **66.67%** |
| `external_s1_budget_forcing` | 20 | **66.67%** |

### PAL vs each external (pairwise rows)

| Comparison | both_correct | pal_only | external_only | both_wrong | Σ(pal−ext) | Δ accuracy (PAL−ext, pp) |
|------------|--------------|----------|---------------|------------|------------|----------------------------|
| vs `external_l1_max` | 16 | 1 | 5 | 8 | −4 | **−13.33** |
| vs `external_tale_prompt_budgeting` | 17 | 0 | 3 | 10 | −3 | **−10.00** |
| vs `external_s1_budget_forcing` | 15 | 2 | 5 | 8 | −3 | **−10.00** |

### PAL vs **best** external (preference order in paired_casebook: `l1` → `tale` → `s1`)

| Metric | Count / value |
|--------|----------------|
| PAL correct | 17 |
| Best external correct | 24 |
| both_correct | 17 |
| pal_only | 0 |
| external_only | 7 |
| both_wrong | 6 |
| Σ(pal − best_external) | −7 |
| Δ accuracy (pp) | **−23.33** |

### Case lists (from recomputation)

- **PAL lost to ≥1 external while PAL wrong:** **7** cases — `openai_gsm8k_54`, `55`, `57`, `58`, `63`, `67`, `70`.
- **PAL beat all three externals:** **0** cases.
- **All four methods wrong:** **6** cases — `openai_gsm8k_51`, `61`, `62`, `71`, `73`, `77` (none overlap the 7 PAL-loss/external-win list).

---

## C. The seven PAL-loss / external-win cases

Offline taxonomy uses PAL rows in `results.jsonl`:

- **`gold_absent_discovery`:** canonical gold answer **not** found on augmented PAL `final_nodes` / `selector_candidate_pool` (same normalization pipeline as the paired PAL bundle materializer).
- **`present_not_selected`:** gold **does** appear among PAL candidates/pool metadata, but the surfaced prediction disagrees with gold (selector / tie-break / integration path).

PAL-side hooks observed across these rows: **parse/exec OK** on recorded PAL paths; **`pal_retry`** sidecar often empty in `results.jsonl` (retry did not trigger or not serialized here); **frontier tie-break** toggled **True** on **54, 57, 70** and **False** on others—tie-break presence alone does not imply correctness.

| ID | PAL outcome | Likely failure type | External winners | TRCE lens |
|----|-------------|---------------------|--------------------|-----------|
| **54** | Wild numeric (`34560000`) vs gold `6` | **gold_absent_discovery** | All three | Strong — multi-hop rate/units chain (`temporal_change` tag in paired_casebook heuristics). |
| **55** | Negative gallons `-28` vs gold `12` | **present_not_selected** | `external_l1_max`, `external_s1_budget_forcing` | Weak for pure TRCE — wrong branch promoted despite candidate signals; unit/wording heavy. |
| **57** | `2` vs gold `1` | **present_not_selected** | `external_s1_budget_forcing` only | Weak — packing / ceiling semantics; **heterogeneous** externals (only S1 hits gold). |
| **58** | `2160` vs gold `3430` | **gold_absent_discovery** | **`external_l1_max` only** | Mixed — temporal epidemic interpretation; **tale** and **s1** also fail here (externals disagree). |
| **63** | `1200` vs gold `200` | **present_not_selected** | `external_l1_max`, `external_s1_budget_forcing` | Weak — relational “3× farther” mis-modeled; gold reachable in pool heuristic but wrong answer chosen. |
| **67** | `2960` vs gold `3140` | **gold_absent_discovery** | All three | Strong — multi-segment itinerary sum (`temporal_change`). |
| **70** | `15` vs gold `18` | **present_not_selected** | **`external_tale_prompt_budgeting` only** | Weak — staged fraction word problem; tie-break **True** but wrong group; **heterogeneous** externals. |

**Split:** **3 / 7** classified as **`gold_absent_discovery`** (54, 58, 67); **4 / 7** as **`present_not_selected`** (55, 57, 63, 70).

---

## D. Comparison to the existing 48-case failure corpus

- **Membership:** None of these seven IDs appear in `failure_cases.csv` / `failure_cases.jsonl` (corpus built from other GSM8K selections—typically higher indices such as the `772+` paired cohort). **`overlaps_48_case_corpus = no`** for all seven.
- **Outcome alignment:** All seven match the **qualitative** “external succeeds where PAL fails” motif behind **`external_only`** rows in the corpus, but this pilot **does not** label gold-absence stages (`gold_in_trace`, etc.) using the full corpus pipeline—only offline PAL-tree checks above.
- **Operation hints:** Several cases carry **`temporal_change`** (54, 58, 63, 67) under the pilot’s lightweight tag heuristic—consistent with the corpus emphasis on temporal/rate surfaces. Others have **empty** tags (55, 57, 70), closer to the corpus **`none`** / weak-tag bucket (`829`, `841`, … in TRCE report).

---

## E. Relationship to the TRCE hypothesis

**TRCE** (Temporal-Rate Coverage Expansion) posits **discovery-coverage** gaps—especially gold-absent failures with temporal/rate structure—where externals find a successful decomposition PAL never materializes.

### Fit

- **Supporting:** Cases **54**, **58**, **67** are **`gold_absent_discovery`** with temporal/epidemic/itinerary structure—exactly the narrative TRCE targets.
- **Non-supporting / orthogonal:** Cases **55**, **57**, **63**, **70** are **`present_not_selected`**—gold appears (under offline checks) yet PAL commits elsewhere. TRCE’s **stated guardrails** explicitly avoid selector-visible pool churn; these failures point toward **selection / tie-break / surfacing** rather than discovery-only expansion.

### Verdict on TRCE strength

- **Unchanged to slightly weakened as a single universal fix:** nearly **half** (4/7) of the pilot’s PAL-loss/external-win rows are **not** pure gold-absent discovery failures—TRCE-shaped interventions risk **missing** the dominant error mode on **this** slice unless paired with selector-safe fixes.
- **Still coherent as a partial hypothesis:** **3/7** rows remain strong TRCE exemplars; they sit in a **fresh** index band, showing the phenomenon is **not** an artifact of the original 48-case ID selection alone.

---

## F. Does this slice imply a different bottleneck?

Yes—**mixed**:

1. **Discovery / structured decomposition** (54, 58, 67): externals assemble long chains or recurrence correctly; PAL’s frontier lacks the gold grouping.
2. **Selection / integration** (55, 63, 70, partially 57): PAL produces plausible intermediate numerics but **commits** to the wrong branch despite offline evidence that the gold grouping existed somewhere in candidate artifacts.
3. **Baseline heterogeneity:** Case **58** shows **`external_l1_max` uniquely correct** while tale and s1 match PAL’s wrong answer—so “external” is **not** monolithic; failures are not explained by a single external recipe.

---

## G. What should **not** be concluded

- **No statistical superiority:** \(n = 30\), contiguous low indices—variance is huge.
- **No universal ranking of external baselines:** methods swap wins case-by-case (e.g., only tale wins on **70**; only s1 wins on **57**).
- **No proof that PAL “never” beats externals:** this slice produced **zero** PAL-only wins vs best-external, but other slices may differ.
- **Gold-in-pool heuristic can misfire** on edge parses; classifications should be treated as **offline guidance**, not ground truth semantics.

---

## H. Recommended next actions (offline-first)

1. **Merge these seven IDs into optional corpus annotations** (failure-pattern tags only)—still **no** implementation.
2. **Segment experiments / hypotheses:** keep TRCE focused on **gold_absent_discovery** rows; track **present_not_selected** under a separate selector-integration workstream.
3. **If another pilot is run:** stratify IDs across GSM8K index ranges and pre-register outcome buckets—still **no API** until hypotheses are narrower.

**API needed now:** **No** — analysis is complete on stored artifacts.

---

## Companion table

Machine-readable row dump: `pal_loss_external_win_cases.csv` (same directory).

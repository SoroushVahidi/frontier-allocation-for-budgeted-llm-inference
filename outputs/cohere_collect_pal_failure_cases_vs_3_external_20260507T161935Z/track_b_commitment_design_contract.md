# Track B commitment layer — pre-implementation design contract

**Bundle:** `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z`  
**PAL method under study:** `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`  
**Status:** Specification and fixtures only — **no runtime implementation** in this step.

**API status:** No API calls are needed now; this design must pass offline replay and guardrail checks before any capped Cohere pilot.

---

## A. Problem statement

PAL failures labeled **`present_not_selected`** show **gold-aligned evidence in PAL-side artifacts** (tree, pool, overlay metadata, or histograms), yet the **surfaced final numeric answer** commits elsewhere. Offline replay across **23** preferred cases indicates failures concentrate in **commitment**: overlay vs PAL stdout, frontier tie-break vs DR peer, and histogram construction—not solely PAL codegen absence.

---

## B. Evidence summary (23 preferred `present_not_selected` cases)

| Dimension | Result |
|-----------|--------|
| Inventory | `openai_gsm8k_1082`, `1083`, `1085`, `1087`, `1095`, `1097`, `1116`, `1120`, `1121`, `1122`, `1124`, `1150`, `1175`, `1205`, `1210`, `1214`, `1279`, `1290`, `1291`, `1299`, `1303`, `1307`, `1314` |
| Replay feasibility | **23 / 23** `replay_ready` |
| Dominant mechanism (offline tag) | **`overlay_previous_equals_gold_but_surface_used_bad_pal_stdout`**: **16 / 23** |
| Frontier tie-break vs gold / DR | **`frontier_tiebreak_selected_peer_not_gold_while_gold_in_pool`**: **3 / 23** |
| Histogram / pool quirks | Skew (e.g. **`1083`**), grouping gap (**`1085`**, **`1095`**), triple ties (**`1279`**, **`1291`**, **`1307`**) |
| Gold literally in normalized selector pool | **8 / 23** (limits pool-only oracle ceilings) |

Source tables: `present_not_selected_replay_table.csv`, `present_not_selected_replay_report.md`.

---

## C. Why naive `max_answer_group_support` is unsafe as a global rule

From `counterfactual_policy_summary.csv` on the GSM8K band **`openai_gsm8k_1072`–`1318`**:

- **Fixes 16 / 23** target failures **offline**, but would flip **39** rows where PAL and best-external are **already both correct** (“guardrail” regressions).
- Histogram mass can be **wrong yet duplicated** (`1083`: wrong numeric earns multiple votes) or **omit gold buckets** (`1095`), so global argmax-support amplifies bad mass.

**Conclusion:** Max-support may appear on offline scorer graphs but is **not** an acceptable unconditional production rule.

---

## D. Why DR-heavy rules are unsafe

`direct_reserve_answer`, `pool_max_branch_score`, and `guarded_direct_reserve` each flip **112–113** guardrail rows on the same cohort—surfaced PAL already equals gold but DR-scoped predictions disagree.

**Conclusion:** Any policy that **defaults to DR / branch-score max without gates** risks mass regressions.

---

## E. Why PAL-executable priority alone does not help

`prefer_strong_pal_executable` fixes **0 / 23** on this slice (PAL stdout often **restates the wrong surfaced numeric**, e.g. **`1087`** executable stdout **`−66`** vs gold **`6`**).

**Conclusion:** Strong PAL execution is **not** a sufficient commitment fix; it must be **subordinate** to overlay / tie-break / pool consistency when those channels conflict.

---

## F. Recommended Track B hypothesis (narrow, pre-registered)

**Primary (dominant 16-row pattern):** **Overlay / commitment / surfacing consistency** — when `pal_overlay` and related metadata identify a **prior or peer answer** that is **not** the same as executable PAL stdout, the runtime must use a **gated contract** (e.g. “do not let PAL stdout become `final_answer` without passing explicit consistency checks with overlay / tie-break / pool registration”) *definition to be refined in implementation*.

**Secondary (3-row + tie residuals):** **Frontier tie-break and DR-pool reconciliation** on **support ties** — when `frontier_tiebreak_triggered` and the **DR pool** and **PAL peer** disagree, commit using **non-gold** signals (pool membership, family, margins, deduped histograms) in a **pre-registered family** of offline-replayed rules.

**Tertiary (histogram family, not a single switch):** **Histogram repair** (deduplication, numeric normalization, missing buckets) as **separate gated policies** — must be proven on skew cases (`1083`, `1085`, `1095`) **without** turning on global max-support.

This is a **family of candidate policies** to stress-test **offline**; it is **not** a single implemented selector in this document.

---

## G. Runtime signals **allowed** (non-gold)

- `result_metadata.pal_overlay` (applied flag, previous answer, selection reasons, conflict flags).
- `result_metadata.frontier_tiebreak_*`, `selected_group`, selector histograms (`answer_group_support_counts`, `direct_answer_group_counts`, `frontier_answer_group_counts`).
- `selector_candidate_pool` entries: `normalized_answer`, `source_family`, `branch_score`, `is_original_selected`, `cost_norm` (as already logged).
- `pal_execution` **structural** fields: parse/exec ok, `pal_candidate_is_strong`, **disagreement** between `pal_json_answer` and `pal_execution_result` stdout (for **consistency checks**, not “pick stdout because strong”).
- Action / budget / guard flags already in metadata (e.g. `guarded_*`, `finalguard_*` when present).

---

## H. Runtime signals **forbidden** (as decision rules)

- **Gold label, reference answer, or any oracle** from the dataset at inference.
- “If gold in tree, select gold” (mining tag is **diagnostic** only).
- Unconditional **global** `argmax(histogram support)`.
- Unconditional **DR / max branch_score** finalization.
- Unconditional **PAL stdout wins** when it conflicts with overlay / tie-break contract under study.

---

## I. Candidate policy family to test **offline** (before any code)

1. **Overlay-consistency gate:** If overlay applied, final surface must satisfy explicit consistency with overlay previous / selection reason (exact definition TBD; must be replayed on fixtures **`1087`**, **`1082`**, **`1279`**).
2. **Tie-break / DR reconciliation:** On `frontier_tiebreak_triggered` with **tied** histogram mass, prefer policies that use **pool structure** (e.g. DR vs pal_seed) with **regression bounds** — replay anchor **`1124`**.
3. **Histogram repair variants:** Deduplication / bucket completion — replay **`1083`**, **`1085`**, **`1095`**; each variant measured against **guardrail cohort**, not only the 23 failures.

---

## J. Target cases (fixture anchors)

Compact fixtures: `tests/fixtures/present_not_selected_replay/*.json`

| Case ID | Focus |
|---------|--------|
| `openai_gsm8k_1083` | Duplicate histogram inflation |
| `openai_gsm8k_1085` | Histogram omits gold bucket; PAL retry |
| `openai_gsm8k_1095` | Tie-break / grouping vs gold in pool |
| `openai_gsm8k_1124` | Tie-break PAL peer vs DR gold |
| `openai_gsm8k_1087` | Overlay vs PAL stdout surface |
| `openai_gsm8k_1279` | Triple tie; overlay prior vs surface |

---

## K. Guardrail cases (cohorts — not necessarily JSON fixtures)

- **Both correct:** **183** rows in band (`pal_correct` and `best_external_correct` in `all_casebook.csv` slice) — any candidate rule must report flip count ≤ agreed budget (see §L).
- **PAL-only correct:** **5** rows — stricter penalty on regressions.
- Optional future: attach IDs from prior selector-isolated / rate-ratio harmed runs when directories are available (**N/A** in current bundle).

---

## L. Required offline pass criteria before implementation

1. For each candidate policy variant: report **fixes among 23**, **still wrong**, **N/A**, **guardrail flips** (both-correct and PAL-only), same methodology as `counterfactual_policy_summary.csv`.
2. **No** production-bound rule until **regression budget** is specified (e.g. max additional flips on both-correct cohort vs baseline surfaced PAL).
3. Fixture replay must stay **bit-for-bit** consistent with archived `per_example_records.jsonl` summaries encoded in fixtures.

---

## M. Required unit / regression tests before implementation

- Schema tests (this deliverable): `tests/test_present_not_selected_replay_fixtures.py`.
- Future (implementation phase): unit tests for **histogram aggregation**, **tie-break ordering**, and **overlay vs final surface** using these fixtures as golden metadata summaries — **not** using gold as a runtime branch.

---

## N. Required small capped Cohere pilot (after offline pass only)

- One **budget-capped** rerun of the cost-normalized validation harness with **one** flagged change at a time.
- Compare **present-not-selected yield**, **overall accuracy**, and **guardrail flips** vs this baseline bundle.

---

## O. Stop conditions

- Guardrail flips exceed agreed threshold **before** target failures move materially.
- Offline replay shows **no** separation between variants (all behave like baseline on anchors).
- Overlay / tie-break metadata proves **unstable** across seeds (requires broader study—not immediate implementation).

---

### Related artifacts

- This contract (copy path): `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/track_b_commitment_design_contract.md`
- Fixtures: `tests/fixtures/present_not_selected_replay/`
- Manifest: `tests/fixtures/present_not_selected_replay/manifest.json`

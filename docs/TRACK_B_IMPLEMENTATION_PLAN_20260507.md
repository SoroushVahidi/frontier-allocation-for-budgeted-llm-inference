# Track B implementation plan — narrow commitment/present-not-selected (2026-05-07)

**Status:** Implementation plan plus initial opt-in gate/evaluator-fix implementation; live causal benefit not yet established. Cached/offline A/B still required before another paid pilot.  
**Worktree:** `research-next-wt`  
**PAL headline method:** `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`

---

## A. Track B hypothesis restatement

### Recommended hypothesis (from design contract)

**Primary (dominant offline mechanism — ~16 / 23 cases tagged `overlay_previous_equals_gold_but_surface_used_bad_pal_stdout`):**  
**Overlay / commitment / surfacing consistency.** When `pal_overlay` and related metadata indicate a **prior or peer numeric** that **conflicts** with **executable PAL stdout** (or with the group chosen after tie-break), the runtime must apply a **narrow, gated contract** — *not* “PAL strong ⇒ final”, *not* global histogram argmax, *not* blind DR finalization.

**Secondary (~3 / 23):** Frontier tie-break vs DR/pool reconciliation when **`frontier_tiebreak_triggered`** and peers disagree (fixture anchors include **`1124`**).

**Tertiary:** Histogram construction / dedup / normalization (**1083**, **1085**, **1095**) — **separate**, gated policies; **no** unconditional global `max_answer_group_support`.

### Offline evidence constraints (must inform implementation)

- Naive **`max_answer_group_support`** fixes **16 / 23** present-not-selected targets **offline** but causes **~39** regressions on **both-correct** guardrail rows (band cohort) — **must not ship as global rule**.
- **DR-heavy** finals (**~112–113** guardrail flips) — **unsafe** as defaults.
- **`prefer_strong_pal_executable`**-style “stdout wins” fixes **0 / 23** on this slice — PAL stdout can be confidently wrong (**1087**: stdout vs overlay-aligned channel).

---

## B. Runtime code path map

### Where final numeric commitment happens today

For the diverse-root guarded PAL stack, the critical ordering is in **`DirectReserveFrontierGateController.run`** (`experiments/controllers.py`, roughly **after** merging direct-reserve and frontier outcomes):

1. **Direct reserve vs frontier merge** sets an incumbent/frontier **`final_answer`** from DR attempts + frontier subtree (`final_answer = frontier_answer if frontier_override_triggered else incumbent_answer`).
2. **Frontier max-support tie-break** (when `enable_frontier_max_support_tiebreak`):  
   - `build_merged_support_histogram_for_tiebreak` → `resolve_frontier_bias_max_support_tiebreak` (`experiments/frontier_max_support_tiebreak.py`)  
   - `pick_answer_text_for_normalized_group` selects **literal answer text** for the normalized group key.
3. **Optional hybrid seed overlay** (`resolve_direct_hybrid_seed_overlay`) — gated by `enable_direct_hybrid_seed`.
4. **PAL overlay promotion** (`experiments/output_layer_repair.py`):  
   - **`decide_pal_strong_overlay_promotion`** — **gold-free** decision whether **`final_answer = pal_answer`** (PAL candidate string).  
   - Invoked from **`controllers.py`** with histogram counts, tie-break trigger/group, `strong_pal`, `pal_score`.  
   - When promotion returns **`True`**, **`final_answer`** becomes **`pal_answer`** (typically **PAL executable normalized stdout path** from **`_run_pal_seed_attempt`** / `execute_pal_code`).

**Implication for Track B:** The dominant failure mode is **not** “missing PAL execution” but **ordering**: overlay/tie-break/histogram **signals already encode** a better-aligned group, yet **`final_answer`** follows **PAL executable surface** or another channel. The **first** narrow fix should **reconcile `pal_answer` / `pal_json_answer` / `pal_execution_result.pal_stdout` discord** with **overlay + tie-break metadata** *without* introducing gold at inference.

### Supporting modules

| Concern | Primary location |
|--------|-------------------|
| Frontier tie-break math + answer lookup | `experiments/frontier_max_support_tiebreak.py` (`resolve_frontier_bias_max_support_tiebreak`, `pick_answer_text_for_normalized_group`) |
| PAL overlay promotion policy (gold-free) | `experiments/output_layer_repair.py` (`decide_pal_strong_overlay_promotion`) |
| PAL execution / stdout / normalized candidate | `experiments/pal_executor.py`, PAL seed path in **`DirectReserveFrontierGateController._run_pal_seed_attempt`** |
| Registry / method IDs | `experiments/frontier_matrix_core.py`, `experiments/strategy_seeded_semantic_diversity_frontier_v1.py` |
| Answer-group aggregation inside frontier exploration | `experiments/controllers.py` (`GlobalDiversityAggregationController` and related), potentially **`experiments/branching.py`** for pool/histogram keys |

### Grep inventory (keyword routing)

High-signal symbols already in-tree: `frontier_tiebreak_*`, `pal_overlay_*`, `selected_group`, `selector_candidate_pool`, `answer_group_support_counts`, `direct_reserve_answer`, `pal_execution`, `decide_pal_strong_overlay_promotion`.

---

## C. Candidate implementation options

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Pure metadata/surfacing bug fix** | Adjust ordering so surfaced **`final_answer`** matches already-recorded overlay/tie-break contract when PAL stdout conflicts | Conceptually smallest diff | Risk of unintended behavior change across methods unless tightly gated |
| **B. Offline replay policy module first** | Implement candidate commitment rule as **pure functions** over logged metadata; replay **`present_not_selected_replay_table.csv`** / fixtures | Zero API; guardrail counts before runtime | Does not fix production until wired |
| **C. Runtime opt-in variant + new method ID** | New **`METHOD`** entry (or flag on controller factory) enabling Track B gate **only** when selected | Default unchanged; A/B in harness | More boilerplate (registry + tests) |
| **D. Fixture/unit harness before runtime** | Extend tests to simulate overlay conflicts using JSON fixtures | Fast feedback; enforces no-gold | Must mirror production ordering carefully |

**Recommendation:** Combine **B + C + D**: **offline parity first**, then **opt-in runtime** behind a **new method ID** (or explicit factory flag only reachable via that ID), with **unit tests** grounded in fixtures **before** enabling live pilots.

---

## D. Recommended minimal implementation path

### Phase 0 — Offline-only (no API)

1. **`decide_pal_strong_overlay_promotion` supersession or sibling**  
   Add a **new gold-free function** (working name: **`decide_track_b_overlay_commitment_gate`**) in **`experiments/output_layer_repair.py`** that:
   - Inputs: normalized **`pal_json_answer`**, **`pal_execution_result.pal_stdout`**, **`pal_candidate_answer`**, **`combined_group_counts_base`**, **`tiebreak_meta`**, **`pal_overlay`-style fields** (applied flag, previous answer string, selection reasons — as already logged).
   - Output: **`(apply_patch: bool, surfaced_answer_if_patch: str | None, reason: str, diagnostics: dict)`**  
   - **Forbidden:** reading **`gold_answer`** or dataset oracle fields.

2. **Wire only behind opt-in**  
   In **`DirectReserveFrontierGateController.run`** (`controllers.py`), **after** tie-break, **before or instead of** unconditional `final_answer = pal_answer` from **`decide_pal_strong_overlay_promotion`**, call the new gate **only if**  
   `getattr(self, "enable_track_b_overlay_commitment_gate", False)` (exact attribute name TBD in implementation).

3. **New method ID (recommended)**  
   Register in **`strategy_seeded_semantic_diversity_frontier_v1.py`** + **`frontier_matrix_core.py`** + harness **`METHODS`** map:
   - **`direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_track_b_commitment_v1`**  
   → Runtime identical to current PAL method **except** Track B gate enabled via controller kwargs.

4. **Default behavior unchanged**  
   Existing **`..._pal`** ID keeps **`enable_track_b_overlay_commitment_gate=False`**.

### Phase 1 — Tests (before any live Cohere)

- Unit tests on **`decide_track_b_overlay_commitment_gate`** using **`tests/fixtures/present_not_selected_replay/*.json`** fields **without** importing **`gold_answer`** into decision code paths (fixtures may contain gold for offline assertions **in tests only**).

### Phase 2 — Offline cohort replay

- Recompute counterfactual-style outcomes on **`counterfactual_policy_summary.csv`** methodology for **guardrail cohorts** (both-correct **183**, PAL-only **5**) — script-level, **no API**.

### Phase 3 — Capped live pilot (only after Phase 1–2 pass)

- Single-flag **`run_cohere_real_model_cost_normalized_validation.py`** job with **only** the new method ID vs baseline, budget-capped — per contract §N.

---

## E. Tests to write first

| Test | Purpose |
|------|---------|
| **Schema tests** | Already present: **`tests/test_present_not_selected_replay_fixtures.py`** — keep green |
| **`test_track_b_overlay_gate_*`** | For each of **six** fixtures, feed **recorded metadata fields** into **`decide_track_b_overlay_commitment_gate`** (or final ordering shim); assert **predicted surfaced numeric** matches **expected policy outcome** defined **without gold at runtime** (test compares to fixture fields **outside** the unit under test) |
| **Regression: not global max-support** | Unit test that **`max_answer_group_support`** / global argmax is **not** invoked from new gate (e.g. monkeypatch / flag audit or explicit code path assertion) |
| **No gold in decision path** | Static or runtime assertion that gate entrypoints do not receive **`gold_answer`** (signature audit + negative test) |
| **No extra budget** | Gate functions take **metadata only**; assert **no** controller methods that expand frontier are called from unit tests |

### Offline replay (no API)

- Parse **`present_not_selected_replay_table.csv`** + **`counterfactual_policy_summary.csv`** rows for **flip counts** — pure Python, **no network**.

---

## F. Guardrail and no-go constraints

### Allowed runtime signals (contract §G)

- **`pal_overlay`** applied flag, previous answer, conflict flags  
- **`frontier_tiebreak_*`**, **`selected_group`**, histogram fields (`answer_group_support_counts`, etc.)  
- **`selector_candidate_pool`** structural entries  
- **`pal_execution`** structural disagreement (**json vs stdout**) — for **consistency checks**, not blind stdout priority  
- Existing guard / budget flags  

### Forbidden (contract §H)

- Gold / oracle / “if gold in tree pick gold”  
- Unconditional global **`argmax(histogram)`**  
- Unconditional DR / branch-score finals  
- Unconditional PAL stdout wins when overlay contract forbids  

### Stop conditions (contract §O)

- Guardrail flips exceed threshold before target failures improve  
- Offline replay shows no separation vs baseline  
- Metadata instability across seeds  

---

## G. Whether API is needed now

**No.** Design contract and replay memo both specify **offline replay and guardrail checks first.** API / Cohere pilot only **after** offline parity and regression budgets are acceptable.

---

## H. Exact next implementation query

Use this prompt for the **first coding session**:

> In ``, implement **Phase 0–1** only for Track B:  
> (1) Add **`decide_track_b_overlay_commitment_gate`** in **`experiments/output_layer_repair.py`** — gold-free, narrow overlay/PAL-json-vs-stdout consistency gate informed by **`decide_pal_strong_overlay_promotion`** and fixture **`openai_gsm8k_1087`**.  
> (2) Wire it in **`DirectReserveFrontierGateController`** behind **`enable_track_b_overlay_commitment_gate`**, default **False**.  
> (3) Register **`..._pal_track_b_commitment_v1`** method ID with that flag **True** only for the new ID.  
> (4) Add **`tests/test_track_b_overlay_commitment_gate.py`** covering all **six** fixtures; keep **`tests/test_present_not_selected_replay_fixtures.py`** passing.  
> **Do not** enable global max-support, **do not** use gold in runtime decisions, **do not** run API. **Do not** commit outputs.

---

### Inputs reviewed for this plan

- `docs/CURRENT_RESEARCH_HANDOFF_20260507.md`
- `docs/CURRENT_METHOD_STATUS_20260507.md`
- `docs/FAILED_DIRECTIONS_20260507.md`
- `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/track_b_commitment_design_contract.md`
- `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/present_not_selected_replay_report.md`
- Tables: `present_not_selected_replay_table.csv`, `counterfactual_policy_summary.csv` (referenced; methodology cited from replay report)
- `tests/fixtures/present_not_selected_replay/`, `tests/test_present_not_selected_replay_fixtures.py`
- Code: `experiments/controllers.py`, `experiments/output_layer_repair.py`, `experiments/frontier_max_support_tiebreak.py`, `experiments/pal_executor.py`, registries in `experiments/strategy_seeded_semantic_diversity_frontier_v1.py` / `experiments/frontier_matrix_core.py`

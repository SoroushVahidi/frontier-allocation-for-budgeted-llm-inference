# Track B final-answer pipeline audit

**Date:** 2026-05-07  
**Worktree:** ``  
**Scope:** Analysis only — no API calls, no commits, no runtime changes in this step.

This document explains why **`metadata.final_answer`** (controller commitment after the Track B gate) can **disagree** with **`final_answer_raw`** stored on harness rows and used for **`exact_match`**. The pilot case **`openai_gsm8k_98`** is the canonical example.

---

## A. Final-answer flow map (PAL `*_tiebreak_pal*` methods on Cohere validation harness)

Order is strict in `scripts/run_cohere_real_model_cost_normalized_validation.py`:

1. **Controller `run()`** (`experiments/controllers.py`, `DirectReserveFrontierGateController` family) computes **`final_answer`** through frontier selection, tie-break, optional overlays, then (when enabled) PAL branch logic including:
   - **`decide_track_b_overlay_commitment_gate`** — may set **`final_answer`** from **`recommended_answer`** and set **`pal_overlay.track_b_gate_override_applied`**.
   - **`decide_pal_strong_overlay_promotion`** — may replace **`final_answer`** with **`pal_answer`** and set **`pal_overlay.pal_overlay_applied`** — **skipped** when Track B sets **`skip_pal_strong_overlay`** after an override.
   - **`metadata["final_answer"]`** is written into the returned **`MethodResult.metadata`** (along with **`pal_overlay`**, histogram counts, tie-break fields, **`pal_execution`**, etc.).

2. **Harness record assembly** reads **`result.metadata`** and **`final_nodes`**.

3. **`evaluate_with_diagnostics()`** (same script, ~564–624):
   - **`choose_repair_answer(...)`** — builds an initial repaired dict from registry nodes (gold-free repair path).
   - **`apply_controller_committed_surfacing_for_evaluation(metadata, repaired, ...)`** — if **`metadata["final_answer"]`** is set, copies it to **`surfaced_final_answer_raw`** / **`chosen_*`** and sets **`final_answer_source`** = **`controller_metadata_final_answer`** (`experiments/output_layer_repair.py` ~776–799).
   - **`apply_pal_residual_strong_integration_fix(metadata, repaired, enabled=..., ...)`** — optional **evaluator-time** second pass; **enabled** when **`--pal-residual-strong-integration-fix`** is on **and** method id contains **`tiebreak_pal`** (~897–907). This may **overwrite** **`surfaced_final_answer_raw`** again (`output_layer_repair.py` ~435–578).
   - **`apply_finalization_guard_surfacing(...)`** — if enabled for the method.
   - **Exact correctness** = **`canonicalize_answer(surfaced_final_answer_raw) == canonicalize_answer(gold)`** (not `metadata.final_answer` in isolation).

4. **Row materialization** sets **`final_answer_raw`** = **`eval_diag["surfaced_final_answer_raw"]`** (~959) and stores **`result_metadata.pal_integration_evaluator`** from the integration sidecar (~914–915).

**Conclusion (flow):** The **scored** answer is **whatever the last enabled post-controller surfacing step leaves in `surfaced_final_answer_raw`**, not necessarily **`metadata.final_answer`**.

---

## B. Case `openai_gsm8k_98` — deep dive (saved `per_example_records.jsonl`)

Source: `outputs/cohere_track_b_ab_pilot_30case_20260507T204409Z/cohere_real_model_cost_normalized_validation_live_run_20260507T204409Z/per_example_records.jsonl`.

| Field | Baseline PAL | Track B |
|--------|--------------|---------|
| **`gold_answer`** | 75 | 75 |
| **`result_metadata.final_answer`** (controller) | 75 | **57** |
| **`controller_final_answer_raw`** (after commit surfacing) | 75 | **57** |
| **`final_answer_raw`** (stored / scored) | 75 | **93** |
| **`exact_match`** | 1 | 0 |
| **`pal_overlay.track_b_gate_override_applied`** | False | **True** |
| **`track_b_gate_decision.recommended_answer`** | — | **57** |
| **`pal_overlay.pal_overlay_applied`** | **True** | **False** |
| **`pal_integration_evaluator.pal_integration_fix_triggered`** | False | **True** |
| **`pal_integration_previous_answer`** | — | **"57"** |
| **`pal_integration_selected_answer`** | — | **"93"** |
| **`pal_integration_fix_reason`** | `skipped_pal_overlay_already_applied` | **`weak_frontier_plus_high_pal_score`** |
| **`pal_integration_conflict_answer`** | — | **"57"** |
| Row **`final_answer_source`** (implicit via diagnostics; mirrored in integration) | controller path | **`pal_residual_strong_integration_fix`** |

**Interpretation:** The controller **did** apply the Track B gate (**57**). Evaluator-time **`apply_pal_residual_strong_integration_fix`** then re-ran **`decide_pal_strong_overlay_promotion`** with **`incumbent_final_answer_raw`** = **`metadata.final_answer`** (**57**) and **promoted** executed PAL (**93**) because **`weak_frontier_plus_high_pal_score`** fired. That **replaced** the surfaced answer used for scoring.

The materializer is consistent: **`final_answer_raw`** reflects **`surfaced_final_answer_raw`** after **all** evaluator passes — so scoring used **93**, not **57**.

---

## C. All four Track B override rows — gate vs controller vs scored vs PAL integration

Pilot overrides: **`openai_gsm8k_80`**, **`85`**, **`98`**, **`108`** (`track_b_override_cases.csv`).

| case_id | Gold | Gate `recommended_answer` | `metadata.final_answer` | `final_answer_raw` (scored) | Integration triggered? | Integration **selected** |
|---------|------|---------------------------|-------------------------|-----------------------------|-------------------------|---------------------------|
| 80 | 20 | 2090 | 2090 | **20** | Yes | 20 (`weak_frontier_plus_high_pal_score`) |
| 85 | 11 | 8.4 | 8.4 | **-21** | Yes | -21 (same reason) |
| 98 | 75 | 57 | 57 | **93** | Yes | 93 |
| 108 | 88 | 104 | 104 | **76** | Yes | 76 |

Common structure for Track B overrides:

- **`pal_overlay.pal_overlay_applied`** is **False** (controller skipped PAL strong overlay after Track B).
- **`apply_pal_residual_strong_integration_fix`** **does not** skip on **`skipped_pal_overlay_already_applied`** (that branch applies when **`pal_overlay_applied`** is **True**, which is the baseline PAL path).

**Would harmful/neutral tags change if scoring used `metadata.final_answer` instead of `final_answer_raw`?**

- **98:** Controller **57** wrong vs gold **75**; scored **93** wrong — **still wrong** either way; tag stays **harmful** vs baseline only if baseline correctness is defined on scored field (baseline row **75** correct).
- **80:** Controller **2090** wrong vs gold **20**; scored **20** correct — **`exact_match` would flip to 0** if scored by controller only (integration **rescued** a catastrophic gate answer).
- **85:** Both controller (**8.4**) and scored (**-21**) wrong vs **11** — no flip.
- **108:** Controller **104** wrong; scored **76** wrong — no correctness flip vs gold **88**.

So **`final_answer_raw`** vs **`metadata.final_answer`** materially changes interpretation for **80** (and changes **who** looks “right” on paper).

---

## D. Source-code locations and field priority

### Controller commitment

- **`final_answer`** assembled and stored on **`metadata`** before **`MethodResult`** return — see **`metadata["final_answer"]`** in the large **`metadata = { ... }`** dict (~8801) and **`pal_overlay`** attachment (~8868–8871).

### Track B gate

- **`enable_track_b_overlay_commitment_gate`** block (~8236–8270): may set **`final_answer`** from gate output and **`skip_pal_strong_overlay = True`**; **`pal_overlay_applied`** stays **False**; **`pal_overlay_reason`** becomes **`track_b_gate_supersedes_pal_strong_overlay`**.

### Evaluator stack (`evaluate_with_diagnostics`)

```531:624:scripts/run_cohere_real_model_cost_normalized_validation.py
def evaluate_with_diagnostics(
    ...
    repaired = apply_controller_committed_surfacing_for_evaluation(md, repaired, dataset=dataset)
    repaired, pal_integration_sidecar = apply_pal_residual_strong_integration_fix(
        md,
        repaired,
        dataset=dataset,
        enabled=bool(enable_pal_residual_strong_integration_fix),
    )
    ...
    surfaced_raw = repaired.get("surfaced_final_answer_raw")
    ...
    exact_match = int(bool(surfaced_can == gold_can and surfaced_can is not None))
```

PAL integration is enabled for **`tiebreak_pal`** methods when the CLI flag is set (~897–907).

### `apply_controller_committed_surfacing_for_evaluation`

```776:799:experiments/output_layer_repair.py
def apply_controller_committed_surfacing_for_evaluation(
    ...
    if ctrl_raw:
        ...
        out["surfaced_final_answer_raw"] = ctrl_raw
        ...
        out["final_answer_source"] = "controller_metadata_final_answer"
        return out
```

### `apply_pal_residual_strong_integration_fix` — skip when overlay already applied at controller

```467:471:experiments/output_layer_repair.py
    if isinstance(pal_already, dict) and bool(pal_already.get("pal_overlay_applied")):
        sidecar["pal_integration_fix_reason"] = "skipped_pal_overlay_already_applied"
        return out, sidecar
```

**Incumbent** for the promotion decision is **`metadata["final_answer"]`** (~508–518), i.e. **post–Track B** commitment.

### Row write

```959:968:scripts/run_cohere_real_model_cost_normalized_validation.py
                                    "final_answer_raw": eval_diag.get("surfaced_final_answer_raw"),
                                    ...
                                    "controller_final_answer_raw": eval_diag.get("controller_final_answer_raw"),
```

**Priority for scoring:**  
`choose_repair` → **controller commit surfacing** → **PAL residual integration** (if enabled) → **finalization guard** → **`surfaced_final_answer_raw`**.

---

## E. Bug vs intended behavior classification

| Option | Verdict |
|--------|---------|
| **A. Intended:** PAL integration is the true final scorer after commitment | **Partially.** The helper is **documented** as evaluator-time alignment with strong PAL for **legacy / offline bundles** (`apply_pal_residual_strong_integration_fix` docstring ~442–446). It was **not** designed to model an explicit **Track B commitment that deliberately suppresses** controller PAL promotion. |
| **B. Bug:** Track B should update the same field PAL integration reads | **Incomplete.** Track B **does** set **`metadata.final_answer`**; integration **uses** it as incumbent. The bug is **not** “wrong field” but **policy collision**: integration **re-applies PAL promotion** when **`pal_overlay_applied`** is false — which is **always** true after a Track B override. |
| **C. Materialization / scoring bug:** wrong field for `final_answer_raw` | **No.** `final_answer_raw` correctly mirrors **`surfaced_final_answer_raw`** after the full evaluator pipeline. |
| **D. Design ambiguity:** multiple final-answer fields disagree | **Yes.** **`metadata.final_answer`**, **`controller_final_answer_raw`**, **`final_answer_raw`**, and **`pal_integration_selected_answer`** can all differ; only **`surfaced_final_answer_raw`** at the end drives **`exact_match`**. |

**Net:** **D** (ambiguous layered policy) with a **concrete integration gap**: Track B **suppresses** controller PAL overlay via **`skip_pal_strong_overlay`**, but that **does not** suppress evaluator-time **`apply_pal_residual_strong_integration_fix`**, because that path keys off **`pal_overlay_applied`**, not **`track_b_gate_override_applied`**.

---

## F. Recommended fix design (for a follow-up implementation pass)

1. **Contract:** After **`track_b_gate_override_applied`**, the **scored** surface should match **controller commitment** unless a **separate, documented** policy explicitly runs (none today).

2. **Minimal behavioral fix (evaluator):** In **`apply_pal_residual_strong_integration_fix`**, **skip** (or branch to “blocked_track_b_commitment”) when **`metadata.get("pal_overlay", {}).get("track_b_gate_override_applied")`** is true — analogous to **`skipped_pal_overlay_already_applied`**.

3. **Alternative / additional:** When Track B applies an override, set a metadata flag that satisfies the same skip path as controller PAL promotion (e.g. treat commitment as **`pal_overlay_applied`** for integration purposes only — **careful**: would change semantics of **`pal_overlay_applied`** in logs).

4. **Harness / CLI:** Keep **`--pal-residual-strong-integration-fix`** behavior documented for PAL methods; add a regression test that Track B + integration does not overwrite commitment.

5. **Offline replay:** Update assumptions (§G below).

---

## G. Required tests before implementation

1. **Unit:** Fixture **`metadata`** with **`track_b_gate_override_applied: True`**, **`final_answer: "57"`**, **`pal_execution`** such that integration **would** promote PAL — assert **`surfaced_final_answer_raw`** stays **57** after **`apply_pal_residual_strong_integration_fix`**.

2. **Unit:** **`pal_overlay_applied: True`** baseline — integration still **skipped** (`skipped_pal_overlay_already_applied`).

3. **Golden harness row:** Replay **`openai_gsm8k_98`** JSON row through **`evaluate_with_diagnostics`** (no API) — **`exact_match`** should align with chosen policy (likely match **`metadata.final_answer`** vs gold after fix).

---

## H. Offline replay: `scripts/replay_track_b_commitment_gate.py`

The script calls **`decide_track_b_overlay_commitment_gate`** only and scores **counterfactual_matches_gold** from **`recommended_answer`** / normalized group (~125–138, ~208–228). It **does not** simulate **`choose_repair_answer`**, **`apply_controller_committed_surfacing_for_evaluation`**, or **`apply_pal_residual_strong_integration_fix`**.

**Mismatch:** Offline replay answers “**would the gate’s override pick gold?**” — **not** “**what would `exact_match` be on the live harness?**” After any fix to evaluator ordering, replay should either:

- add an optional **post-process** that applies the **same** PAL integration policy to a mocked surfaced answer, or  
- document that replay is **gate-only** and **non-equivalent** to scored rows.

---

## I. Whether API is needed now

**No.** All conclusions follow from static code and archived **`per_example_records.jsonl`**.

---

## Root cause (one paragraph)

**Evaluator-time `apply_pal_residual_strong_integration_fix`** re-runs **`decide_pal_strong_overlay_promotion`** when controller **`pal_overlay_applied`** is false. Track B overrides intentionally skip controller PAL strong overlay, leaving **`pal_overlay_applied` false**, so integration **still runs** and can **overwrite** the post–Track B **`metadata.final_answer`** in **`surfaced_final_answer_raw`**. **`final_answer_raw`** in the harness faithfully records that post-integration surface — so **Track B does not reliably control the scored answer** under the current flag combination.

---

## Exact next action

1. **Freeze pilot interpretation:** Do **not** treat **`exact_match`** on Track B runs as evidence that the **gate** controls production/scored output until evaluator policy is fixed or **`--pal-residual-strong-integration-fix`** is disabled for Track B methods (product decision).

2. **Implement §F** (small, local skip when **`track_b_gate_override_applied`**) + **§G** tests — **no API**.

3. **Re-run offline replay / cached JSON** through **`evaluate_with_diagnostics`** to confirm **`final_answer_raw`** matches the chosen contract.

4. **Defer** another **live** Cohere pilot until **(a)** contract is fixed and **(b)** paired design (cached completions / interleaving) is addressed — see existing **`pilot_causal_audit.md`**.

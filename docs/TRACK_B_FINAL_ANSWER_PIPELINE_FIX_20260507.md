# Track B final-answer pipeline fix (evaluator layer)

**Date:** 2026-05-07  
**Worktree:** ``

## Bug / layering issue

Track B updates **`metadata["final_answer"]`** when **`track_b_gate_override_applied`** is true, but **`apply_pal_residual_strong_integration_fix`** could still run afterward because **`pal_overlay_applied`** stayed false (controller skipped PAL strong overlay). Evaluator-time **`decide_pal_strong_overlay_promotion`** then overwrote **`surfaced_final_answer_raw`** with executed PAL stdout — so **`final_answer_raw`** did not reliably reflect the Track B commitment.

See: `docs/TRACK_B_FINAL_ANSWER_PIPELINE_AUDIT_20260507.md`.

## Exact fix

In **`experiments/output_layer_repair.py`**, inside **`apply_pal_residual_strong_integration_fix`**, immediately after the existing **`skipped_pal_overlay_already_applied`** branch:

- If **`pal_overlay.track_b_gate_override_applied`** is true, **return early** without calling **`decide_pal_strong_overlay_promotion`**.
- Set **`pal_integration_fix_reason`** to **`"skipped_track_b_gate_override_applied"`** and **`pal_integration_skipped_reason`** to **`"track_b_gate_override_applied"`**.

No change to **`decide_track_b_overlay_commitment_gate`** or baseline PAL controller logic when no Track B override fires.

## Tests added

**`tests/test_track_b_final_answer_pipeline.py`**

- **A.** Override true → integration skipped; surfaced answer stays controller/commit (**57** on synthetic fixture).
- **B.** Override false → integration still promotes PAL (**93**) under the same PAL metadata (**unchanged** non–Track-B behavior).
- **C.** **`pal_overlay_applied`** true → still **`skipped_pal_overlay_already_applied`** (ordering preserved).
- **D.** Skip reason recorded (**`pal_integration_skipped_reason`**).
- **E.** Fixtures use only metadata fields (no gold in gate logic); archived **`openai_gsm8k_98`** row asserts honest outcome vs gold.

## Offline replay script

**`scripts/replay_track_b_commitment_gate.py`**: docstring and generated report note clarify **gate-only replay** — does not model full harness evaluator semantics.

## Case `openai_gsm8k_98` (offline, archived row)

With the fix, evaluator-time PAL integration **does not** replace the post-gate commitment:

- **Controller / commitment:** **57** (wrong vs gold **75**).
- **Previously scored (`final_answer_raw`):** **93** via **`weak_frontier_plus_high_pal_score`** (also wrong vs gold).

So the fix makes scored output **honor Track B** (**57**), which is **more faithful to the mechanism under test**; it is **not** strictly “better” vs gold for this case — **both 57 and 93 are incorrect** relative to **75**. The pilot’s harmful override classification assumed scoring tracked the gate; this fix aligns scoring with that contract.

## Is another Cohere pilot justified now?

**Premature for causal claims about the gate.** The evaluator now matches the intended **commitment → score** contract for overrides, but prior pilot **wins** were still dominated by **run-to-run drift**, not helpful overrides (`pilot_causal_audit.md`). Use a larger live run only for **population accuracy / cost** after paired design (cached completions or interleaving) is addressed — not to prove gate efficacy.

## Remaining caveat

Track B **gate policy** still needs tightening / offline validation separately; this change fixes **layering only**.

## Verification

- **Pytest:** `tests/test_present_not_selected_replay_fixtures.py`, `tests/test_track_b_overlay_commitment_gate.py`, `tests/test_track_b_final_answer_pipeline.py` — pass.
- **Ruff:** targeted files — pass.
- **API:** none run.

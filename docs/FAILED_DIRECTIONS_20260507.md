# Failed or unsafe directions — frontier iteration 2 (2026-05-07)

Short index of **negative results** and **offline-unsafe** counterfactuals so they are not repeated blindly. Evidence traces live under `outputs/` and mining reports—cite folders, not anecdotes.

---

## 1. PAL execution → selector pool merge (“poolfix”)

- **Tried:** Inject PAL execution outputs into selector-visible pools for commitment.
- **Evidence:** Added **~0** useful merged candidates in audited runs; dominant failure mode unchanged.
- **Why it failed:** Did not address commitment / surfacing ordering; pool noise without pairing rules can distract selectors.
- **Narrower variant?** Targeted, **flagged** merge only when duplicate normalization matches existing histogram branch—still requires offline replay.
- **No-go:** Blind pool injection “because PAL ran.”

---

## 2. Broad rate/ratio gate

- **Tried:** Wide temporal/rate gate on frontier expansion.
- **Evidence:** Exact accuracy **worsened** despite some coverage motion.
- **Why it failed:** Gate triggers too often; steals budget from productive branches.
- **Narrower variant?** Only with **offline calibration** on mined anchors and rollback tests.
- **No-go:** Rerun broad gate without new hypotheses.

---

## 3. Conservative rate/ratio gate (`override_allowed=0`)

- **Tried:** Conservative variant meant to avoid destructive overrides.
- **Evidence:** Exact still **worsened**.
- **Why it failed:** Selector-visible perturbations still changed outcomes even without explicit overrides.
- **No-go:** Assume “conservative” means “safe without replay proof.”

---

## 4. Selector-isolated exploration logging

- **Tried:** Extra exploration actions for logging / diagnostics.
- **Evidence:** Exact **worsened** because logging consumed **normal search/action budget**.
- **Why it failed:** Budget accounting—not metadata-only in practice.
- **Narrower variant?** Truly zero-cost logging hooks **outside** frontier action budget (design-level change).
- **No-go:** Spend expansion budget **only** for telemetry.

---

## 5. Naive global `max_answer_group_support` (offline counterfactual)

- **Tried:** Always commit histogram argmax support.
- **Evidence:** Fixes **16 / 23** present-not-selected failures **offline**, but **~39** regressions where PAL and externals were **already both correct** on the GSM8K band cohort.
- **Why unsafe:** Histogram mass can be wrong-yet-duplicated (`1083`) or omit gold buckets (`1095`); global argmax amplifies errors.
- **Narrower variant?** **Dedup + normalization + gated ties** as separate flagged policies with guardrail budgets.
- **No-go:** Ship global max-support as production selector.

---

## 6. DR-heavy commitment policies (offline)

- **Tried:** Counterfactuals that always surface **`direct_reserve_answer`** / max **`branch_score`** from DR lane.
- **Evidence:** **112–113** guardrail flips on already-correct rows.
- **Why unsafe:** DR peer is often correct globally but **not** the committed surface after overlay/tie-break/PAL—blind DR finals regress hard.
- **Narrower variant?** DR reconciliation **only when** tie-break metadata + pool sources agree on DR peer—requires spec + replay.
- **No-go:** Default “pick DR” finalizer.

---

## 7. `prefer_strong_pal_executable` (offline)

- **Tried:** Prefer strong executable PAL stdout as final.
- **Evidence:** **0 / 23** fixes on present-not-selected replay slice; executable stdout can disagree violently with economics (`1087`: **−66** vs gold **6**).
- **Why it failed:** PAL execution proves code ran, not that stdout matches problem semantics after overlay/tie-break.
- **Narrower variant?** PAL stdout as **input** to consistency checks vs overlay—not blind priority.
- **No-go:** “PAL strong ⇒ final answer.”

---

## 8. GSM8K structural “validator score” / static-audit triggers as runtime policy

- **Tried (local):** `experiments/gsm8k_structural_validate.py`, scaled PAL-code audit, Track A discovery diagnostics.  
- **Evidence:** universal score almost **flat** stratified by gold; PN-comparable slice **no** clean gold-vs-wrong gap; scaled triggers **missed** implementation bands (e.g. no signal met ≥20% gold_absent with ≤5% guardrail FP at chosen definitions).  
- **Why it failed (as ranker):** signal is **telemetry**, not a safe commitment or retry gate.  
- **No-go:** wire structural score or raw audit triggers into **runtime** selection, reranking, or auto-retry without a new calibrated contract + replay proof.

---

### Cross-reference

- Offline replay tables: `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/counterfactual_policy_summary.csv` (local bundle).  
- Track B contract: `outputs/.../track_b_commitment_design_contract.md`.

# Current method status — frontier iteration 2 (2026-05-07)

Snapshot of **runtime-relevant** method IDs vs **historical** IDs. For registry detail see `docs/METHOD_REGISTRY_CANONICAL_20260429.md`.

---

## Active headline internal method (real-model diagnostics)

| Name | ID | Status | Claim posture |
|------|-----|--------|-----------------|
| **PAL + retry / guarded PAL** | `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal` | **Current best engineered line** for diverse-root real-model GSM8K-style runs | **Limited** — competitive vs `external_l1_max` on several bundles; **no** robust superiority claim |

**Composition (informal):** diverse-root **direct reserve** + **guarded** discovery + **k=1** frontier structure + **frontier4** + **frontier tie-break** + **PAL** integration + **empty-code PAL retry**.

---

## External baselines

| ID | Role |
|----|------|
| `external_l1_max` | **Primary** headline external comparator. |
| `external_tale_prompt_budgeting` | Token-budget-style external protocol. |
| `external_s1_budget_forcing` | Budget-forcing external protocol. |
| `external_l1_exact` | Diagnostic fairness / length contract—not the main “beat L1” headline bar. |

---

## Historical / non-headline internal references

| ID | Role |
|----|------|
| `strict_f3` | Matched-surface manuscript representative — **do not** treat as current PAL-line outcome. |
| `strict_gate1_cap_k6` | Broader strict phased default — distinct surface from PAL+retry bundle. |
| `strict_f2` | Secondary depth reference. |
| `direct_reserve_diverse_root_frontier_v1_guarded` | Guarded base without PAL/tiebreak stack—superseded for PAL experiments. |

---

## Parked / failed variant families (see `docs/FAILED_DIRECTIONS_20260507.md`)

- Rate/ratio gates (broad and conservative) — exact regressions.  
- Selector-isolated exploration logging — budget regression.  
- Execution-pool merge / poolfix — no decisive win.  
- Offline-only unsafe selectors: naive global **`max_answer_group_support`**, DR-heavy finals, **`prefer_strong_pal_executable`** on present-not-selected slice.

---

## Track B (pushed in `bc693b8`)

| Name | ID | Status |
|------|-----|--------|
| **Track B commitment (opt-in)** | `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_track_b_commitment_v1` | **Merged** behind opt-in method ID; evaluator honors override for scored finals. **Causal benefit unproven**—treat as **experimental**, not a closed win. |

## Next candidates (post-`bc693b8`)

| Track | Hypothesis | Status |
|-------|------------|--------|
| **Target-staged PAL retry** | Explicit target/units/subgoals before PAL code (schema-mining motivated) | **Local scaffold** only—manifest unarmed; needs review + optional `data/` vendoring |
| **Structural validator / static audit** | PAL/trace shape telemetry | **Local** eval scripts—**not** a runtime policy until recalibrated |
| **Track A / TRCE** | Gold-absent structured discovery | Parallel direction; smaller share of newest preferred failures |

---

## Claim status summary

| Topic | Safe today? |
|-------|----------------|
| PAL+retry **directionally** ahead on **300-case paired** bundle | Yes, with CI / *p* caveats |
| Universal or **statistically decisive** dominance vs `external_l1_max` | **No** |
| 30-case pilot ranking PAL below all externals as universal truth | **No** (small *n*) |
| Track B offline replay “fixes” imply safe global selector | **No** — guardrail regressions documented |

# Two-Stage Deferral Target Analysis (2026-05-23, Offline Only)

## Scope and constraints
- No API calls were made.
- Existing artifacts only.
- All counterfactual policies are **diagnostic-only** and **not promoted**.
- Gold/exact fields are used only for offline evaluation.

## Inputs
Primary MATH-500 diagnostic inputs:
- `outputs/math500_fta_transfer_diagnostic_20260523/complete_case_records.csv`
- `outputs/math500_fta_transfer_diagnostic_20260523/gate_decomposition.csv`
- `outputs/math500_fta_transfer_diagnostic_20260523/variant_summary.csv`
- `outputs/math500_fta_transfer_diagnostic_20260523/override_reason_distribution.csv`

GSM8K aggregate references used to reconstruct conditional behavior:
- `outputs/overnight_fix5_promotion_grade_validation_20260519T040621Z/.../per_example_records.jsonl`
- `outputs/fix6_lovec_independent_extra_action_pilot_20260519T163021Z/.../per_example_records.jsonl`
- `outputs/final_fix24_all_external_validation_20260519_20260520T000902Z/.../per_example_records.jsonl`

## Outputs produced
- `outputs/two_stage_deferral_target_analysis_20260523/manifest.json`
- `outputs/two_stage_deferral_target_analysis_20260523/conditional_source_accuracy.csv`
- `outputs/two_stage_deferral_target_analysis_20260523/ldg_target_regret.csv`
- `outputs/two_stage_deferral_target_analysis_20260523/dataset_region_source_ranking.csv`
- `outputs/two_stage_deferral_target_analysis_20260523/diagnostic_variant_summary.csv`

---

## Region definitions
Precedence partition used for both datasets:
1. `ldg_trigger`: FIX-2 low-depth trigger region (`fix2_is_low_depth=True`)
2. `eco_trigger`: not LDG, and ECO unanimity condition holds
3. `no_gate`: neither condition
4. `all`: full set

---

## 1) Region sizes
- MATH-500 complete cases: `488`
  - LDG: `261`
  - ECO: `0`
  - No-gate: `227`
- GSM8K aggregate: `720`
  - LDG: `207`
  - ECO: `5`
  - No-gate: `508`

(From `conditional_source_accuracy.csv`.)

---

## 2) Conditional source accuracy highlights

### MATH-500
- All: frontier `26.23%`, L1 `30.33%`, external-majority `27.66%`, pooled-4 `29.71%`, current FTA `27.66%`.
- LDG region: frontier `16.09%`, L1 `21.07%`, external-majority/current FTA `18.77%`, pooled-4 `21.84%`.
- No-gate region: frontier `37.89%`, L1 `40.97%`, pooled-4 `38.77%`.
- ECO region: empty (`0`).

### GSM8K aggregate-720
- All: frontier `75.28%`, L1 `77.64%`, external-majority `80.28%`, pooled-4 `82.08%`, current FTA `80.69%`.
- LDG region: frontier `44.44%`, L1 `57.00%`, external-majority/current FTA `60.87%`, pooled-4 `63.29%`.
- ECO region (`n=5`): frontier `0%`, externals/FTA `100%`.
- No-gate region: frontier/current FTA `88.58%`, pooled-4 `89.57%`, L1 `85.83%`.

(From `conditional_source_accuracy.csv`.)

---

## 3) LDG-target diagnostics (regret / recoveries)

### MATH-500 LDG region (`n=261`)
- Oracle-over-sources: `92/261 = 35.25%`
- Current LDG fallback (current FTA in LDG): `49/261 = 18.77%`
- Regret to oracle: `43`
- L1 in LDG: `55/261 = 21.07%`
- Current LDG fallback vs frontier: recoveries `27`, regressions `20`, net `+7`
- Current LDG fallback vs L1: recoveries `14`, regressions `20`, net `-6`

### GSM8K LDG region (`n=207`)
- Oracle-over-sources: `160/207 = 77.29%`
- Current LDG fallback: `126/207 = 60.87%`
- Regret to oracle: `34`
- L1 in LDG: `118/207 = 57.00%`
- Current LDG fallback vs frontier: recoveries `56`, regressions `22`, net `+34`
- Current LDG fallback vs L1: recoveries `21`, regressions `13`, net `+8`

(From `ldg_target_regret.csv`.)

---

## 4) Source-ranking transfer table
Ranking source: `dataset_region_source_ranking.csv`

Key ranking contrasts:
- MATH-500 LDG: `pooled4 > L1 > external-majority ~= current FTA > frontier > S1 > TALE`
- GSM8K LDG: `pooled4 > external-majority ~= current FTA > S1 > L1 > TALE > frontier`
- MATH-500 all: `L1` ranks first.
- GSM8K all: `pooled4` first, then current FTA/external-majority.

This is a target-order inversion inside LDG across datasets.

---

## 5) Diagnostic variants (all examples)
(From `diagnostic_variant_summary.csv`.)

### MATH-500
- Current FTA: `27.66%`
- LDG->L1 then ECO: `28.89%` (`+1.23pp vs current FTA`)
- LDG->external3(L1-tie) then ECO: `29.30%` (`+1.64pp vs current FTA`)
- LDG->pooled4 then ECO: `29.30%` (`+1.64pp vs current FTA`)
- Always L1: `30.33%` (best among non-oracle diagnostics)
- Pooled-4: `29.71%`

### GSM8K aggregate-720
- Current FTA: `80.69%`
- LDG->L1 then ECO: `79.58%` (`-1.11pp vs current FTA`)
- LDG->external3(L1-tie) then ECO: `81.11%` (`+0.42pp vs current FTA`)
- LDG->pooled4 then ECO: `81.39%` (`+0.69pp vs current FTA`)
- Always L1: `77.64%`
- Pooled-4: `82.08%`

---

## 6) Trigger-transfer vs target-transfer conclusions

### Is LDG a transferable risk detector?
Yes, **as a risk detector**. In both datasets, LDG regions are much harder than no-gate regions:
- MATH-500 frontier: LDG `16.09%` vs no-gate `37.89%`
- GSM8K frontier: LDG `44.44%` vs no-gate `88.58%`

### Is fallback target non-transferable?
Yes. The best fallback ordering changes by dataset/region.
- On MATH-500 LDG, L1 materially beats current external-majority/FTA target.
- On GSM8K LDG, current external-majority target beats L1.

### Does MATH-500 support a two-stage framework?
Yes, diagnostically:
1. Detect unreliable frontier region (LDG trigger).
2. Calibrate fallback target by surface/region (not one-size-fits-all ordering).

### ECO behavior
- GSM8K ECO is rare (`5/720`) but high precision (all 5 repaired).
- MATH-500 ECO trigger is absent (`0/488`), indicating rarity under current unanimity condition on this artifact.
- Breakdown of ECO preconditions:
  - MATH-500: among non-LDG `direct_frontier_agree` rows (`130`), unanimous externals appear in `57`, but **none** disagree with frontier (`0`), so ECO never fires.
  - GSM8K: among non-LDG `direct_frontier_agree` rows (`456`), unanimous externals appear in `392`, and `5` disagree with frontier, matching ECO fires (`5`).

---

## Strongest safe research claim (diagnostic-only)
A **trigger-vs-target decomposition** is empirically supported offline:
- LDG appears to transfer as a frontier-risk detector across GSM8K and MATH-500.
- The fallback target ranking does not transfer cleanly; MATH-500 requires different fallback calibration than GSM8K.
- Therefore, a two-stage approach (risk detection first, target calibration second) is a better explanatory frame than a single fixed FIX-2 fallback target.

This is not promotion-grade evidence and should be framed as offline transfer diagnostics only.

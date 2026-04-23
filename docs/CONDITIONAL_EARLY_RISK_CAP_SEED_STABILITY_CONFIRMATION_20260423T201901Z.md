# Conditional early risk-cap seed-stability confirmation (2026-04-23)

## Rationale

This pass is the next minimal confirmation after:
- targeted conditional early intervention evaluation, and
- tiny local threshold sensitivity around `strict_f3_conditional_early_risk_cap_k2_v1`.

Given prior judgment (`fragile positive`), this pass widens only the **seed** dimension while keeping all other contracts fixed.

## Fixed evaluation contract

- Replay surface source: `outputs/canonical_full_method_ranking_20260421T212948Z/per_case_outcomes.csv`
- Same manuscript-relevant surface dimensions:
  - datasets: `{openai/gsm8k, HuggingFaceH4/MATH-500, HuggingFaceH4/aime_2024}`
  - budgets: `{4,6,8}`
  - subset size per seed: `20`
- Anchor: `strict_f3`
- Candidate intervention: `strict_f3_conditional_early_risk_cap_k2_v1`
- Targeted hard slice contract (anchor-defined):
  - anchor failure
  - absent-from-tree
  - repeated-same-family present

## Seed contract (explicit)

- Base seeds from prior surface: `{11, 23}`
- Added confirmation seeds in this pass: `{37, 41}`
- All seeds evaluated: `{11, 23, 37, 41}`

This is a compact seed expansion only; no threshold sweep, no rival-maturation, and no new controller families.

## Output bundle

- `outputs/manuscript_slice_conditional_early_risk_cap_seed_stability_eval_20260423T201901Z/eval_manifest.json`
- `outputs/manuscript_slice_conditional_early_risk_cap_seed_stability_eval_20260423T201901Z/per_case_results.csv`
- `outputs/manuscript_slice_conditional_early_risk_cap_seed_stability_eval_20260423T201901Z/method_summary.csv`
- `outputs/manuscript_slice_conditional_early_risk_cap_seed_stability_eval_20260423T201901Z/target_slice_method_summary.csv`
- `outputs/manuscript_slice_conditional_early_risk_cap_seed_stability_eval_20260423T201901Z/per_seed_summary.csv`
- `outputs/manuscript_slice_conditional_early_risk_cap_seed_stability_eval_20260423T201901Z/aggregate_summary.json`

## Results: full replay surface (720 rows)

### `strict_f3` (anchor)
- accuracy: `0.6083` (438/720)
- absent-from-tree: `213` (`0.2958`)
- present-not-selected: `69` (`0.0958`)
- repeated same-family present: `629` (`0.8736`)
- gold-in-tree: `507` (`0.7042`)
- avg actions/expansions/verifications: `5.3278 / 4.9514 / 0.3764`

### `strict_f3_conditional_early_risk_cap_k2_v1`
- accuracy: `0.6292` (453/720), **+0.0208 vs anchor**
- absent-from-tree: `201` (`0.2792`), **-12 vs anchor**
- present-not-selected: `66` (`0.0917`), **-3 vs anchor**
- repeated same-family present: `626` (`0.8694`), **-3 vs anchor**
- gold-in-tree: `519` (`0.7208`), **+12 vs anchor**
- avg actions/expansions/verifications: `5.2708 / 5.1847 / 0.0861`
- head-to-head vs anchor: improved `176`, worsened `161`, unchanged `383`

## Results: targeted hard slice (192 rows)

Slice is anchor-defined (`strict_f3` failure + absent-from-tree + repeated same-family present), so anchor replay is by construction:
- accuracy `0.0000`
- absent-from-tree `192`
- repeated same-family `192`
- gold-in-tree `0`

Candidate (`strict_f3_conditional_early_risk_cap_k2_v1`) on this exact slice:
- accuracy: `0.5938` (114/192)
- absent-from-tree: `62` (`0.3229`)
- present-not-selected: `16` (`0.0833`)
- repeated same-family present: `168` (`0.8750`)
- gold-in-tree: `130` (`0.6771`)
- head-to-head vs anchor: improved `114`, worsened `0`, unchanged `78`

## Per-seed summary (candidate vs anchor)

Full surface:
- seed `11`: accuracy `0.6667` vs `0.6167`; absent `43` vs `51`; repeated `157` vs `158`; gold-in-tree `137` vs `129`
- seed `23`: accuracy `0.6111` vs `0.6444`; absent `56` vs `51`; repeated `157` vs `161`; gold-in-tree `124` vs `129`
- seed `37`: accuracy `0.6167` vs `0.5833`; absent `52` vs `52`; repeated `156` vs `159`; gold-in-tree `128` vs `128`
- seed `41`: accuracy `0.6222` vs `0.5889`; absent `50` vs `59`; repeated `156` vs `151`; gold-in-tree `130` vs `121`

Target hard slice:
- seed `11`: accuracy `0.7234`, absent `8`, repeated `41`, gold-in-tree `39`
- seed `23`: accuracy `0.4681`, absent `20`, repeated `41`, gold-in-tree `27`
- seed `37`: accuracy `0.4800`, absent `22`, repeated `45`, gold-in-tree `28`
- seed `41`: accuracy `0.7083`, absent `12`, repeated `41`, gold-in-tree `36`

## Stability judgment and gate

Compact judgment from this pass: **stable positive**.

Promotion-gate check (for this seed-confirmation step):
- preserve/improve accuracy vs `strict_f3`: **pass** (`0.6292` vs `0.6083`)
- no material absent-from-tree worsening: **pass** (`201` vs `213`)
- no material repeated-same-family worsening: **pass** (`626` vs `629`)
- upstream tree-entry interpretation retained: **pass** (`gold_in_tree +12`, present-not-selected not worsened)

## Recommendation

**Recommendation: promote later.**

Interpretation of "promote later" here:
- This setting now has seed-stability support on the same manuscript-relevant replay contract.
- Keep it non-canonical until a dedicated canonical decision pass updates source-of-truth artifacts.
- Next step, if taken, should be a narrow canonical-compliance promotion check rather than new threshold/family exploration.

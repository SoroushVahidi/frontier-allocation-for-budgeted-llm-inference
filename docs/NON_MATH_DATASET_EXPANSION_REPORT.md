# Non-Math Dataset Expansion Report

## What was added?
- Added a selective non-math expansion run at:
  - `outputs/non_math_dataset_expansion_20260424T230500Z/`
- Datasets successfully included:
  - `google-deepmind/natural-plan`
  - `Idavidrein/gpqa` (GPQA Diamond config)

## Why these datasets?
- **Natural Plan** was first priority and is now integrated via the existing git-clone dataset pathway.
- **GPQA Diamond** was second priority and was feasible through Hugging Face access in this environment.
- Both are non-math reasoning-oriented and expand evidence beyond GSM8K/MATH/AIME-only matched surfaces.

## Subset/config choices
- Budgets: `4,6,8`
- Seeds: `11,23,37,41,53`
- Subset target per dataset/seed: `20` (pilot-scale in this run)
- Natural Plan task selection: `trip_planning` (deterministic filtering where available)
- GPQA config: `gpqa_diamond` with deterministic option shuffling and letter-label gold answers for automatic MC grading.

## Methods/baselines evaluated
- `strict_f3`
- `strict_gate1_cap_k6`
- `strict_f3_anti_collapse_weak_v1`
- `external_l1_max`
- `external_s1_budget_forcing`
- `external_tale_prompt_budgeting`
- `self_consistency_3`
- `self_consistency_5`

## Key quantitative findings
Aggregate over both non-math datasets in this run:
- `strict_f3`: **0.6245**
- `self_consistency_3`: **0.6172**
- `strict_f3_anti_collapse_weak_v1`: **0.6081**
- `external_l1_max`: **0.4505**

Paired tests:
- `strict_f3` vs `self_consistency_3`: delta **+0.0073**, 95% CI **[-0.0495, 0.0641]**, p **0.8497** (not decisive)
- `strict_f3` vs `external_l1_max`: delta **+0.1740**, 95% CI **[0.1136, 0.2326]**, p **0.00033** (decisive)
- `strict_f3_anti_collapse_weak_v1` vs `strict_f3`: delta **-0.0165**, 95% CI **[-0.0733, 0.0385]**, p **0.6081** (no clear improvement)
- `strict_f3` vs `strict_gate1_cap_k6`: delta **+0.0385**, 95% CI **[-0.0183, 0.0971]**, p **0.2239** (not decisive)

Per-dataset top methods in this run:
- GPQA Diamond: `strict_f3` (`0.6233`) narrowly above `self_consistency_3` (`0.6200`)
- Natural Plan (trip planning slice): `strict_f3_anti_collapse_weak_v1` (`0.6341`), with `strict_f3` (`0.6260`) close behind

## Does frontier allocation remain competitive beyond math?
- Yes, in this run frontier variants remain competitive on both added non-math datasets.
- The strongest supported claim is superiority vs `external_l1_max` under matched budgets.
- Against self-consistency (`SC3`/`SC5`), point estimates are favorable for `strict_f3` but not statistically decisive at this pilot scale.

## Does calibrated weak anti-collapse help beyond math?
- Not consistently in this run.
- It helps on Natural Plan slice but underperforms `strict_f3` on GPQA aggregate; pooled paired test does not support a reliable net gain.

## Promote to main paper or keep as held-out evidence?
- This run should remain **held-out/appendix pilot evidence** because subset size is pilot-scale (`20` per dataset/seed).
- It strengthens the broader external-validity narrative but does not yet justify universal or headline dominance wording.

## Manuscript claim now supported
> Beyond math-only matched surfaces, frontier-allocation methods remain competitive on held-out non-math datasets (Natural Plan and GPQA Diamond) and decisively outperform strong near-direct length-control baselines under matched budgets; comparisons vs self-consistency are promising but not statistically decisive in pilot-scale evaluation.

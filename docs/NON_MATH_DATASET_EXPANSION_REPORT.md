# Non-Math Dataset Expansion Report

## Which non-math datasets were added?
- Added **Natural Plan** via `google-deepmind/natural-plan`.
- Added **GPQA Diamond** via `Idavidrein/gpqa` (config `gpqa_diamond`).

## Why were they selected?
- They directly address the reviewer concern that the matched surface was math-only.
- Natural Plan provides non-math planning-style reasoning with deterministic exact-match style grading under repository canonicalization.
- GPQA Diamond provides non-math, expert-level science multiple-choice reasoning with deterministic option mapping and letter-label evaluation.

## Which configs/subsets were used?
- Runner: `scripts/run_non_math_dataset_expansion.py`.
- Output bundle: `outputs/non_math_dataset_expansion_20260424T223313Z/`.
- Budgets: `4, 6, 8`.
- Seeds: `11, 23, 37, 41, 53`.
- Subset size target: `120` examples per dataset per seed.
- Natural Plan selection: deterministic subset, filtered to task `trip_planning` when available.
- GPQA Diamond selection: deterministic dataset shuffle per seed, deterministic option shuffle keyed by `(seed, index, question)`.

## Which methods and baselines were evaluated?
- Frontier-allocation family:
  - `strict_f3`
  - `strict_gate1_cap_k6`
  - `strict_f3_anti_collapse_weak_v1`
- Budget-matched external baselines:
  - `external_l1_max`
  - `external_s1_budget_forcing`
  - `external_tale_prompt_budgeting`
- Budget-matched self-consistency baselines:
  - `self_consistency_3`
  - `self_consistency_5`

## Does frontier allocation remain competitive beyond math?
Yes, on this non-math bundle frontier allocation remains competitive and strong:
- Best overall method was `strict_f3_anti_collapse_weak_v1` with mean accuracy `0.6292`.
- `strict_f3_anti_collapse_weak_v1` vs `external_l1_max`: delta `+0.1547`, 95% CI `[0.1301, 0.1778]`, permutation p-value `0.00033`.
- This supports a stronger claim against the near-direct length-control baseline under matched budgets.

## Does `strict_f3_anti_collapse_weak_v1` improve over default `strict_f3` beyond math?
- Directionally yes, but not decisively in this run:
  - delta `+0.0158`, 95% CI `[-0.0061, 0.0386]`, p-value `0.1879`.
- So the anti-collapse weak variant is promising but not yet conclusively superior to default `strict_f3` on this bundle.

## Are results strong enough to promote into the main paper, or remain held-out/appendix evidence?
- Since subset size is substantial (`120`/dataset/seed) and both Natural Plan + GPQA Diamond were feasible, the evidence is stronger than a pilot-only pass.
- Still, because several internal pairwise comparisons are not all decisive (e.g., anti-collapse vs `strict_f3`, anti-collapse vs `self_consistency_5`), the safest framing is:
  - **main-paper supportive external-validity evidence with calibrated wording**, and
  - full detail retained in appendix/supplement tables.

## What exact manuscript claim is now supported?
A defensible strengthened claim is:

> Frontier-allocation methods remain competitive beyond math-only benchmarks: on non-math Natural Plan and GPQA Diamond, frontier allocation is at least competitive with budget-matched self-consistency baselines and significantly outperforms strong budget-matched near-direct baselines (e.g., `external_l1_max`), while not supporting universal dominance claims.

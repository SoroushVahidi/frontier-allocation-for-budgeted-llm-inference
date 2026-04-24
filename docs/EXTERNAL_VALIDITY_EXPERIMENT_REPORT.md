# External Validity Experiment Report

## Scope
- New experiment bundle: `outputs/non_math_external_validity_20260424T121500Z/`.
- Contract: non-math held-out surface, matched budgets `{4,6,8}`, seeds `{11,23,37,41,53}`, and paired per-case outcomes.

## Which non-math dataset was added?
- Added **`TIGER-Lab/MMLU-Pro`** as an automatically gradable non-math held-out reasoning surface in this run.
- The script first checks Natural Plan availability and falls back to a non-math auto-gradable dataset if the Natural Plan clone is not locally ready.

## Which stronger baselines were added?
- `self_consistency_3`
- `self_consistency_5`
- `external_l1_max`
- `external_s1_budget_forcing`
- plus the internal comparator stack:
  - `strict_f3`
  - `strict_gate1_cap_k6`
  - `strict_f3_anti_collapse_weak_v1`

## Quantitative answer to key questions

### Does frontier allocation beat self-consistency under matched budget?
- Best frontier variant (`strict_f3_anti_collapse_weak_v1`) achieved **0.6333** vs `self_consistency_3` at **0.6033** (delta **+0.0300**).
- Paired test (`n=300`) vs `self_consistency_3`: 95% bootstrap CI **[-0.0467, 0.1100]**, permutation p-value **0.5011**.
- Interpretation: positive point estimate, **not statistically decisive** in this slice.

### Does calibrated weak anti-collapse improve over default?
- `strict_f3_anti_collapse_weak_v1`: **0.6333** vs `strict_f3`: **0.6300** (delta **+0.0033**).
- Paired test (`n=300`): 95% bootstrap CI **[-0.0733, 0.0800]**, permutation p-value **1.0000**.
- Interpretation: no decisive improvement; effectively tied in this run.

### Stronger external baseline comparison
- `strict_f3_anti_collapse_weak_v1` vs `external_l1_max`: delta **+0.1833**.
- Paired test (`n=300`): 95% bootstrap CI **[0.1067, 0.2600]**, p-value **0.00025**.
- Interpretation: strong advantage over this external baseline under matched budget.

## Are results strong enough to move beyond “math-only diagnostic”?
- **Yes, cautiously**: this adds a non-math matched-budget surface with explicit paired statistical testing and stronger baselines (including self-consistency variants).
- **No universal dominance claim** is supported; the evidence supports broader reasoning competitiveness, not blanket superiority across all settings.

## Manuscript-safe claim now supported
> On a held-out non-math reasoning surface (MMLU-Pro), frontier-allocation variants remain competitive under matched budgets and outperform strong length-control external baselines; against self-consistency, point estimates favor frontier allocation but remain statistically non-decisive in this pilot-scale slice.

## Real-model quantitative audit packaging
- Added a quantitative paper-table path that ingests existing real-model audit outputs and reports method accuracies, paired n, CI, p-value, and conservative interpretation labels.
- This table is explicitly designed to remain supportive/appendix-level unless significance and coverage justify stronger claims.

# Conditional K relaxation eval (20260421T165840Z)

- Output folder: `outputs/conditional_k_relaxation_eval_20260421T165840Z`
- Surface: matched hundred-case canonical failure-statistics rows (mixed budgets, mixed datasets).

## Aggregate accuracy
- `fixed_k6_control`: 0.6600
- `relax_on_cross_family_coverage_complete`: 0.6900
- `relax_on_low_marginal_gain_absence_false`: 0.5800
- `relax_on_multi_family_maturity`: 0.6700
- `relax_on_high_confidence_incumbent_but_no_challenger_gap`: 0.7300

## Head-to-head vs fixed_k6_control
- `relax_on_cross_family_coverage_complete`: {'unchanged': 55, 'worsened': 21, 'improved': 24}
- `relax_on_low_marginal_gain_absence_false`: {'worsened': 33, 'unchanged': 42, 'improved': 25}
- `relax_on_multi_family_maturity`: {'unchanged': 49, 'worsened': 25, 'improved': 26}
- `relax_on_high_confidence_incumbent_but_no_challenger_gap`: {'unchanged': 55, 'worsened': 19, 'improved': 26}

## Interpretation
- Overall winner: `relax_on_high_confidence_incumbent_but_no_challenger_gap`.
- Best non-control beats fixed K=6: `True`.
- Claims apply only to this evaluated surface and current strict-phased repo state.

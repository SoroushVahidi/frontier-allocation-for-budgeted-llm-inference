# Early answer-diversity maturation failure audit

- Status: experimental / provenance-only
- What was audited:
  - `experiments/controllers.py`
  - `experiments/frontier_matrix_core.py`
  - `tests/test_early_answer_diversity_maturation.py`
  - `scripts/run_early_answer_diversity_maturation_diagnostic.py`
  - `scripts/analyze_early_answer_diversity_maturation_failure.py`
  - `outputs/early_answer_diversity_maturation_diagnostic_20260428T201131Z/`
  - `outputs/early_answer_diversity_maturation_diagnostic_20260428T201809Z/`

Audit output package:
- `outputs/early_answer_diversity_maturation_failure_audit_20260428T203023Z/`
  - `early_maturation_failure_summary.csv`
  - `early_maturation_pairwise_case_audit.csv`
  - `early_maturation_trigger_audit.csv`
  - `early_maturation_recommendation.json`

## Why v1 and gated_v1 were tested

- `early_answer_diversity_maturation_v1` was introduced to force early answer-distinct maturation and target absent-from-tree failures.
- `early_answer_diversity_maturation_gated_v1` was introduced as a safer follow-up to only intervene under early-collapse triggers.

## Key numerical findings

From `early_maturation_failure_summary.csv` and `early_maturation_recommendation.json`:

- `v1` accuracy delta vs `strict_f3`: `-0.0556`
- `gated_v1` accuracy delta vs `strict_f3`: `-0.0926`
- `gated_v1` absent-from-tree delta vs `strict_f3`: `0.0000`
- `gated_v1` accuracy delta vs `external_l1_max`: `+0.1481`
- Pairwise gated vs strict_f3: 12 wins / 17 losses / 25 ties
- Override rate (gated): `0.3704`
- Estimated harm rate conditional on override: `0.35`

## Case-level failure patterns

- Losses are concentrated in higher budgets on this diagnostic slice:
  - budget-4 mean delta vs `strict_f3`: `0.0`
  - budget-6 mean delta vs `strict_f3`: `-0.1667`
  - budget-8 mean delta vs `strict_f3`: `-0.1111`
- Variants often changed early exploration behavior but did not convert those changes into correctness gains.
- Neither variant reduced absent-from-tree or present-not-selected rates relative to `strict_f3` in this audit slice.

## Trigger-level findings

From `early_maturation_trigger_audit.csv`:

- `recent_same_family_expansions_ge_2`: 20 hits (37.0%)
- `single_family_monopoly_with_admissible_alternative`: 20 hits (37.0%)
- skip reason `no_collapse_trigger`: 32 (59.3%)
- skip reason `outside_early_prefix`: 22 (40.7%)
- override applied rate: 20/54 (37.0%)

Correlation checks were weak:
- corr(repeated-family reduction, accuracy delta) ≈ `0.0118`
- corr(early diversity gain, accuracy delta) ≈ `0.0849`

Interpretation: reducing repeated-family behavior was not predictive of correctness gains on this slice.

## `strict_gate1_cap_k6` exclusion: fixed or explained

- In the audited historical directories, `strict_gate1_cap_k6` is excluded.
- Root cause is a runner-name mismatch, not a missing strict-gate1 family in strategy construction:
  - `build_frontier_strategies()` registers long canonical strict-gate1 names (`...fixed_k6_control`) rather than a short `strict_gate1_cap_k6` key.
- Runner fix was applied in `scripts/run_early_answer_diversity_maturation_diagnostic.py` via `_resolve_runtime_key()` alias mapping.
- Small smoke rerun confirms inclusion after fix:
  - `python scripts/run_early_answer_diversity_maturation_diagnostic.py --num-examples 6 --budgets 4`
  - `outputs/early_answer_diversity_maturation_diagnostic_20260428T202915Z/method_summary.csv` includes `strict_gate1_cap_k6`
  - corresponding `methods_excluded.csv` is empty.

## Final recommendation

- **a) discard this algorithmic line for promotion**.
- **b) keep v1 and gated_v1 only as provenance artifacts**.
- **c) revisit only if future real-model traces show repeated-family collapse with recoverable alternatives that are demonstrably rescued by intervention.**

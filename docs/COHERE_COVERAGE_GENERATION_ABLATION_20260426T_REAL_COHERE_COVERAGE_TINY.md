# Cohere coverage-generation ablation decision report (20260426T_REAL_COHERE_COVERAGE_TINY)

## Run scope
- Provider/model: `cohere` / `command-r-plus-08-2024`
- Cases: 9 GSM8K cases (same tiny-case composition: 3 absent, 3 present-not-selected, 3 control)
- Budget/seed: budget `4`, seed `11`
- Methods:
  - `strict_f3`
  - `external_l1_max`
  - `direct_reserve_strong_v1`
  - `direct_reserve_strong_plus_diverse_v1`
- Real API: enabled (`--run-real-api`)
- Output dir: `outputs/cohere_coverage_generation_ablation_20260426T_REAL_COHERE_COVERAGE_TINY`

## Key method-level results
From `per_method_summary.csv`:

| method | gold-present count/rate | selected-gold count/rate | absent-from-pool rate | present-not-selected rate | avg actions |
|---|---:|---:|---:|---:|---:|
| strict_f3 | 7 / 0.7778 | 0 / 0.0000 | 0.2222 | 0.7778 | 3.0 |
| external_l1_max | 7 / 0.7778 | 0 / 0.0000 | 0.2222 | 0.7778 | 1.0 |
| direct_reserve_strong_v1 | 6 / 0.6667 | 6 / 0.6667 | 0.3333 | 0.0000 | 4.0 |
| direct_reserve_strong_plus_diverse_v1 | 9 / 1.0000 | 9 / 1.0000 | 0.0000 | 0.0000 | 4.0 |

## Per-stratum notes
- `direct_reserve_strong_plus_diverse_v1` reached 100% gold-present and 100% selected-gold in all three strata for this tiny run.
- `direct_reserve_strong_v1` improved selection where gold was present, but had weaker control/absent coverage than baseline.
- Baselines (`strict_f3`, `external_l1_max`) had decent gold presence on this tiny slice but failed selection (0 selected-gold).

## Decision questions
1. **Did direct-reserve strong increase gold-present rate?**
   - `direct_reserve_strong_v1` did **not** increase gold-present vs strict_f3 on this tiny run (0.6667 vs 0.7778).

2. **Did diverse direct reserve increase gold-present rate further?**
   - Yes. `direct_reserve_strong_plus_diverse_v1` increased to 1.0000 gold-present.

3. **Did either method improve selected-gold rate?**
   - Yes. `direct_reserve_strong_v1` improved to 0.6667 and `direct_reserve_strong_plus_diverse_v1` to 1.0000 from baseline 0.0.

4. **Did any method hurt control cases?**
   - `direct_reserve_strong_v1` underperformed on control stratum (selected-gold 1/3).
   - `direct_reserve_strong_plus_diverse_v1` did not show control degradation on this tiny run (3/3 selected-gold).

5. **Is budget 4 still too tight?**
   - For this tiny diagnostic set, budget 4 appears sufficient for `direct_reserve_strong_plus_diverse_v1`.

6. **Recommended next step**
   - Promote `direct_reserve_strong_plus_diverse_v1` as the **next diagnostic runtime candidate** (not canonical replacement).
   - Run one additional tiny confirmatory repetition (same scale) to test stability.
   - Only return to learned scorer experiments after confirming this coverage/selection gain is stable across another tiny seed slice.

## Rule-based interpretation
- We observed strong gains in both gold-present and selected-gold without control harm for `direct_reserve_strong_plus_diverse_v1` on this run.
- Therefore the next engineering step is to continue with this diagnostic runtime method before investing further in reranking-only work.

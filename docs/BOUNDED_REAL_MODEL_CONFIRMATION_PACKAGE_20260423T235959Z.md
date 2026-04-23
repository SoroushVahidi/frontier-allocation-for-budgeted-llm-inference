# Bounded real-model confirmation package (20260423T235959Z)

## Why this was the highest-value remaining manuscript-strengthening task

From `docs/PAPER_OPEN_GAPS_AND_RISKS.md`, the highest unresolved manuscript-facing risk was **real-model breadth and stability** under bounded, controlled conditions, while preserving the matched-surface paper story and avoiding scope creep. This pass targets exactly that gap: a compact real-model check on the manuscript family and fair near-direct external anchor, without introducing new methods or datasets.

## Audit-first findings (before new execution)

1. **What small real-model confirmations already existed?**
   - `docs/CANONICAL_REAL_MODEL_VALIDATION_20260423T121500Z.md` + `outputs/canonical_real_model_validation_20260423T121500Z/` documented a bounded OpenAI real-model package.
   - `docs/BROAD_DIVERSITY_AGGREGATION_REAL_MODEL_CONFIRMATION_2026_04_18.md` documented broader-family real-model contact, but not a manuscript-main focused strict_f3 / strict_f2 / strict_gate1_cap_k6 package.

2. **Did existing evidence already cover the manuscript-facing main story sufficiently?**
   - **Not fully for this final check.** The prior canonical real-model package did not include `strict_f2`, which is a required internal anchor for this final compact manuscript-strengthening question.

3. **Decision from audit**
   - Run the smallest additional package needed to close that exact gap: keep the same manuscript-facing dataset family, single model/provider, one seed, one budget, and only the core methods.

## Exact bounded contract used

- Script: `scripts/run_canonical_real_model_validation.py`
- Provider/model: `openai/gpt-4.1-mini`
- Datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`
- Subset size: 2 examples per dataset (seeded sample)
- Seed(s): `[11]`
- Budget(s): `[4]`
- Methods included:
  - `strict_f3`
  - `strict_gate1_cap_k6`
  - `strict_f2`
  - `external_l1_max`
- Deterministic grading lane: `choose_repair_answer` + `canonicalize_answer`
- Runtime error handling: API/provider retries from `APIBranchGenerator`; per-example failures logged in `retry_error_log.csv`

## Output bundle

- `outputs/canonical_real_model_validation_20260423T235959Z/`

## Aggregate results

From `outputs/canonical_real_model_validation_20260423T235959Z/aggregate_summary.csv`:

- `external_l1_max`: accuracy **0.5000**
- `strict_f3`: accuracy **0.3333**
- `strict_f2`: accuracy **0.0000**
- `strict_gate1_cap_k6`: accuracy **0.0000**

Key bounded observations:
- `strict_f3` remains strongest among the three internal methods in this slice.
- `external_l1_max` is higher than `strict_f3` on this tiny real-model slice.

## Direct comparison to current manuscript-facing claim

Core question asked whether, on a compact real-model slice:
1. `strict_f3` remains competitive/strongest among current internal methods.
2. Strongest fair near-direct external baseline does not overturn the main conclusion.

Result on this bounded package:
- (1) **Yes**: `strict_f3` > `strict_f2` and `strict_gate1_cap_k6`.
- (2) **No on this slice**: `external_l1_max` > `strict_f3`.

## Honest limitations

- Very small sample size (18 scored rows total) and single provider/model.
- Single seed and single budget mean high variance and unstable rank risk.
- This package is strictly appendix/support evidence; it is not suitable to replace canonical matched-surface manuscript evidence.

## Final judgment

**Mixed support.**

- Supports the internal-ordering part (`strict_f3` strongest internal on this slice).
- Does not support the stronger external-non-overturn expectation on this specific tiny real-model slice.

## Recommendation for manuscript usage

Use as **appendix/support only** with explicit caveats:
- present as bounded real-model contact evidence,
- report mixed outcome transparently,
- do not promote this package into canonical headline evidence replacing matched-surface canonical results.

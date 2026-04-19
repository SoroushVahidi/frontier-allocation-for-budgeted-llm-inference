# Broad diversity/aggregation Cohere+Gemini confirmation (2026-04-18)

## Purpose

This pass is a larger (than the tiny prior real pass) but still bounded real-model confirmation sweep for the frozen broad diversity/aggregation family, using **Cohere API and Gemini API only**.

## Frozen compared methods

- `self_consistency_3`
- `adaptive_min_expand_1`
- `selective_sc_hybrid_v1`
- `broad_diversity_aggregation_v1`
- `broad_diversity_aggregation_strong_v1`

No new method families were introduced.

## Providers/models used

- Cohere: `command-r-plus-08-2024`
- Gemini: `gemini-2.0-flash`

OpenAI was not used.

## Actual run scale completed

Planned bounded scale:
- datasets requested: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`, `olympiadbench`
- subset size per dataset: `2`
- seeds: `11`
- budgets: `4`
- providers: Cohere + Gemini

Completed outcomes:
- planned provider×dataset×seed×budget cells: `8`
- successful cells with method outputs: `2` datasets worth of rows (Cohere on `HuggingFaceH4/aime_2024` and `olympiadbench`)
- failed cells: `6`

Failure pattern:
- Gemini returned quota/rate-limit 429 errors on all attempted cells.
- Cohere timed out on `openai/gsm8k` and `HuggingFaceH4/MATH-500` cells in this bounded run.

## Aggregate comparison result

In the completed rows, all five methods scored `0.0` mean accuracy.

So this sweep does **not** provide a meaningful accuracy ranking signal among the five frozen methods.

- gap to `self_consistency_3`: `0.0` for all methods in this run
- `broad_diversity_aggregation_v1` vs `broad_diversity_aggregation_strong_v1`: tie (`0.0` vs `0.0`)
- variant leadership status: `variant_unstable` (no separable signal)

## Diversity mechanism audit

Even on failed/underpowered outcomes, mechanism-level signals remain visible on the tiny completed Cohere slice:

- aggregation used frequently (`0.75` for v1; `1.0` for strong)
- forced exploration remained high (`0.875` for v1; `1.0` for strong)
- duplicate suppression fired non-trivially (`0.6875` for v1; `0.6458` for strong)
- realized diversity stayed poor (`low_diversity_realization_rate = 1.0` for both variants)

Interpretation: the mechanism activates, but answer-level diversity still often fails to materialize under real noise.

## Residual-loss analysis

`residual_loss_cases.json` is empty in this run because there were no aligned examples where `self_consistency_3` was correct and the selected broad candidate was wrong.

This is a power limitation artifact, not evidence that residual losses are solved.

## Main-candidate decision for this pass

Per the scripted selection rule (higher mean accuracy, tie-break by stability), this run records:

- main candidate: `broad_diversity_aggregation_v1`
- ablation sibling: `broad_diversity_aggregation_strong_v1`

But this should be read as **provisional only** because the effective signal is tie-level and underpowered.

## Hard conclusion

Under this Cohere+Gemini-only bounded sweep, the broad diversity/aggregation family is **not falsified**, but it is also **not decisively confirmed**.

The practical blocker in this pass was provider reliability/quota, which prevented sufficient successful real-model coverage to settle variant leadership.

So the family remains **real-model unstable / underconfirmed**, and the top remaining weakness is still:
- insufficient realized diversity under real generation noise,
- with unstable commit/selection behavior once noise and provider failures are present.

## Artifacts

Primary bundle:
- `outputs/broad_diversity_aggregation_cohere_gemini_confirmation_20260418/`

Includes all required machine-readable files:
- `manifest.json`
- `methods_compared.json`
- `providers_and_models.json`
- `datasets_compared.json`
- `run_scale_summary.json`
- `aggregate_comparison_summary.json`
- `per_dataset_tables.json`
- `per_provider_tables.json`
- `variant_selection_summary.json`
- `diversity_mechanism_audit.json`
- `residual_loss_taxonomy.json`
- `residual_loss_cases.json`
- `commands_assumptions_caveats.md`

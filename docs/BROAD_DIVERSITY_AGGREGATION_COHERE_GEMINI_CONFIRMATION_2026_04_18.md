# Broad diversity/aggregation Cohere+Gemini confirmation (2026-04-18)

## Purpose

This pass is a larger, cost-controlled **real-model** confirmation sweep for the frozen broad diversity/aggregation family.

It is not a new-family search and it does not use OpenAI API.

## Frozen compared methods

- `self_consistency_3`
- `adaptive_min_expand_1`
- `selective_sc_hybrid_v1`
- `broad_diversity_aggregation_v1`
- `broad_diversity_aggregation_strong_v1`

No additional method family was introduced.

## Provider/model policy and what actually executed

Requested providers/models:
- Cohere: `command-r-plus-08-2024`
- Gemini: `gemini-2.0-flash`

OpenAI API usage:
- explicitly excluded.

Execution reality in this environment:
- Cohere executed successfully.
- Gemini preflight failed with quota-exceeded HTTP 429, so Gemini run cells could not be executed in this pass.

So this pass is a **Cohere-executed + Gemini-attempted-but-blocked** real-model confirmation sweep.

## Actual bounded run scale completed

Configured sweep:
- datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`, `olympiadbench`
- subset size per dataset: `2`
- seeds: `11`
- budgets: `4`
- providers requested: `cohere,gemini`

Completed cells:
- targeted cells: `8`
- successful cells: `4` (Cohere only)
- aligned examples: `8`

## Aggregate result

Overall mean accuracy over budgets:
- `self_consistency_3`: `0.25`
- `selective_sc_hybrid_v1`: `0.25`
- `broad_diversity_aggregation_v1`: `0.25`
- `broad_diversity_aggregation_strong_v1`: `0.125`
- `adaptive_min_expand_1`: `0.0`

Interpretation:
- broad family remained competitive (v1 tied SC on this bounded real slice),
- but this run did **not** show broad-family dominance,
- and the strong variant underperformed v1.

## Per-dataset and per-provider behavior

Per-dataset and per-provider tables are exported to:
- `outputs/broad_diversity_aggregation_cohere_gemini_confirmation_20260418/per_dataset_tables.json`
- `outputs/broad_diversity_aggregation_cohere_gemini_confirmation_20260418/per_provider_tables.json`

Because Gemini was quota-blocked, per-provider results in this pass are effectively Cohere-only.

## Variant decision (explicit)

Decision rule:
1. higher overall mean accuracy over budgets,
2. tie-break with lower seed-stability std.

Selected main candidate from this real pass:
- **`broad_diversity_aggregation_v1`**

Ablation sibling:
- `broad_diversity_aggregation_strong_v1`

Why:
- v1 had higher mean accuracy than strong-v1 on the completed real slice (`0.25` vs `0.125`).

## Diversity-mechanism audit (most important)

For the selected main variant (`broad_diversity_aggregation_v1`) in this run:
- aggregation usage: high (`1.0`),
- forced exploration: active (`forced_explore_active_rate=1.0`),
- duplicate suppression: active (`duplicate_suppression_active_rate=1.0`),
- realized diversity: poor (`diversity_materialized_rate=0.0`, `low_diversity_realization_rate=1.0`),
- support concentration: highly concentrated (`mean_group_support_fraction=1.0`).

Interpretation:
- the mechanism activates,
- but realized answer diversity still frequently fails under real noise,
- so commit/aggregation can remain brittle.

## Residual-loss summary (SC beats selected broad candidate)

Residual taxonomy shows dominated failure in this run by:
- `insufficient_diversity_realized`

This matches the continuing bottleneck identified previously.

## Hard conclusion

1. **Did the broad diversity/aggregation family hold up?**
   - Partially. It stayed competitive (v1 tied SC) but did not show a clear broad win.

2. **Which variant is the real main candidate after this pass?**
   - `broad_diversity_aggregation_v1` (strong-v1 kept as ablation).

3. **Did it materially challenge self-consistency in real runs?**
   - Yes at tie-level in this bounded slice, but not as a decisive superior method.

4. **Biggest remaining weakness:**
   - low realized diversity under real-model generation noise, with resulting unstable aggregation/commit behavior.

5. **What remains missing for paper-grade confidence:**
   - successful multi-provider (including Gemini) execution at larger real-model scale,
   - plus stronger evidence that realized diversity reliably materializes under real noise.


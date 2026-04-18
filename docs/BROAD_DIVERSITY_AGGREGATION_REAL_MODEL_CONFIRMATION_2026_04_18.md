# Broad diversity/aggregation real-model confirmation (2026-04-18)

## Purpose

This pass is a **real-model confirmation pass** for the already-selected broad diversity/aggregation family, not a new-family search.

## Frozen method set

Compared methods (fixed):
- `self_consistency_3`
- `adaptive_min_expand_1`
- `selective_sc_hybrid_v1`
- `broad_diversity_aggregation_v1`
- `broad_diversity_aggregation_strong_v1`

No new method family was introduced.

## Real-model setup used

Runner:
- `scripts/run_broad_diversity_aggregation_real_model_confirmation_20260418.py`

Providers/models used:
- OpenAI: `gpt-4.1-mini`
- Cohere: `command-r-plus-08-2024`

Decoding/runtime settings:
- `temperature=0.1`
- `max_output_tokens=160`
- `timeout_seconds=45`
- API retry attempts: 4
- Retryable HTTP codes: `408,429,500,502,503,504`

Datasets included (real API-backed):
- `openai/gsm8k`
- `HuggingFaceH4/MATH-500`
- `HuggingFaceH4/aime_2024`
- `olympiadbench`

Bounded slice for feasibility:
- subset size per dataset: `1`
- seeds: `11`
- budgets: `4`

Important caveat:
- this is a very small bounded real-model slice designed to control API latency/cost;
- it is informative directionally, but insufficient for paper-grade statistical confidence.

## Aggregate outcomes (real-model bounded slice)

Overall mean accuracy over budgets (combined across both providers and all included datasets in this run):
- `broad_diversity_aggregation_v1`: `0.500`
- `self_consistency_3`: `0.375`
- `broad_diversity_aggregation_strong_v1`: `0.375`
- `adaptive_min_expand_1`: `0.125`
- `selective_sc_hybrid_v1`: `0.125`

Key gap vs SC:
- `broad_diversity_aggregation_strong_v1 - self_consistency_3 = 0.000` (tie in this bounded slice)
- `broad_diversity_aggregation_v1 - self_consistency_3 = +0.125`

Interpretation:
- the **broad family still looks competitive**,
- but the **strong variant did not reproduce a clear win over SC** in this specific real-model bounded run,
- while the non-strong sibling (`broad_diversity_aggregation_v1`) ranked first.

## Per-dataset behavior (bounded)

Across this run, both providers were represented on all four datasets.
Observed pattern:
- broad family variants were often competitive on the tiny slice,
- but behavior was unstable at this scale (expected with 1-example/dataset sampling).

See machine-readable tables:
- `outputs/broad_diversity_aggregation_real_model_confirmation_20260418/per_dataset_tables.json`

## Hard-slice/disagreement behavior (recoverable)

Hard-slice summary is exported in:
- `activation_behavior_summary.json`
- `aggregate_comparison_summary.json`

Given this tiny slice size, hard-slice rates should be treated as directional diagnostics only.

## Broad-family activation and diversity mechanism audit

From `diversity_mechanism_audit.json`:
- aggregation was frequently active (`aggregation_used_rate` high for both broad variants),
- forced exploration remained high,
- but low-diversity realization remained common:
  - `broad_diversity_aggregation_v1`: low-diversity realization rate `1.0`
  - `broad_diversity_aggregation_strong_v1`: low-diversity realization rate `0.875`

This indicates the mechanism is active, but realized answer diversity is still often limited in this bounded real-model run.

## Residual-loss analysis (SC > strong cases)

Residual case artifacts are written to:
- `residual_loss_taxonomy.json`
- `residual_loss_cases.json`

In this run, where SC beat strong, the retained category was mainly:
- `commit_timing_or_other`

Why this differs from simulator taxonomy:
- sample count here is tiny, so the classic three dominant categories from simulator confirmation are underpowered in this slice.

## What realism changed relative to simulator evidence

Compared with stricter simulator confirmation:
- simulator confirmation had strong-v1 clearly above SC,
- this real-model bounded pass did **not** replicate that clear strong-v1 lead,
- the broad family signal still exists, but the lead appears variant-sensitive and less stable under real generation noise.

## Hard conclusion

1. **Did `broad_diversity_aggregation_strong_v1` hold up in real-model confirmation?**
   - **Partially**: it remained competitive but did not clearly beat `self_consistency_3` in this bounded run (tie-level outcome).

2. **Is it still the leading main candidate?**
   - **Not clearly on this real slice**. The family remains strong, but `broad_diversity_aggregation_v1` outperformed strong-v1 in this bounded real-model pass.

3. **Paper-grade or still promising?**
   - **Still promising only**. This run is real-model evidence but too small for paper-grade confidence.

4. **Single biggest remaining weakness:**
   - **Insufficient realized diversity under real generations** (despite diversity-aware mechanism activation), plus associated commit/selection instability.

## Artifacts

Primary output bundle:
- `outputs/broad_diversity_aggregation_real_model_confirmation_20260418/`

Includes:
- `manifest.json`
- `methods_compared.json`
- `providers_and_models.json`
- `datasets_compared.json`
- `aggregate_comparison_summary.json`
- `per_dataset_tables.json`
- `activation_behavior_summary.json`
- `diversity_mechanism_audit.json`
- `residual_loss_taxonomy.json`
- `residual_loss_cases.json`
- `commands_assumptions_caveats.md`

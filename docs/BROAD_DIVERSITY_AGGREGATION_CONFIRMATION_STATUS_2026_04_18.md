# Broad diversity/aggregation confirmation status (2026-04-18)

## Purpose

This is a stricter confirmation/hardening pass for the broad diversity/aggregation family, not a new method search.

## Candidate freeze decision

From the stricter confirmation run:
- `broad_diversity_aggregation_strong_v1` is selected as the **main tracked candidate**.
- `broad_diversity_aggregation_v1` is retained as the **ablation sibling**.

Selection rule used:
- higher overall mean accuracy over budgets,
- tie-break by lower seed-stability standard deviation.

## Stricter broad confirmation setup

Compared methods:
- `self_consistency_3`
- `adaptive_min_expand_1`
- `selective_sc_hybrid_v1`
- `broad_diversity_aggregation_v1`
- `broad_diversity_aggregation_strong_v1`

Datasets:
- `openai/gsm8k`
- `HuggingFaceH4/MATH-500`
- `HuggingFaceH4/aime_2024`
- `olympiadbench`

Stricter settings vs prior light pass:
- subset size increased to `48`
- seeds increased to `11,23,37,47,59`
- budgets expanded to `4,6,8,10`

## Did the result hold up?

Short answer: **Yes in this stricter simulator confirmation pass.**

Key aggregate outcomes:
- `self_consistency_3`: `0.5338`
- `broad_diversity_aggregation_strong_v1`: `0.6524`
- gap to SC for strong variant: `-0.1187` (candidate above SC on mean over budgets)
- material narrowing flag: `true`

Gap reductions (candidate vs baselines):
- vs `adaptive_min_expand_1`: `+0.2534`
- vs `selective_sc_hybrid_v1`: `+0.2753`

## Robustness and distribution

Robustness indicators:
- candidate beats SC on `1059` aligned examples (`0.3043` rate)
- candidate loses to SC on `635` aligned examples (`0.1825` rate)

Not concentrated in one dataset:
- candidate wins over SC are distributed across all four datasets.

Hard-slice behavior:
- candidate remains strong on near-tie and hard-case-active slices,
- disagreement slice is improved but still somewhat unstable across variants.

## Diversity mechanism realism audit

Audit evidence suggests gains are tied to the intended mechanism:
- aggregation used on `~98.6%` of candidate examples,
- duplicate-penalty applied on `~43.8%` of candidate expansions,
- non-trivial diversity bonus usage (`mean_diversity_bonus_on_expand ~0.315`),
- high forced-explore rate (`~0.72`) indicating systematic delayed commitment,
- candidate still has many low-diversity realizations (important residual caveat).

## Residual-loss casebook summary

Where SC still wins vs candidate, main residual categories are:
1. `insufficient_diversity_realized`
2. `value_ranking_error_despite_diversity`
3. `aggregation_concentration_failure`

So remaining error is no longer only local gating; it is now a mix of:
- diversity not materializing on enough cases,
- ranking/selection mistakes even when diversity exists.

## Caveats

- This is still simulator-mode evidence (even though stricter than prior light pass).
- Real-model confirmation is still needed before final paper-grade claim strength.
- Diversity realization remains incomplete on a large subset of examples.

## Hard conclusion

Under stricter bounded evaluation, the broad diversity/aggregation family **does hold up as the leading serious method family** in this repo.

Current recommendation:
- treat `broad_diversity_aggregation_strong_v1` as the main central-method candidate,
- keep `broad_diversity_aggregation_v1` as ablation,
- move next to stronger realism confirmation (especially real-model validation) rather than opening a new method family.

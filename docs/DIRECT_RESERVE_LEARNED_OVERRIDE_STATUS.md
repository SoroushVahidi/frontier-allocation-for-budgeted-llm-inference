# Direct-reserve learned override status

This note describes `direct_reserve_strong_plus_diverse_learned_override_v1`. It is diagnostic-only and not a canonical manuscript-facing method.

## Motivation

`direct_reserve_strong_plus_diverse_v1` already creates useful answer candidates, but support-only final selection can miss a discovered correct answer. The learned override asks a narrower runtime question: when a saved RF or pairwise candidate scorer strongly prefers a different answer group, can it safely override the base selector?

## Relation to plus-diverse

The learned override uses the same direct-reserve plus-diverse candidate generation path and applies the scorer only at final answer-group selection. If the model is missing, features are incomplete, the learned answer is invalid, or the learned score margin is below threshold, it returns the base plus-diverse answer.

## Why margin-gated is not enough

The heuristic margin-gated selector is useful as a comparison, but it is brittle: on the first slice it made 9 overrides with 3 degradations and 2 control degradations. The learned RF override at threshold 0.05 made 5 overrides with 5 improvements, 0 degradations, and 0 control degradations on the same slice.

## Allowed learned models

Recommended diagnostic scorers are:

- `random_forest`
- `pairwise_logit`

HGB is excluded from recommendations because it degraded controls in the fresh scorer validation and the runtime override rejects HGB model types.

## Fresh zero-overlap evidence

Fresh GSM8K validation used 20 new problem IDs with 0 overlap against prior scorer slices. Base `direct_reserve_strong_plus_diverse_v1` selected gold at 0.60. Learned RF and pairwise reranking selected gold at 0.70, with 2 improvements, 0 degradations, and 0 control degradation.

## Threshold behavior

The runtime default is a conservative learned-score margin threshold of `0.05`. Offline validation keeps the threshold configurable through `scripts/run_direct_reserve_learned_override_eval.py --thresholds`.

## Offline threshold sweep

Artifact path: `outputs/direct_reserve_learned_override_eval_20260426T_LEARNED_OVERRIDE_DIAGNOSTIC/`.

| Slice | Selector | Selected-gold | Overrides | Improvements | Degradations | Control degradations |
|---|---:|---:|---:|---:|---:|---:|
| first 20260426T150000Z | base plus-diverse | 0.60 | 0 | 0 | 0 | 0 |
| first 20260426T150000Z | RF override margin 0.05 | 0.85 | 5 | 5 | 0 | 0 |
| first 20260426T150000Z | pairwise offline rerank | 0.85 | 7 | 5 | 0 | 0 |
| fresh zero-overlap | base plus-diverse | 0.60 | 0 | 0 | 0 | 0 |
| fresh zero-overlap | RF override margin 0.05 | 0.70 | 4 | 2 | 0 | 0 |
| fresh zero-overlap | pairwise offline rerank | 0.70 | 5 | 2 | 0 | 0 |

## Current recommendation

Keep `direct_reserve_strong_plus_diverse_learned_override_v1` opt-in and diagnostic-only. The RF threshold-0.05 override is ready for a tiny real validation under the bounded Cohere-only policy, but it should not become default or canonical without broader fresh validation across more cases, seeds, and providers.

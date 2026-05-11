# Direct L1 Seed Strengthening Preflight

## Bottleneck Targeted

The bottleneck is still discovery, not selector polish.

The PAL unresolved taxonomy showed that the main failure shape is gold-absent / frontier-collapse behavior: the correct answer often never enters the candidate pool, so selector-only changes do not address the root problem.

This preflight does not propose another selector patch. It prepares a stronger direct-seed experiment that stays on the candidate-generation side of the pipeline.

## Why the 43-Case Slice

The merged recovery coverage audit found 157 PAL still-failing covered cases.

The unresolved taxonomy then split those cases into:

- 43 direct-L1-anchor-potential cases
- 18 stronger patch-effect matches
- 97 wrong-supported-consensus / both-direct-and-frontier-wrong cases

The 43-case slice is the cleanest high-signal target because it is the only unresolved set with explicit direct-L1 evidence in the existing artifacts.

## Why Not Another Selector Patch

A selector patch can only help if the correct answer is already in the pool.

The current problem is earlier in the pipeline:

- candidate generation is incomplete
- gold often never enters the pool
- frontier search collapses onto a low-diversity wrong answer

So the safest next move is to strengthen the direct seed behind a new opt-in method ID, then validate that seed on a small exact diagnostic slice before any paid run.

## Current Direct L1 Anchor Behavior

From `experiments/controllers.py`, the current direct-L1 path is:

- a `direct_l1_anchor` diverse-prompt spec mapped to `direct_l1_max_budget`
- a direct-hybrid seed path that is opt-in behind `enable_direct_hybrid_seed`
- a second opt-in anchor path behind `enable_diverse_prompt_anchors`
- a special-case preserve/skip rule so `direct_l1_anchor` does not silently double-spend budget when the hybrid seed already ran

The key limitation is that this path is still only as good as the direct seed answer itself.

## Why the 15-Case Slice Is First

The first live diagnostic should stay tiny.

The preflight preserves this 15-case slice when present:

- `openai_gsm8k_297`
- `openai_gsm8k_168`
- `openai_gsm8k_180`
- `openai_gsm8k_190`
- `openai_gsm8k_197`
- `openai_gsm8k_213`
- `openai_gsm8k_264`
- `openai_gsm8k_347`
- `openai_gsm8k_367`
- `openai_gsm8k_376`
- `openai_gsm8k_391`
- `openai_gsm8k_204`
- `openai_gsm8k_228`
- `openai_gsm8k_233`
- `openai_gsm8k_354`

In the current artifacts, all 15 are present in the anchor-potential slice. They are a diagnostic starter set, not proof.

Exact-replay overlap from the existing artifacts:

- anchor-potential overlap with the 30-case exact replay: 8
- anchor-potential overlap with the 50-case exact replay: 14
- selected 15-case overlap with the 30-case exact replay: 8
- selected 15-case overlap with the 50-case exact replay: 8

## Recommended Stronger-Seed Design

Recommended next implementation:

- `direct answer plus independent arithmetic/unit self-check`

Why this one:

- it stays on the direct-seed path
- it is less invasive than a broader selector or routing rewrite
- it can be kept opt-in behind a new method ID
- it does not require changing production defaults

Suggested opt-in method ID:

- `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_l1_strong_seed_v1`

## Validation Ladder

Before any paid/live run, the validation ladder should be:

1. No-API method registry test first.
1. Validate the exact diagnostic slice loader.
1. Run a dry-run / call-plan check.
1. Only after explicit approval, run a live 15-case diagnostic.

## Claim Boundaries

- No external-baseline claim.
- No current accuracy claim.
- No runtime default change.
- No paid/model API calls.
- This is only preflight/design.


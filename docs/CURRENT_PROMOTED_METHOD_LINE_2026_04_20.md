# Current promoted method line (2026-04-20)

## Purpose

This note gives the shortest canonical answer to:
- what the current promoted method line is,
- why it is promoted,
- what problem it is trying to solve,
- what evidence currently supports it,
- and what the current refinement discipline has now selected as the default model.

## Current promoted line

The current promoted line inside the repository is still:

> **broad diversity-aware branch allocation with answer-support aggregation, strengthened by anti-collapse answer-group-aware allocation, soft repeat-expansion control, and a deterministic output-layer repair stage.**

This is still the same broad family. It is **not** a separate controller family.

## Important current refinement update

What changed is not the identity of the broad promoted family, but the **discipline used to test early-coverage refinements inside it** and the **current default model selected within that family**.

The repository now interprets hard-coverage refinements under a strict law:

> **finish F1 first, then F2, then F3**

for forced shallow balanced coverage over root families.

Under that stricter law, the broader default-decision pass selected:

> **`strict_gate1_cap_k6` as the current broad default promoted model on the evaluated surface.**

## Why this line is promoted

The strongest repository-backed diagnosis remains that many bad cases arise from:
- early-to-mid branch-family monopolization,
- repeated expansion of one high-priority branch,
- shallow child spawning without sufficient alternative maturation,
- and a smaller residual where the correct answer is present but not selected cleanly enough.

The promoted line directly targets both:
- structural tree-growth failures,
- and a subset of final output-layer failures,
rather than only late-stage thresholding.

## What it is trying to fix

The bottleneck is now best understood as:

> **under fixed budget, the controller still tends to over-expand one early-favored branch and does not yet reliably preserve and mature answer-distinct alternatives strongly enough.**

So the promoted line tries to improve:
- early answer-group survival,
- anti-collapse behavior,
- alternative maturation,
- control over repeated same-family expansion,
- and deterministic final-answer surfacing after branch selection.

## What evidence currently supports it

Current repository evidence supports the following bounded conclusions:
- anti-collapse design matters for realized budget use and controller behavior,
- answer-group-aware preservation and maturation are more relevant than generic diversity-for-diversity,
- strict-phased hard-coverage experiments materially changed the method-selection picture,
- capped-family follow-up experiments identified a useful anti-monopolization regime,
- and the final broader strict-phased decision pass selected `strict_gate1_cap_k6` over the strongest uncapped and strict-force finalists on the evaluated surface.

Primary decisive artifact:
- `FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`

## What it is not yet safe to claim

It is **not** yet safe to claim that this line is:
- a robust universal winner across every future surface,
- broadly superior to all strong external baselines,
- or fully closed without broader independent confirmation and stronger external-baseline maturity.

But it **is** now safe to say that the repository has selected a current broad default promoted model for the evaluated strict-phased surface.

## Current default promoted model inside the line

The current broad default promoted model is:
- **`strict_gate1_cap_k6`**

The strongest nearby anchors remain:
- `strict_gate1`
- `strict_f2`
- `strict_f3`
- `strict_gate2`

## Reading path

To understand this line quickly, read:
1. `CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`
2. `FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
3. `NEW_HUNDRED_NEWEST_VS_BEST_FAILURE_STATISTICS_20260421T032711Z.md`
4. `CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
5. `CURRENT_SAFE_CLAIMS.md`

## Safe one-sentence summary

> The current promoted repository line is still a broad diversity/aggregation controller strengthened by anti-collapse answer-group-aware allocation, repeat-expansion control, and deterministic output-layer repair, but the current broader strict-phased default-decision pass now selects **`strict_gate1_cap_k6`** as the repository’s broad default promoted model on the evaluated surface.
